import re
import pandas as pd

# 1. 读取下载好的 HTML 网页文件
file_path = "data/数据 - 天元之弈数据站.htm"
with open(file_path, "r", encoding="utf-8") as f:
    html_content = f.read()

# 2. 编写正则表达式，精准匹配：英雄名称 与 后续连续的9项数据
# 匹配顺序为：英雄、胜率、出场率、输出占比、承伤占比、分均经济、拿牌率、前期胜率、中期胜率、后期胜率
pattern = (
    r'title="([^"]+)">\1</p>.*?'             # 匹配英雄名称
    r'text-\[20px\]">([^<]+)</span>.*?'      # 胜率
    r'text-\[20px\]">([^<]+)</span>.*?'      # 出场率
    r'text-\[20px\]">([^<]+)</span>.*?'      # 输出占比
    r'text-\[20px\]">([^<]+)</span>.*?'      # 承伤占比
    r'text-\[20px\]">([^<]+)</span>.*?'      # 分均经济
    r'text-\[20px\]">([^<]+)</span>.*?'      # 拿牌率
    r'text-\[20px\]">([^<]+)</span>.*?'      # 前期胜率
    r'text-\[20px\]">([^<]+)</span>.*?'      # 中期胜率
    r'text-\[20px\]">([^<]+)</span>'         # 后期胜率
)

# 3. 提取所有匹配到的英雄数据
matches = re.findall(pattern, html_content, re.DOTALL)

# 4. 转换为 DataFrame 格式并定义表头
columns = ['英雄', '胜率', '出场率', '输出占比', '承伤占比', '分均经济', '拿牌率', '前期胜率', '中期胜率', '后期胜率']
df = pd.DataFrame(matches, columns=columns)

# 5. 保存为 CSV 文件（使用 utf-8-sig 编码防止 Excel 打开时中文乱码）
output_file = "英雄属性数据.csv"
df.to_csv(output_file, index=False, encoding="utf-8-sig")

print(f"数据提取成功！共提取了 {len(df)} 位英雄的数据，已保存至: {output_file}")