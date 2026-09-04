# -*- coding: utf-8 -*-
"""
生成英雄拼音映射，保存到 data/hero_pinyin.json。
用 pypinyin（需要 pip install pypinyin）。
用法：python3 -u gen_pinyin.py
"""
import os
import json

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from main import load_roles  # noqa: E402
from pypinyin import lazy_pinyin, Style  # noqa: E402

# 多音字/特殊读音人工修正（pypinyin 无法识别游戏英雄名的官方读音）
# 键 = 英雄名，值 = 拼音音节列表（覆盖 pypinyin 的结果）
MANUAL_PINYIN = {
    "伽罗": ["jia", "luo"],   # 伽为多音字(gā/jiā/qié)，英雄名读 Jiāluó
    "刘禅": ["liu", "shan"],  # 禅为多音字(chán/shàn)，刘禅读 Liú Shàn
}


def build():
    roles = load_roles()
    out = {}
    for n in roles:
        syllables = MANUAL_PINYIN.get(n) or lazy_pinyin(n, style=Style.NORMAL)
        full = ''.join(syllables)
        initial = ''.join(s[0] for s in syllables)
        out[n] = {"pinyin": full, "initial": initial}
    os.makedirs('data', exist_ok=True)
    with open('data/hero_pinyin.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"已生成拼音映射: {len(out)} 个英雄 -> data/hero_pinyin.json")
    return out


if __name__ == '__main__':
    build()