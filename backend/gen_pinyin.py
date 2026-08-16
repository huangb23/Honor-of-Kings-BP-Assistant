# -*- coding: utf-8 -*-
"""
生成英雄拼音映射，保存到 data/hero_pinyin.json。
用 pypinyin（需要 pip install pypinyin）。
用法：../win_rate/.venv/bin/python -u gen_pinyin.py
"""
import os
import json

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from main import load_roles  # noqa: E402
from pypinyin import lazy_pinyin, Style  # noqa: E402


def build():
    roles = load_roles()
    out = {}
    for n in roles:
        full = ''.join(lazy_pinyin(n, style=Style.NORMAL))
        initial = ''.join(lazy_pinyin(n, style=Style.FIRST_LETTER))
        out[n] = {"pinyin": full, "initial": initial}
    os.makedirs('data', exist_ok=True)
    with open('data/hero_pinyin.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"已生成拼音映射: {len(out)} 个英雄 -> data/hero_pinyin.json")
    return out


if __name__ == '__main__':
    build()