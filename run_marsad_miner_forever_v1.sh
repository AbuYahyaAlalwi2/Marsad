#!/data/data/com.termux/files/usr/bin/bash
# يشغّل المنقّب بشكل مستمر، يعيد المحاولة لو انهار، ويسجّل كل شيء بوقت

cd ~/Marsad
LOG_DIR=~/Marsad/logs
mkdir -p "$LOG_DIR"

# يمنع الهاتف من النوم أثناء التشغيل (ضروري على Termux)
termux-wake-lock

RUN=1
trap "RUN=0" SIGINT SIGTERM

while [ "$RUN" -eq 1 ]; do
    TS=$(date "+%Y%m%d_%H%M%S")
    echo "[$TS] بدء دورة تشغيل جديدة للمنقّب" | tee -a "$LOG_DIR/miner_master.log"

    python3 historical_truth_miner_v1.py >> "$LOG_DIR/miner_${TS}.log" 2>&1
    EXIT_CODE=$?

    TS2=$(date "+%Y%m%d_%H%M%S")
    if [ $EXIT_CODE -eq 0 ]; then
        echo "[$TS2] المنقّب انتهى طبيعياً (exit 0) — إعادة تشغيل بعد 10 ثواني" | tee -a "$LOG_DIR/miner_master.log"
    else
        echo "[$TS2] المنقّب انهار (exit $EXIT_CODE) — إعادة تشغيل بعد 30 ثانية" | tee -a "$LOG_DIR/miner_master.log"
        sleep 20
    fi
    sleep 10
done

termux-wake-unlock
echo "تم إيقاف المنقّب نهائياً." | tee -a "$LOG_DIR/miner_master.log"
