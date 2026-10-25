"""Explicitly unconfigured subscription integration; never reuses host sign-in."""
def executable():
    raise ValueError('原型尚未配置独立 Codex 登录桥。不会读取此电脑现有的订阅登录。请先选择 API 模型。')

def probe():
    return {'ok': False, 'message': '订阅桥需要单独授权和配置；本原型不继承私人登录。'}

class Session:
    def generate(self, payload, cfg):
        executable()
    def close(self):
        pass
