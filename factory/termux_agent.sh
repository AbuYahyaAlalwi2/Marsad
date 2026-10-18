#!/data/data/com.termux/files/usr/bin/bash
# مسار تعدين من الهاتف: يكمل بعد انقطاع الإنترنت (الصندوق الصادر + انتظار الشبكة) ويُعاد تشغيله تلقائياً إن سقط.
# الاستعمال:  bash termux_agent.sh      (للتشغيل بعد إغلاق الجلسة:  nohup bash termux_agent.sh > ~/marsad_agent.log 2>&1 &)
cd "$(dirname "$0")" || exit 1
pkg install -y python git gh uv >/dev/null 2>&1 || pip install uv
python -c "import huggingface_hub" 2>/dev/null || pip install -q huggingface_hub
termux-wake-lock 2>/dev/null
set -a; . "$HOME/.marsad_secrets/all.env"; set +a
export GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
export WORK_DIR="$HOME/marsad_work" HOST_NAME=termux SHARD="${SHARD:-1/2}" WORKERS=1 BATCH=2 PORT=0 UV_PYTHON_DOWNLOADS=never LLM_SITES="${LLM_SITES:-40}"
mkdir -p "$WORK_DIR"
[ -n "$HF_TOKEN" ] && [ -n "$GH_TOKEN" ] || { echo "HF_TOKEN/GH_TOKEN مفقودان في all.env"; exit 1; }
while true; do
  python marsad_factory_daemon_v5.py
  echo "$(date +%T) daemon exited; restart in 20s"; sleep 20
done
