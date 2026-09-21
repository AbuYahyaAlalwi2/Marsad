"""
CYBERGUARD OS - Platforms Registry
27 platforms classified by: free tier, credit card, API support, VPS capability.
"""

PLATFORMS = [
    # ============ الفئة A: بدون بطاقة ============
    {"name": "cloudflare", "country": "US", "type": "Edge/Serverless",
     "free": True, "no_card": True, "api": True, "vps": False,
     "limits": "100K req/day, 512MB", "note": "Workers/Pages/D1/R2"},
    {"name": "vercel", "country": "US", "type": "PaaS/Serverless",
     "free": True, "no_card": True, "api": True, "vps": False,
     "limits": "100GB BW/month", "note": "للاستخدام الشخصي فقط"},
    {"name": "netlify", "country": "US", "type": "PaaS/Serverless",
     "free": True, "no_card": True, "api": True, "vps": False,
     "limits": "300 credits/month", "note": "~15GB bandwidth"},
    {"name": "render", "country": "US", "type": "PaaS",
     "free": True, "no_card": True, "api": True, "vps": False,
     "limits": "750h + 512MB", "note": "ينام بعد 15 دقيقة"},
    {"name": "supabase", "country": "US", "type": "Backend/DB",
     "free": True, "no_card": True, "api": True, "vps": False,
     "limits": "500MB DB, 2GB BW", "note": "ينام بعد أسبوع"},
    {"name": "deno_deploy", "country": "US", "type": "Edge/Serverless",
     "free": True, "no_card": True, "api": True, "vps": False,
     "limits": "1M req/month", "note": "100 GiB egress"},
    {"name": "firebase", "country": "US", "type": "Backend/Cloud",
     "free": True, "no_card": True, "api": True, "vps": False,
     "limits": "10GB/month", "note": "Spark plan"},
    {"name": "github_pages", "country": "US", "type": "Static hosting",
     "free": True, "no_card": True, "api": True, "vps": False,
     "limits": "1GB storage", "note": "للمواقع الثابتة فقط"},
    {"name": "ibm_cloud", "country": "US", "type": "Cloud",
     "free": True, "no_card": True, "api": True, "vps": False,
     "limits": "Lite plan دائم", "note": "بدون بطاقة"},
    {"name": "koyeb", "country": "FR", "type": "PaaS",
     "free": True, "no_card": True, "api": True, "vps": False,
     "limits": "512MB RAM, 2GB SSD", "note": "بدون بطاقة"},
    
    # ============ الفئة B: بطاقة للتحقق ============
    {"name": "oracle_cloud", "country": "US", "type": "Cloud/VPS",
     "free": True, "no_card": False, "api": True, "vps": True,
     "limits": "2 VMs Always Free", "note": "أقوى عرض مجاني"},
    {"name": "google_cloud", "country": "US", "type": "Cloud/VPS",
     "free": True, "no_card": False, "api": True, "vps": True,
     "limits": "$300 trial", "note": "بطاقة إلزامية"},
    {"name": "aws", "country": "US", "type": "Cloud/VPS",
     "free": True, "no_card": False, "api": True, "vps": True,
     "limits": "12-month free", "note": "بطاقة إلزامية"},
    {"name": "azure", "country": "US", "type": "Cloud/VPS",
     "free": True, "no_card": False, "api": True, "vps": True,
     "limits": "$200 credit", "note": "بطاقة إلزامية"},
    {"name": "alibaba_cloud", "country": "CN", "type": "Cloud/VPS",
     "free": True, "no_card": False, "api": True, "vps": True,
     "limits": "Trial", "note": "بطاقة إلزامية"},
    {"name": "tencent_cloud", "country": "CN", "type": "Cloud/VPS",
     "free": True, "no_card": False, "api": True, "vps": True,
     "limits": "Trial", "note": "تحقق إضافي"},
    {"name": "digitalocean", "country": "US", "type": "Cloud/VPS",
     "free": True, "no_card": False, "api": True, "vps": True,
     "limits": "$200 trial", "note": "بطاقة إلزامية"},
    {"name": "linode", "country": "US", "type": "Cloud/VPS",
     "free": True, "no_card": False, "api": True, "vps": True,
     "limits": "$100 trial", "note": "بطاقة إلزامية"},
    {"name": "northflank", "country": "UK", "type": "PaaS",
     "free": True, "no_card": False, "api": True, "vps": False,
     "limits": "Sandbox", "note": "بطاقة + KYC"},
    
    # ============ الفئة C: مدفوعة ============
    {"name": "hetzner", "country": "DE", "type": "Cloud/VPS",
     "free": False, "no_card": False, "api": True, "vps": True,
     "limits": "رخيص فقط", "note": "لا free tier"},
    {"name": "scaleway", "country": "FR", "type": "Cloud",
     "free": True, "no_card": False, "api": True, "vps": True,
     "limits": "محدود جداً", "note": "750GB لـ 90 يوم"},
    {"name": "clever_cloud", "country": "FR", "type": "PaaS",
     "free": False, "no_card": False, "api": True, "vps": False,
     "limits": "لا free tier", "note": "مدفوع"},
    {"name": "blitz_cloud", "country": "DE", "type": "Cloud/PaaS",
     "free": False, "no_card": False, "api": True, "vps": False,
     "limits": "لا free tier", "note": "مدفوع من اليوم الأول"},
]


def list_no_card():
    """Platforms that don't require credit card."""
    return [p for p in PLATFORMS if p["no_card"]]


def list_free():
    """Platforms with free tier."""
    return [p for p in PLATFORMS if p["free"]]


def list_with_api():
    """Platforms with API support."""
    return [p for p in PLATFORMS if p["api"]]


def list_vps():
    """Platforms offering real VPS."""
    return [p for p in PLATFORMS if p["vps"]]


def summary():
    return {
        "total": len(PLATFORMS),
        "no_card": len(list_no_card()),
        "free": len(list_free()),
        "with_api": len(list_with_api()),
        "vps": len(list_vps()),
        "by_category": {
            "A_no_card": [p["name"] for p in list_no_card()],
            "B_card_required": [p["name"] for p in PLATFORMS
                                if not p["no_card"] and p["free"]],
            "C_paid": [p["name"] for p in PLATFORMS if not p["free"]],
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(summary(), indent=2, ensure_ascii=False))
