#!/data/data/com.termux/files/usr/bin/bash
# اختبر مفاتيح Kaggle عبر API مباشرة

test_key() {
    local user="$1"
    local key="$2"
    local label="$3"
    
    local response=$(curl -s -u "$user:$key" \
        "https://www.kaggle.com/api/v1/datasets/list?page=1&pageSize=1" \
        -w "\n%{http_code}" --max-time 20)
    
    local code=$(echo "$response" | tail -1)
    local body=$(echo "$response" | head -n -1)
    
    if [ "$code" = "200" ]; then
        echo "$label ✅ يعمل ($user)"
        return 0
    else
        echo "$label ❌ فشل ($code)"
        echo "   $body" | head -c 200
        echo ""
        return 1
    fi
}

echo "── اختبار المفتاحين ──"
test_key "alwyabood68" "c4dffc8578d5262253b68b904d8b7543" "Account 1"
test_key "apwpkralalwwi" "aeb0ebc22d88545596d03719495992d2" "Account 2"
