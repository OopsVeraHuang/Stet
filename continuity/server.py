"""Loopback-only standard-library server for the single-user offline prototype."""
import argparse
import base64
import binascii
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
from urllib.parse import parse_qs, quote, urlsplit
import webbrowser

from .importing import ImportProblem, MAX_BYTES, strict_json
from .store import Store

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).with_name('static')


def make_server(directory, port=0):
    store = Store(directory)
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # No original text, queries or request bodies in access logs.

        def send(self, data, status=200, mime='application/json; charset=utf-8', filename=None):
            body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            if filename is not None:
                self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + quote(filename, safe=''))
            self.end_headers()
            self.wfile.write(body)

        def permitted(self, mutation=False):
            expected = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != expected:
                self.send({'error': '请使用启动时显示的 127.0.0.1 地址。'}, 403)
                return False
            origin = self.headers.get('Origin')
            if origin is not None and origin != 'http://' + expected:
                self.send({'error': '不允许跨站请求。'}, 403)
                return False
            if mutation and (self.headers.get('X-Continuity-Token') != token or
                             self.headers.get('Content-Type') != 'application/json'):
                self.send({'error': '请求校验失败，请刷新页面。'}, 403)
                return False
            return True

        def do_GET(self):
            if not self.permitted():
                return
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query, keep_blank_values=True)
            path = parsed.path
            try:
                if path in {'/i18n.js','/i18n-catalog.js'}:
                    self.send((ROOT/'app/static'/path[1:]).read_bytes(), mime='text/javascript; charset=utf-8')
                elif path == '/guide.html':
                    self.send((ROOT/'app/static/guide.html').read_bytes(), mime='text/html; charset=utf-8')
                elif path in {'/guide.zh.md', '/guide.en.md'}:
                    name = '14-getting-started.md' if path == '/guide.zh.md' else '15-getting-started.en.md'
                    self.send((ROOT/'docs'/name).read_bytes(), mime='text/markdown; charset=utf-8')
                elif path in {'/', '/app.js', '/style.css'}:
                    name, mime = {'/': ('index.html', 'text/html; charset=utf-8'),
                                  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                                  '/style.css': ('style.css', 'text/css; charset=utf-8')}[path]
                    self.send((STATIC / name).read_bytes(), mime=mime)
                elif path == '/api/session':
                    self.send({'token': token, 'mode': 'offline-literal-only'})
                elif path == '/api/messages':
                    self.send({'messages': store.messages(query.get('q', [''])[0],
                                                          query.get('source', [None])[0],
                                                          query.get('branch', [None])[0])})
                elif path.startswith('/api/messages/'):
                    self.send(store.detail(path.removeprefix('/api/messages/')))
                elif path == '/api/batches':
                    self.send({'batches': store.batches()})
                elif path.startswith('/api/original/'):
                    batch = path.removeprefix('/api/original/')
                    original = store.original(batch)
                    filename = next((b['filename'] for b in store.batches() if b['id'] == batch), 'continuity-original.txt')
                    self.send(original, mime='application/octet-stream', filename=filename)
                elif path in {'/api/examples/messages.json', '/api/examples/messages.md'}:
                    self.send((ROOT / 'examples' / path.rsplit('/', 1)[1]).read_bytes(), mime='text/plain; charset=utf-8')
                else:
                    self.send({'error': '页面不存在。'}, 404)
            except KeyError as error:
                self.send({'error': error.args[0]}, 404)
            except (OSError, sqlite3.Error):
                self.send({'error': '读取失败，请检查数据目录权限。'}, 500)

        def do_POST(self):
            if not self.permitted(mutation=True):
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_BYTES * 2:
                    raise ImportProblem('请求大小无效或超过限制。')
                self.connection.settimeout(15)
                body = strict_json(self.rfile.read(length).decode('utf-8'))
                if not isinstance(body, dict):
                    raise ImportProblem('请求必须为对象。')
                if self.path in {'/api/preview', '/api/import'}:
                    filename = body.get('filename')
                    if not isinstance(filename, str) or not filename or len(filename) > 255:
                        raise ImportProblem('文件名无效。')
                    filename = filename.replace('\\', '/').rsplit('/', 1)[-1]
                    raw = base64.b64decode(body.get('data', ''), validate=True)
                    result = store.preview(raw, filename) if self.path == '/api/preview' else store.import_file(raw, filename)
                    self.send(result)
                elif self.path == '/api/rebuild':
                    self.send(store.rebuild())
                elif self.path == '/api/remove-batch':
                    batch = body.get('batch_id')
                    if not isinstance(batch, str):
                        raise ImportProblem('缺少导入批次。')
                    self.send(store.remove_batch(batch))
                else:
                    self.send({'error': '操作不存在。'}, 404)
            except (ImportProblem, ValueError, TypeError, UnicodeError, binascii.Error) as error:
                self.send({'error': str(error)}, 400)
            except KeyError as error:
                self.send({'error': error.args[0]}, 404)
            except (OSError, sqlite3.Error):
                self.send({'error': '保存失败；请检查数据目录及可用空间。'}, 500)

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / '.local' / 'continuity')
    parser.add_argument('--port', type=int, default=0, help='0 chooses a free local port')
    parser.add_argument('--open', action='store_true', help='Open the local browser')
    args = parser.parse_args()
    server = make_server(args.data_dir, args.port)
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'Continuity P1-A: {url}\n仅本机 · 无模型 · Ctrl+C 停止', flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
