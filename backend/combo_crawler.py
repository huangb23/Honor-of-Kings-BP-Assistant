# -*- coding: utf-8 -*-
"""
组合优势爬虫：抓取每个英雄的协同/克制指数（/api/hero/analysis?heroId={id}）。

规则（每日更新）：
  - 汇总成一份 backend/data/combo_advantage.json 保存。
  - combo_advantage.json 非今日抓取则自动重新爬取（与胜率爬虫的每日刷新对齐）。
  - 站点数据每天更新（totalMatches/指数随对局增长），过期数据会低估关系强度。
  - 抓取失败的英雄从旧数据回填；仅当全部英雄抓取成功才把 fetched_at 记为今天，
    否则沿用旧日期、下次启动自动重试（当前运行使用合并后的最优数据）。

输出结构：
    {
      "fetched_at": "2026-09-04",
      "combo": {
        "廉颇": { "synergy": { "队友A": {"idx": 8.09, "m": 1024}, ... },
                  "counter": { "英雄X": {"idx": 15.9, "m": 512}, ... } },
        ...
      }
    }

用法：python3 -u combo_crawler.py
"""
import os
import json
import time
import datetime
import requests

from config import (BASE_URL, HEADERS, HERO_ANALYSIS_API, DATA_DIR,
                    COMBO_FILE, COMBO_MAX_AGE_DAYS, REGISTRY_FILE,
                    WINRATE_GAME_MODES)


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
    """数据非今日（或不存在）则需重新爬取（每日更新）。"""
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
            url = f"{BASE_URL}/api/herostats?date={ds}&gameMode={WINRATE_GAME_MODES[0]}"
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
    """抓取单个英雄的分析，返回 {synergy: {...}, counter: {...}}。

    每个关系元素形如 {"idx": 指数, "m": totalMatches}：
      synergy: {对手: {"idx": synergyIndex, "m": totalMatches}}
      counter: {对手: {"idx": advantageIndex, "m": totalMatches}}
    totalMatches 供模型做频次过滤（如 min_m=50，低频关系视为不存在）。
    """
    url = f"{BASE_URL}{HERO_ANALYSIS_API}?heroId={hero_id}"
    r = session.get(url, timeout=20)
    r.raise_for_status()
    d = r.json()

    synergy = {}
    for it in d.get("goodSynergies", []) + d.get("badSynergies", []):
        synergy[it["heroName"]] = {
            "idx": it.get("synergyIndex", 0.0),
            "m": it.get("totalMatches", 0),
        }

    counter = {}
    for it in d.get("counters", []) + d.get("counteredBy", []):
        counter[it["heroName"]] = {
            "idx": it.get("advantageIndex", 0.0),
            "m": it.get("totalMatches", 0),
        }

    return {"synergy": synergy, "counter": counter}


def collect(force=False):
    """抓取并保存组合优势（每日更新）；force=True 则无视过期强制重爬。

    - 抓取失败的英雄从旧数据回填，保证合并后数据完整；
    - 仅当全部英雄抓取成功时才把 fetched_at 记为今天；
      否则沿用旧日期，下次启动自动重试（当前运行仍使用合并后的最优数据）。
    """
    if not force and not refresh_needed():
        print(f"♻️  组合优势今日已更新，复用: {combo_path()}")
        return combo_path()

    reg = load_hero_registry()

    # 旧数据（用于失败英雄回填与日期回退）
    old_combo, old_fetched = {}, None
    if os.path.exists(combo_path()):
        try:
            with open(combo_path(), encoding="utf-8") as f:
                old = json.load(f)
            old_combo, old_fetched = old.get("combo", {}), old.get("fetched_at")
        except Exception:
            old_combo, old_fetched = {}, None

    session = requests.Session()
    session.headers.update(HEADERS)

    combo, failed, missing404 = {}, [], []
    for name, info in reg.items():
        try:
            combo[name] = fetch_one(session, info["id"])
            time.sleep(0.3)
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status == 404:
                # 站点永久无此英雄分析页（如李信光/暗形态），视为正常缺失
                missing404.append(name)
                if old_combo.get(name):
                    combo[name] = old_combo[name]
            else:
                failed.append(name)
                print(f"⚠️ {name}({info['id']}) 抓取失败: {e}")
                if old_combo.get(name):
                    combo[name] = old_combo[name]
                if len(failed) >= 20:
                    print("⚠️ 失败过多，提前停止，其余英雄沿用旧数据。")
                    break
        except Exception as e:
            failed.append(name)
            print(f"⚠️ {name}({info['id']}) 抓取失败: {e}")
            if old_combo.get(name):
                combo[name] = old_combo[name]
            if len(failed) >= 20:
                print("⚠️ 失败过多，提前停止，其余英雄沿用旧数据。")
                break

    # 提前停止时，其余英雄从旧数据回填
    for name in reg:
        if name not in combo and old_combo.get(name):
            combo[name] = old_combo[name]

    # fetched_at：无暂时性失败（404 永久缺失不计入）→ 今天（当日不再重爬）；
    # 否则沿用旧日期，使 refresh_needed() 保持 True，下次启动自动重试
    today = datetime.date.today().isoformat()
    still_missing = [n for n in reg if not combo.get(n) and n not in missing404]
    if not failed and not still_missing:
        fetched_at = today
    else:
        fetched_at = old_fetched or (datetime.date.today()
                                     - datetime.timedelta(days=COMBO_MAX_AGE_DAYS)).isoformat()

    os.makedirs(DATA_DIR, exist_ok=True)
    path = combo_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "fetched_at": fetched_at,
            "combo": combo,
        }, f, ensure_ascii=False, indent=2)

    print(f"✅ 组合优势已保存: {path}，共 {len(combo)} 个英雄，失败 {len(failed)}，"
          f"站点无分析页 {len(missing404)}"
          + ("（已回填旧数据，下次启动重试）" if failed or still_missing else ""))
    return path


def load_combo():
    """读取组合优势；数据非今日则自动重爬（每日更新）。

    重爬失败时回退本地缓存（保证服务可用），下次启动自动重试。
    返回 {hero: {synergy, counter}}。
    """
    if refresh_needed():
        try:
            collect()
        except Exception as e:
            if not os.path.exists(combo_path()):
                raise
            print(f"⚠️ 组合优势每日更新失败，本次使用本地缓存: {e}")
    with open(combo_path(), encoding="utf-8") as f:
        data = json.load(f)
    return data["combo"]


if __name__ == "__main__":
    collect(force=False)