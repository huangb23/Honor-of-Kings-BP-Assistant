#!/usr/bin/env bash
# 启动 BP 器（Mac / Linux）
# 用法: 在项目根目录 ./start.sh  或  bash start.sh
set -e

# 切到脚本所在目录（项目根目录），保证相对路径正确
cd "$(dirname "$0")"

PORT="${1:-8000}"

# 默认使用系统 python（不依赖 venv）
if command -v python3 >/dev/null 2>&1; then
    PY="python3"
elif command -v python >/dev/null 2>&1; then
    PY="python"
else
    echo "❌ 找不到 Python 3，请先安装 Python 3 并执行: pip install -r requirements.txt"
    exit 1
fi

echo "使用解释器: $PY"
echo "启动 BP 服务端口: $PORT"
echo "浏览器打开: http://localhost:$PORT/index.html"
exec "$PY" -u backend/server.py "$PORT"