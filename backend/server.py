# -*- coding: utf-8 -*-
"""
BP 预测 API 服务（零依赖，用标准库 http.server）。

接口：
  GET  /heroes           返回全部英雄及分路（供前端下拉框）
  POST /predict          body: {"my": [...], "opp": [...], "ban": [...], "role": null}
                         返回: {base_win_rate, single_pick:{role:[...]}, double_pick:[...]}

用法：../win_rate/.venv/bin/python -u server.py  [端口，默认 8000]
前端页面由 http.server 一并托管（static 目录）。
"""
import os
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from main import load_winrate, load_combo, load_roles
from model import WinRateModel
from engine import BPEngine

BASE = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE), 'frontend')

def _load_pinyin():
    """读取英雄拼音映射（data/hero_pinyin.json），缺失则尝试生成。"""
    p = os.path.join(BASE, 'data', 'hero_pinyin.json')
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    try:
        from gen_pinyin import build
        return build()
    except Exception as e:
        print(f"⚠️ 拼音映射不可用（前端拼音检索失效）: {e}")
        return {}


# 全局构建一次模型（数据缓存命中，加载很快）
print("📦 加载模型数据 ...")
_WR = load_winrate()
_COMBO = load_combo()
_ROLES = load_roles()
_PINYIN = _load_pinyin()
_MODEL = WinRateModel(_WR, _COMBO)
_ENGINE = BPEngine(_MODEL, _ROLES)
print(f"✅ 模型就绪，共 {len(_ROLES)} 个英雄")


def build_hero_list():
    """返回 [{name, roles:[...], pinyin, initial}]，用于前端选人。"""
    out = []
    for h, r in _ROLES.items():
        py = _PINYIN.get(h, {})
        out.append({"name": h, "roles": r,
                    "pinyin": py.get("pinyin", ""),
                    "initial": py.get("initial", "")})
    return out


def handle_predict(body):
    my = body.get("my") or []
    opp = body.get("opp") or []
    ban = body.get("ban") or []
    role = body.get("role")  # None 或分路名
    top_k = int(body.get("top_k", 5))

    # 我方已占用位置：前端传 my_slots=[{role, hero}, ...]，取已选英雄的分路
    used_roles = set()
    for slot in (body.get("my_slots") or []):
        if slot.get("hero") and slot.get("role"):
            used_roles.add(slot["role"])

    base = _ENGINE.base_win_rate(my, opp)
    single = _ENGINE.single_pick_by_role(my, opp, ban, role=role, top_k=top_k)
    double = _ENGINE.suggest_double_pick(my, opp, ban, top_k=20, used_roles=used_roles)
    return {
        "base_win_rate": round(float(base), 4),
        "single_pick": single,
        "double_pick": double,
        "used_roles": sorted(used_roles),
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj, ctype="application/json"):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/heroes":
            self._send(200, {"heroes": build_hero_list()})
            return
        # 静态文件
        if path == "/" or path == "":
            path = "/index.html"
        fp = os.path.join(FRONTEND_DIR, path.lstrip("/"))
        if os.path.isfile(fp):
            ctype = "text/html; charset=utf-8" if path.endswith(".html") else \
                "application/javascript; charset=utf-8" if path.endswith(".js") else \
                "text/css; charset=utf-8" if path.endswith(".css") else "application/octet-stream"
            with open(fp, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/predict":
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send(400, {"error": "invalid json"})
            return
        try:
            result = handle_predict(body)
            self._send(200, result)
        except Exception as e:
            self._send(500, {"error": str(e)})

    def log_message(self, *args):
        pass


def main():
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"✅ 前端目录: {FRONTEND_DIR}")
    print(f"🚀 BP 服务启动: http://localhost:{port}/index.html")
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()