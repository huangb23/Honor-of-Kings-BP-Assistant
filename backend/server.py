# -*- coding: utf-8 -*-
"""
BP 预测 API 服务（零依赖，用标准库 http.server）。

接口：
  GET  /heroes           返回全部英雄及分路（供前端下拉框）
  GET  /api/leaderboard  ?mode=dianfeng|dazhong&top=10  胜率榜 + 日环比变动榜
  POST /predict          body: {"my": [...], "opp": [...], "ban": [...], "role": null}
                         返回: {base_win_rate, single_pick:{role:[...]}, double_pick:[...]}

用法：python3 -u server.py  [端口，默认 8000]
前端页面由 http.server 一并托管（static 目录）。
"""
import os
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from main import load_combo, load_roles
from config import DEFAULT_WINRATE_MODE
from winrate_crawler import load_with_prev, load_dates, winrate_for_mode
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


# 全局加载数据（多分段胜率 + 前一天胜率 + 组合 + 名册），按请求分段构建模型
print("📦 加载模型数据 ...")
_MODES_MAP, _MODES_PREV, _DATES = load_with_prev()   # 当日/前一日 {hero: {m1,m3,m4,m6}}
_COMBO = load_combo()
_ROLES = load_roles()
_PINYIN = _load_pinyin()
print(f"✅ 数据就绪，共 {len(_ROLES)} 个英雄，数据日期 {_DATES}")


def _engine_for_mode(mode):
    """按胜率分段构建模型与引擎。

    mode: 'dianfeng'=巅峰千强；'dazhong'=大众分段（csv 按克制数在 大众↔巅峰 间插值）。
    """
    mode = mode or DEFAULT_WINRATE_MODE
    df = winrate_for_mode(_MODES_MAP, "dianfeng")
    if mode == "dazhong":
        pk = winrate_for_mode(_MODES_MAP, "dazhong")
        model = WinRateModel(df, pk, _COMBO, mode="dazhong")
    else:
        model = WinRateModel(df, {}, _COMBO, mode="dianfeng")
    return BPEngine(model, _ROLES)


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
    top_k = int(body.get("top_k", 8))
    mode = body.get("mode") or DEFAULT_WINRATE_MODE  # dianfeng / dazhong

    engine = _engine_for_mode(mode)

    # 我方已占用位置：前端从 my_slots[] 取已选英雄的分路
    used_roles = set()
    for slot in (body.get("my_slots") or []):
        if slot.get("hero") and slot.get("role"):
            used_roles.add(slot["role"])

    base = engine.base_win_rate(my, opp)
    single = engine.single_pick_by_role(my, opp, ban, role=role, top_k=top_k)
    double = engine.suggest_double_pick(my, opp, ban, top_k=20, used_roles=used_roles)

    # 附上英雄自身胜率（按请求分段），供前端展示与着色
    own = winrate_for_mode(_MODES_MAP, mode)
    single = {r: [(h, w, own.get(h)) for h, w in items] for r, items in single.items()}
    double = [(pair, wr, (own.get(pair[0]), own.get(pair[1]))) for pair, wr in double]

    return {
        "base_win_rate": round(float(base), 4),
        "single_pick": single,
        "double_pick": double,
        "used_roles": sorted(used_roles),
        "mode": mode,
    }


def build_leaderboard(mode=None, top=10):
    """胜率排行榜 + 日环比变动榜（按请求分段）。

    返回: {mode, date, prev_date, winrate:[{name,wr,delta}], rise:[...], fall:[...]}
    无前一天数据时 delta 为 null，rise/fall 为空列表。
    """
    mode = mode or DEFAULT_WINRATE_MODE
    try:
        top = max(1, min(int(top), 50))
    except (TypeError, ValueError):
        top = 10

    cur = winrate_for_mode(_MODES_MAP, mode)     # {hero: winRate}
    prev = winrate_for_mode(_MODES_PREV, mode) if _MODES_PREV else {}

    rows = []
    for h, wr in cur.items():
        d = round(wr - prev[h], 2) if h in prev else None
        rows.append({"name": h, "wr": round(wr, 2), "delta": d})

    by_wr = sorted(rows, key=lambda x: -x["wr"])[:top]
    with_delta = [r for r in rows if r["delta"] is not None]
    rise = sorted(with_delta, key=lambda x: -x["delta"])[:top]
    fall = sorted(with_delta, key=lambda x: x["delta"])[:top]

    dates = _DATES or load_dates()
    return {
        "mode": mode,
        "date": dates[0] if dates else None,
        "prev_date": dates[1] if len(dates) > 1 else None,
        "winrate": by_wr,
        "rise": rise,
        "fall": fall,
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
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/heroes":
            self._send(200, {"heroes": build_hero_list()})
            return
        if path == "/api/leaderboard":
            qs = parse_qs(parsed.query)
            mode = (qs.get("mode") or [None])[0]
            top = (qs.get("top") or [10])[0]
            self._send(200, build_leaderboard(mode=mode, top=top))
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