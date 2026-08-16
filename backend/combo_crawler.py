# -*- coding: utf-8 -*-
"""
组合优势爬虫：抓取每个英雄的协同/克制指数（/api/hero/analysis?heroId={id}）。

规则：
  - 汇总成一份 backend/data/combo_advantage.json 保存。
  - 若 combo_advantage.json 存在且其抓取时间距现在 < COMBO_MAX_AGE_DAYS 天，则直接复用，不重新爬。
  - 否则按英雄名册里的全部英雄重新抓取。

输出结构：
    {
      "fetched_at": "2026-08-16",
      "combo": {
        "廉颇": { "synergy": { "队友A": 8.09, ... }, "counter": { "英雄X": 15.9, ... } },
        ...
      }
    }

用法：.venv/bin/python -u combo_crawler.py
"""
import os
import json
import time
import datetime
import requests

from config import (BASE_URL, HEADERS, HERO_ANALYSIS_API, DATA_DIR,
                    COMBO_FILE, COMBO_MAX_AGE_DAYS, REGISTRY_FILE,
                    WINRATE_GAME_MODE)


def combo_path():
    return os.path.join(DATA_DIR, COMBO_FILE)


def combo_age_days():
    """返回 combo 数据距今的天数；缺失/无日期则返回无穷大。"""
    path = combo_path()
    if not os.path.exists(path):
        return float("inf")
    try:
        with open(path, encoding="utf-8") as f:
            fetched = json.load(f).get("fetched_at")
    except Exception:
        return float("inf")
    if not fetched:
        return float("inf")
    try:
        d = datetime.date.fromisoformat(fetched)
    except ValueError:
        return float("inf")
    return (datetime.date.today() - d).days


def refresh_needed():
    """超过 COMBO_MAX_AGE_DAYS 天（或不存在）则需重新爬取。"""
    return combo_age_days() >= COMBO_MAX_AGE_DAYS


def load_hero_registry():
    """返回完整英雄名册 dict[heroName] = {"id": str, "roles": [..]}。
    优先从站点 herostats 接口拉最新全量（含新英雄），失败才回退旧 1.json。"""
    reg_path = os.path.join(DATA_DIR, REGISTRY_FILE)

    # 0) 本地缓存若为今天抓取，直接复用（避免每次启动都请求站点）
    if os.path.exists(reg_path):
        try:
            with open(reg_path, encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("fetched_at") == datetime.date.today().isoformat() and "registry" in cached:
                print("♻️  使用今日英雄名册缓存")
                return cached["registry"]
        except Exception:
            pass

    # 1) 尝试从站点拉最新全量英雄（herostats 返回所有英雄的 heroId/roles）
    #    每天只更新前一天数据 → 优先从昨天开始，再回退更早
    session = requests.Session()
    session.headers.update(HEADERS)
    today = datetime.date.today()
    registry = {}
    for back in range(1, 8):  # 从昨天(1)开始，回退到 7 天前
        ds = (today - datetime.timedelta(days=back)).isoformat()
        try:
            url = f"{BASE_URL}/api/herostats?date={ds}&gameMode={WINRATE_GAME_MODE}"
            r = session.get(url, timeout=25)
            r.raise_for_status()
            data = r.json()
            if not (isinstance(data, list) and data):
                continue
            for it in data:
                name = it.get("heroName")
                if not name:
                    continue
                roles = [x.strip() for x in str(it.get("roles", "")).split("/") if x.strip()]
                registry[name] = {"id": str(it.get("heroId")), "roles": roles}
            print(f"✅ 已从站点拉取最新英雄名册（日期 {ds}），共 {len(registry)} 个英雄")
            break
        except Exception as e:
            print(f"⚠️ {ds} 拉取英雄名册失败: {e}")
    if registry:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(reg_path, "w", encoding="utf-8") as f:
            json.dump({"registry": registry,
                       "fetched_at": datetime.date.today().isoformat()},
                      f, ensure_ascii=False, indent=2)
        return registry

    # 2) 回退：本地缓存
    if os.path.exists(reg_path):
        with open(reg_path, encoding="utf-8") as f:
            reg = json.load(f)
        if "registry" in reg:
            print("♻️  使用本地缓存的英雄名册")
            return reg["registry"]

    # 3) 最后回退：旧 1.json（可能不全）
    fallback = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "training", "data", "1.json")
    with open(fallback, encoding="utf-8") as f:
        items = json.load(f)
    registry = {it["name"]: {"id": str(it["id"]),
                             "roles": [x.strip() for x in str(it.get("roles", "")).split("/") if x.strip()]}
                for it in items}
    return registry


def fetch_one(session, hero_id):
    """抓取单个英雄的分析，返回 {synergy: {...}, counter: {...}}。"""
    url = f"{BASE_URL}{HERO_ANALYSIS_API}?heroId={hero_id}"
    r = session.get(url, timeout=20)
    r.raise_for_status()
    d = r.json()

    synergy = {}
    for it in d.get("goodSynergies", []) + d.get("badSynergies", []):
        synergy[it["heroName"]] = it.get("synergyIndex", 0.0)

    counter = {}
    for it in d.get("counters", []) + d.get("counteredBy", []):
        counter[it["heroName"]] = it.get("advantageIndex", 0.0)

    return {"synergy": synergy, "counter": counter}


def collect(force=False):
    """抓取并保存组合优势；force=True 则无视过期强制重爬。"""
    if not force and not refresh_needed():
        print(f"♻️  组合优势未过期，复用: {combo_path()}")
        return combo_path()

    reg = load_hero_registry()
    session = requests.Session()
    session.headers.update(HEADERS)

    combo = {}
    failed = 0
    for name, info in reg.items():
        hero_id = info["id"]
        try:
            combo[name] = fetch_one(session, hero_id)
            time.sleep(0.3)
        except Exception as e:
            failed += 1
            print(f"⚠️ {name}({hero_id}) 抓取失败: {e}")
            if failed >= 20:
                print("⚠️ 失败过多，提前停止。")
                break

    os.makedirs(DATA_DIR, exist_ok=True)
    path = combo_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "fetched_at": datetime.date.today().isoformat(),
            "combo": combo,
        }, f, ensure_ascii=False, indent=2)

    print(f"✅ 组合优势已保存: {path}，共 {len(combo)} 个英雄，失败 {failed}")
    return path


def load_combo():
    """读取组合优势；过期则重新爬取。返回 {hero: {synergy, counter}}。"""
    if refresh_needed():
        collect()
    with open(combo_path(), encoding="utf-8") as f:
        data = json.load(f)
    return data["combo"]


if __name__ == "__main__":
    collect(force=False)