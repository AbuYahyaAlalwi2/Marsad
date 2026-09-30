#!/data/data/com.termux/files/usr/bin/bash
ENV_FILE="$HOME/.marsad_secrets/render.env"
[ ! -f "$ENV_FILE" ] && { echo "missing"; exit 1; }

echo "◈ uploading $ENV_FILE"
count=0; skipped=0
while IFS= read -r line; do
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${line// }" ]] && continue
    [[ "$line" != *"="* ]] && continue

    key="${line%%=*}"
    key="${key// /}"
    value="${line#*=}"
    [ -z "$key" ] && continue
    [ -z "$value" ] && continue

    if printf '%s' "$value" | railway variable set "$key" --stdin --skip-deploys 2>/dev/null; then
        echo "  ok $key"
        count=$((count+1))
    else
        echo "  fail $key"
        skipped=$((skipped+1))
    fi
done < "$ENV_FILE"

echo ""
echo "uploaded: $count | failed: $skipped"
