"""Optional single-user HTTPS login. Local-only mode stays unchanged."""
import hashlib,hmac,json,os,secrets,time,urllib.parse
from http.cookies import SimpleCookie
from pathlib import Path
from collections import deque
ATTEMPTS=deque(maxlen=100)

def origin():
    value=os.environ.get('CONTINUITY_PUBLIC_ORIGIN','').rstrip('/')
    if value:
        u=urllib.parse.urlsplit(value)
        if u.scheme!='https' or not u.netloc or u.path or u.query or u.fragment or u.username:raise ValueError('云端地址必须是完整 HTTPS 域名。')
    return value

def password_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),600000).hex()

def initialize(api,db):
    db.execute('CREATE TABLE IF NOT EXISTS web_sessions(digest TEXT PRIMARY KEY,expires REAL)')

def password_path(api):return api.STATE/'login-password.hash'

def authenticated(api,handler):
    try:
        c=SimpleCookie();c.load(handler.headers.get('Cookie',''));token=c['__Host-continuity-session'].value
        if len(token)>150:return False
        with api.state_db() as db:r=db.execute('SELECT expires FROM web_sessions WHERE digest=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        return bool(r and r[0]>time.time())
    except (KeyError,ValueError):return False

def check_login(api,password):
    now=time.monotonic()
    while ATTEMPTS and ATTEMPTS[0]<now-300:ATTEMPTS.popleft()
    if len(ATTEMPTS)>=20:raise ValueError('尝试次数过多，请五分钟后再试。')
    ATTEMPTS.append(now)
    path=password_path(api)
    if not path.exists():raise ValueError('云端登录尚未配置。')
    expected=path.read_text().strip()
    if not isinstance(password,str) or len(password)>200 or not hmac.compare_digest(password_hash(password,expected.split(':')[0]),expected):raise ValueError('密码不正确。')
    token=secrets.token_urlsafe(32)
    with api.state_db() as db:
        db.execute('DELETE FROM web_sessions WHERE expires<?',(time.time(),))
        db.execute('INSERT INTO web_sessions VALUES(?,?)',(hashlib.sha256(token.encode()).hexdigest(),time.time()+30*86400))
    return token

def gate(api,h):
    """True means handled or denied; None leaves normal routing untouched."""
    public=origin()
    if not public:return False
    if h.headers.get('Host')!=urllib.parse.urlsplit(public).netloc:
        h.respond(403,{'error':'地址不匹配。'});return True
    path=urllib.parse.urlsplit(h.path).path
    if path=='/login' and h.command=='GET':
        return h.respond(200,(api.ROOT/'app/static/login.html').read_bytes(),'text/html; charset=utf-8') or True
    if path=='/login' and h.command=='POST':
        if h.headers.get('Origin')!=public:h.respond(403,{'error':'请从登录页面提交。'});return True
        try:
            length=int(h.headers.get('Content-Length','0'))
            if not 0<length<=2000:raise ValueError('输入无效。')
            fields=urllib.parse.parse_qs(h.rfile.read(length).decode())
            token=check_login(api,fields.get('password',[''])[0])
            h.send_response(303);h.send_header('Location','/');h.send_header('Cache-Control','no-store')
            h.send_header('Set-Cookie',f'__Host-continuity-session={token}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=2592000');h.send_header('Content-Length','0');h.end_headers()
        except ValueError as e:h.respond(403,{'error':str(e)})
        return True
    if not authenticated(api,h):
        if h.command=='GET' and path=='/':
            h.send_response(303);h.send_header('Location','/login');h.send_header('Cache-Control','no-store');h.send_header('Content-Length','0');h.end_headers()
        else:h.respond(401,{'error':'登录已过期，请重新打开首页登录。'})
        return True
    if path=='/logout' and h.command=='POST':
        if h.headers.get('Origin')!=public or not hmac.compare_digest(h.headers.get('X-Continuity-Token',''),api.TOKEN):
            h.respond(403,{'error':'请求无效。'});return True
        cookie=SimpleCookie();cookie.load(h.headers.get('Cookie',''))
        with api.state_db() as db:db.execute('DELETE FROM web_sessions WHERE digest=?',(hashlib.sha256(cookie['__Host-continuity-session'].value.encode()).hexdigest(),))
        h.send_response(200);h.send_header('Set-Cookie','__Host-continuity-session=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0');h.send_header('Cache-Control','no-store');h.send_header('Content-Length','0');h.end_headers();return True
    return False

def protect(api,raw,decrypt=False):
    # Linux key material belongs only to the service user. Ciphertexts are never sent to the browser.
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    path=api.STATE/'server-key.bin'
    if not path.exists():
        if decrypt:raise ValueError('服务器加密密钥缺失。')
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(secrets.token_bytes(32))
    cipher=AESGCM(path.read_bytes())
    if decrypt:
        if not raw.startswith(b'VK1'):raise ValueError('这份凭据属于 Windows，请在云端重新填写 API 密钥。')
        return cipher.decrypt(raw[3:15],raw[15:],b'Agent')
    nonce=secrets.token_bytes(12);return b'VK1'+nonce+cipher.encrypt(nonce,raw,b'Agent')
