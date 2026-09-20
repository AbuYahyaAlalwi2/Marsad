"""
وكيل الجمع — جمع البيانات تلقائياً
"""
import time
from db import log_event
from collect.multi_platform import collector
from collect.datasets import dataset_collector


class CollectorAgent:
    """
    جمع البيانات من كل المنصات
    """

    def __init__(self):
        log_event("collector_agent", {"status": "initialized"})

    def collect(self, query: str) -> dict:
        """جمع بيانات حسب استعلام"""
        try:
            # جمع الأكواد
            code_results = collector.collect_all(query, limit=50)

            # جمع datasets
            dataset_results = dataset_collector.collect_all(query, limit_per_platform=10)

            total_items = sum(
                r.get("items", 0) if isinstance(r, dict) else 0
                for r in code_results.values()
            )

            log_event("collector_agent", {
                "query": query,
                "items": total_items,
                "platforms": len(code_results)
            })

            return {
                "status": "success",
                "items": total_items,
                "code_results": code_results,
                "dataset_results": dataset_results
            }

        except Exception as e:
            log_event("collector_agent_errors", {"error": str(e)})
            return {"status": "error", "error": str(e)}

    def collect_security(self) -> dict:
        """جمع بيانات أمنية"""
        queries = [
            "CVE-2024 exploit",
            "OWASP Top 10 vulnerability",
            "penetration testing tool",
            "security patch",
            "malware analysis"
        ]

        results = []
        for query in queries:
            result = self.collect(query)
            results.append(result)
            time.sleep(2)

        return {
            "status": "success",
            "queries": len(queries),
            "results": results
        }

    def collect_code(self, language: str = "python") -> dict:
        """جمع أكواد برمجية"""
        queries = [
            f"{language} algorithm implementation",
            f"{language} best practices",
            f"{language} optimization techniques",
            f"{language} design patterns"
        ]

        results = []
        for query in queries:
            result = self.collect(query)
            results.append(result)
            time.sleep(2)

        return {
            "status": "success",
            "language": language,
            "queries": len(queries),
            "results": results
        }


# نسخة عامة
collector_agent = CollectorAgent()
