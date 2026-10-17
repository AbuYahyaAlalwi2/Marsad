import concurrent.futures as cf
import httpx

# التصحيح: (subdomain, worker_name_prefix)
ACCOUNTS = [
    ("marsad-8a059168ac", 1),    # cf_1 → marsad-1-*
    ("yahya1990alalwi",   2),    # cf_2 → marsad-2-*
    ("marsad-8dd6a57a72", 3),    # cf_3 → marsad-3-*
    ("amjdalalwi2000",    4),    # primary → marsad-4-*
    ("www-technique2030", 5),    # cf_5 → marsad-5-*
]

def check(sub, idx, w):
    url = f"https://marsad-{idx}-{w}.{sub}.workers.dev/status"
    try:
        r = httpx.get(url, timeout=8)
        if r.status_code == 200:
            return {"ok": True, "url": url, "region": r.json().get("region", "?")}
        return {"ok": False, "url": url, "code": r.status_code}
    except Exception as e:
        return {"ok": False, "url": url, "err": str(e)[:40]}

def main():
    print("=" * 60)
    print("  التحقق من 500,000 وكيل — بالأسماء الصحيحة")
    print("=" * 60)
    tasks = [(sub, idx, w) for sub, idx in ACCOUNTS for w in range(1, 11)]
    alive, dead, regions = 0, 0, {}
    with cf.ThreadPoolExecutor(max_workers=20) as ex:
        futs = {ex.submit(check, s, i, w): (s, i, w) for s, i, w in tasks}
        for f in cf.as_completed(futs):
            s, i, w = futs[f]
            r = f.result()
            if r["ok"]:
                alive += 1
                regions[r["region"]] = regions.get(r["region"], 0) + 1
                print(f"  OK  marsad-{i}-{w}.{s[:20]}  ->  {r['region']}")
            else:
                dead += 1
                print(f"  XX  marsad-{i}-{w}.{s[:20]}  ->  {r.get('code', r.get('err'))}")
    print()
    print("=" * 60)
    print(f"  Workers حية: {alive}/{alive+dead}")
    print(f"  الوكلاء الفعليون: {alive * 10_000:,}")
    print("=" * 60)

if __name__ == "__main__":
    main()
