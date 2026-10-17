import re
from pathlib import Path
FILE = Path.home() / ".marsad_secrets" / "all.env"

print("=== مفاتيح Cloudflare في all.env ===")
for line in FILE.read_text().splitlines():
    for k in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_API_TOKEN_2",
              "CLOUDFLARE_EMAIL", "CLOUDFLARE_GLOBAL_KEY",
              "CF_TOKEN_1", "CF_TOKEN_2", "CF_TOKEN_3", "CF_TOKEN_4", "CF_TOKEN_5",
              "CF_ACCOUNT_1", "CF_ACCOUNT_2", "CF_ACCOUNT_3", "CF_ACCOUNT_4", "CF_ACCOUNT_5"):
        if line.startswith(k + "="):
            v = line.split("=", 1)[1]
            print(f"  ✓ {k:28s} ({len(v)} حرف)")
