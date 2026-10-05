#!/data/data/com.termux/files/usr/bin/bash
ROOT="$HOME/Marsad"
PIDF="$ROOT/logs/watchdog.pid"
LOGF="$ROOT/logs/runner.out"
mkdir -p "$ROOT/logs"

case "$1" in
  start)
    if [ -f "$PIDF" ] && kill -0 "$(cat $PIDF)" 2>/dev/null; then
      echo "already running: $(cat $PIDF)"; exit 0
    fi
    cd "$ROOT"
    setsid bash -c '
      while true; do
        python -m core.autonomous_runner
        echo "[watchdog] restart in 5s $(date +%H:%M:%S)"
        sleep 5
      done
    ' > "$LOGF" 2>&1 < /dev/null &
    echo $! > "$PIDF"
    echo "watchdog started pid=$(cat $PIDF)"
    ;;
  stop)
    if [ -f "$PIDF" ]; then
      PID=$(cat "$PIDF")
      pkill -P "$PID" 2>/dev/null
      kill "$PID" 2>/dev/null
      rm -f "$PIDF"
    fi
    pkill -f autonomous_runner 2>/dev/null
    echo "stopped"
    ;;
  status)
    if [ -f "$PIDF" ] && kill -0 "$(cat $PIDF)" 2>/dev/null; then
      echo "watchdog running pid=$(cat $PIDF)"
      echo "python procs: $(pgrep -f autonomous_runner | tr '\n' ' ')"
    else
      echo "stopped"
    fi
    ;;
  logs)
    tail -f "$LOGF"
    ;;
  *)
    echo "usage: bash run.sh {start|stop|status|logs}"
    ;;
esac
