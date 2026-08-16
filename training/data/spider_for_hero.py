import json
import time
from pathlib import Path
from tqdm import tqdm
import requests

# 输入文件
INPUT_FILE = "raw_data/1.json"

# 输出目录
OUTPUT_DIR = Path("raw_data/heroes")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

# 读取英雄列表
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    heroes = json.load(f)

session = requests.Session()
session.headers.update(HEADERS)

for hero in tqdm(heroes):
    hero_id = hero["id"]

    url = (
        f"https://tianyuanzhiyi.com/api/hero/analysis"
        f"?heroId={hero_id}"
    )

    try:
        print(f"Fetching hero {hero_id}...")

        resp = session.get(url, timeout=20)
        resp.raise_for_status()

        data = resp.json()

        output_file = OUTPUT_DIR / f"{hero_id}.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Saved -> {output_file}")

        # 防止请求过快
        time.sleep(0.5)

    except Exception as e:
        print(f"Failed hero {hero_id}: {e}")

print("Done.")