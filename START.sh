#!/bin/bash
cd "$(dirname "$0")"
mkdir -p data models datasets
export CG_DB_PATH="$(pwd)/data/cyberguard.db"
export CG_AUTORUN_INTERVAL="${CG_AUTORUN_INTERVAL:-300}"

echo "========================================"
echo "  CYBERGUARD OS — One Button Start"
echo "========================================"

# install minimal if missing
python3 -c "import streamlit" 2>/dev/null || pip install -q streamlit requests plotly pandas 2>/dev/null
python3 -c "import playwright" 2>/dev/null || pip install -q playwright 2>/dev/null

# init db
python3 -c "from db import _ensure_db; _ensure_db(); print('[+] DB ready')"

# start autorun in background
nohup python3 autorun.py >> data/autorun.log 2>&1 &
echo $! > data/autorun.pid
echo "[+] Autorun PID $(cat data/autorun.pid)"

# start dashboard
echo "[+] Launching Dashboard on http://0.0.0.0:8501"
exec streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
