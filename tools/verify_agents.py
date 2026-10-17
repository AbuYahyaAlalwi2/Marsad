import concurrent.futures as cf
import httpx

ACCOUNTS = [
    ("primary", "amjdalalwi2000"),
    ("cf_1",    "marsad-8a059168ac"),
    ("cf_2",    "yahya1990alalwi"),
    ("cf_3",    "marsad-8dd6a57a72"),
    ("cf_5",    "www-technique2030"),
]
WORKERS_PER_ACCOUNT = 10
AGENTS_PER_WORKER = 10_000

def check_worker(idx, worker_num, subdomain, name):
    url = f"https://marsad-{idx}-{worker_num}.{subdomain}.workers.dev/status"
    try:
        r = httpx.get(url, timeout=8, follow_redirects=True)
        if r.status_code == 200:
            d = r.json()
            return {"url": url, "ok": True, "region": d.get("region", "?")}
        return {"url": url, "ok": False, "code": r.status_code}
    except Exception as e:
        return {"url": url, "ok": False, "error": str(e)[:60]}

def main():
    print("=" * 60)
    print("  التحقق من 500,000 وكيل على Cloudflare")
    print("=" * 60)
    tasks = []
    for idx, (name, sub) in enumerate(ACCOUNTS, 1):
        for w in range(1, WORKERS_PER_ACCOUNT + 1):
            tasks.append((idx, w, sub, name))
    alive, dead, regions = 0, 0, {}
    with cf.ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(check_worker, i, w, s, n): (i, w, s, n)
                   for (i, w, s, n) in tasks}
        for f in cf.as_completed(futures):
            i, w, s, n = futures[f]
            r = f.result()
            if r["ok"]:
                alive += 1
                regions[r["region"]] = regions.get(r["region"], 0) + 1
                print(f"  OK  {n}/marsad-{i}-{w}  ->  {r['region']}")
            else:
                dead += 1
                print(f"  XX  {n}/marsad-{i}-{w}  ->  {r.get('code', r.get('error'))}")
    print()
    print("=" * 60)
    print(f"  Workers حية: {alive}/{alive + dead}")
    print(f"  الوكلاء الفعليون: {alive * AGENTS_PER_WORKER:,}")
    print(f"  المتوقعون: {len(tasks) * AGENTS_PER_WORKER:,}")
    print("  توزيع المناطق:")
    for reg, c in sorted(regions.items(), key=lambda x: -x[1]):
        print(f"    {reg}: {c}")
    print("=" * 60)

if __name__ == "__main__":
    main()
