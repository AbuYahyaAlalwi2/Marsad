import re
from pathlib import Path
FILE = Path.home() / ".marsad_secrets" / "all.env"

print("=== المفاتيح الجديدة ===")
found = {}
for line in FILE.read_text().splitlines():
    for k in ("OPENROUTER_API_KEY", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_EMAIL", "CLOUDFLARE_GLOBAL_KEY"):
        if line.startswith(k + "="):
            found[k] = len(line.split("=", 1)[1])

for k in ("OPENROUTER_API_KEY", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_EMAIL", "CLOUDFLARE_GLOBAL_KEY"):
    v = found.get(k)
    print(f"  {'✓' if v else '✗'} {k:28s} {'موجود (' + str(v) + ' حرف)' if v else 'غير موجود'}")
