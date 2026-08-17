# -*- coding: utf-8 -*-
"""
英雄胜率爬虫：抓取多个分段的胜率（gameMode: 1=全分段, 3=1350+, 4=顶端排位, 6=巅峰千强近5日）。

来源：https://tianyuanzhiyi.com/api/herostats?date=YYYY-MM-DD&gameMode={mode}
  - 每天只更新前一天数据，因此优先用"昨天"，若当天接口已就绪则用当天。
  - 每个分段分别抓取；英雄在某分段缺胜率时用 45 兜底，保证与名册/组合英雄数一致。

大众分段聚合胜率：popular = (mode1*0.5 + mode3*1 + mode4*1 + mode6*0.5) / 3

输出：backend/data/hero_winrate.json
    {
      "fetched_at": "2026-08-16",
      "dates": ["2026-08-15"],
      "modes": [1, 3, 4, 6],
      "heroes": { "廉颇": {"m1": 50.1, "m3": 48.2, "m4": 47.0, "m6": 44.95}, ... }
    }

用法：python3 -u winrate_crawler.py
"""
import os
import json
import datetime
import requests

from config import (BASE_URL, HEADERS, WINRATE_GAME_MODES, DATA_DIR, WINRATE_FILE)


def fetch_mode(session, date_str, mode):
    """抓取某天某 gameMode 的每英雄胜率，返回 {heroName: winRate}。"""
    url = f"{BASE_URL}/api/herostats?date={date_str}&gameMode={mode}"
    r = session.get(url, timeout=25)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        return {}
    return {item["heroName"]: item.get("winRate") for item in data}


def collect():
    session = requests.Session()
    session.headers.update(HEADERS)

    today = datetime.date.today()
    # 每天只更新前一天数据，优先从昨天开始；若昨天尚未出数据则继续回退更早
    for back in range(1, 8):
        ds = (today - datetime.timedelta(days=back)).isoformat()
        per_mode = {}
        ok = True
        for mode in WINRATE_GAME_MODES:
            try:
                day_map = fetch_mode(session, ds, mode)
            except Exception as e:
                print(f"⚠️ {ds} mode={mode} 抓取失败: {e}")
                day_map = {}
            if not day_map:
                print(f"⚠️ {ds} mode={mode} 返回为空")
                ok = False
                break
            per_mode[mode] = day_map
        if ok:
            # 汇总每个英雄各分段胜率，缺失分段用 45 兜底
            all_heroes = set()
            for mp in per_mode.values():
                all_heroes |= set(mp.keys())
            heroes = {}
            for h in all_heroes:
                entry = {}
                for mode in WINRATE_GAME_MODES:
                    wr = per_mode.get(mode, {}).get(h)
                    entry[f"m{mode}"] = round(wr if wr is not None else 45.0, 4)
                heroes[h] = entry
            os.makedirs(DATA_DIR, exist_ok=True)
            path = os.path.join(DATA_DIR, WINRATE_FILE)
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "fetched_at": today.isoformat(),
                    "dates": [ds],
                    "modes": WINRATE_GAME_MODES,
                    "heroes": heroes,
                }, f, ensure_ascii=False, indent=2)
            print(f"✅ 胜率已保存: {path}，共 {len(heroes)} 个英雄，来源日期 {ds}，分段 {WINRATE_GAME_MODES}")
            return path

    raise RuntimeError("近几日均未抓到英雄胜率数据。")


def load():
    """读取已保存的多分段胜率，返回 {hero: {mode_key: winRate}}（mode_key 如 'm1'/'m3'/'m4'/'m6'）。
    每天新增前一天数据 → 若文件不存在或 fetched_at 不是今天，则重新拉取。"""
    path = os.path.join(DATA_DIR, WINRATE_FILE)
    if not os.path.exists(path):
        collect()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("fetched_at") != datetime.date.today().isoformat():
        print("⚠️ 胜率数据非今日，重新拉取...")
        collect()
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

    heroes = data.get("heroes", {})
    # 兼容旧结构：旧版为 {hero: {"winRate": x}}，此时视为只有 mode6
    out = {}
    for h, v in heroes.items():
        if isinstance(v, dict) and any(k.startswith("m") for k in v):
            out[h] = v
        else:
            wr = v.get("winRate") if isinstance(v, dict) else v
            out[h] = {"m6": round(wr if wr is not None else 45.0, 4)}
    return out


def winrate_for_mode(modes_map, mode="dianfeng"):
    """把多分段胜率 map 转成单胜率 map {hero: winRate}。

    mode:
      'dianfeng' -> 巅峰千强，使用 m6
      'dazhong'  -> 大众分段，聚合 (m1*0.5 + m3 + m4 + m6*0.5) / 3
    缺失分段按 45 兜底。
    """
    from config import POPULAR_WEIGHTS, POPULAR_DIVISOR
    out = {}
    for h, entry in modes_map.items():
        if mode == "dazhong":
            s = 0.0
            n = 0
            for mk, w in POPULAR_WEIGHTS.items():
                wr = entry.get(f"m{mk}")
                if wr is not None:
                    s += wr * w
                    n += 1
            val = s / POPULAR_DIVISOR if n > 0 else 45.0
        else:  # dianfeng（及默认）
            val = entry.get("m6", 45.0)
        out[h] = round(val, 4)
    return out


if __name__ == "__main__":
    collect()