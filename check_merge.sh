#!/data/data/com.termux/files/usr/bin/bash
# مراقبة تقدم مهمة صهر على Kaggle عبر Marsad

if [ -z "$1" ]; then
  echo "الاستخدام: ./check_merge.sh <kernel_slug>"
  echo "مثال: ./check_merge.sh marsad-merge-1790380497"
  exit 1
fi

SLUG="$1"
URL="https://marsad-dashboard.onrender.com/api/gpu/kaggle_status/${SLUG}"

echo "مراقبة: $SLUG"
echo "اضغط Ctrl+C للإيقاف يدويًا"
echo "----------------------------------------"

while true; do
  RESPONSE=$(curl -s --max-time 20 "$URL")

  STATUS=$(echo "$RESPONSE" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    inner = json.loads(d.get('status', '{}'))
    print(inner.get('status', 'UNKNOWN'))
except Exception:
    print('ERROR_PARSING')
")

  TIMESTAMP=$(date '+%H:%M:%S')
  echo "[$TIMESTAMP] الحالة: $STATUS"

  if [ "$STATUS" = "COMPLETE" ]; then
    echo "----------------------------------------"
    echo "✅ اكتمل الصهر بنجاح!"
    echo "$RESPONSE" | python3 -m json.tool
    break
  elif [ "$STATUS" = "ERROR" ]; then
    echo "----------------------------------------"
    echo "❌ فشلت المهمة."
    echo "$RESPONSE" | python3 -m json.tool
    break
  elif [ "$STATUS" = "ERROR_PARSING" ]; then
    echo "⚠️  تعذر قراءة الرد:"
    echo "$RESPONSE"
    break
  fi

  sleep 20
done
