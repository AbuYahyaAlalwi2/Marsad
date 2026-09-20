import requests, time
from db import log_event, insert_row

class RealCollector:
    def collect(self, query):
        results = {}
        total = 0
        try:
            resp = requests.get("https://api.stackexchange.com/2.3/questions", params={"order": "desc", "sort": "votes", "site": "stackoverflow", "tagged": query, "pagesize": 50}, timeout=15)
            items = resp.json().get("items", [])
            results["stackoverflow"] = len(items)
            total += len(items)
            for item in items[:10]:
                insert_row("collected_data", {"source": "stackoverflow", "content": item["title"], "created_at": time.time()})
        except: results["stackoverflow"] = 0
        try:
            resp = requests.get("https://api.github.com/search/repositories", params={"q": query, "sort": "stars", "per_page": 50}, timeout=15)
            items = resp.json().get("items", [])
            results["github"] = len(items)
            total += len(items)
        except: results["github"] = 0
        return {"total": total, "sources": results}

real_collector = RealCollector()
