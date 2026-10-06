"""اختبارات رسمية للمنسق عبر طلبات HTTP حقيقية (TestClient)."""
import json
import os
import tempfile
import unittest

os.environ["MARSAD_DATA_DIR"] = tempfile.mkdtemp()
from fastapi.testclient import TestClient
import adversarial_orchestrator as orch


def nvd_ok(cve):
    return {"vulnerabilities": [{"cve": {"id": cve, "vulnStatus": "Analyzed",
        "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 9.8}}]},
        "weaknesses": [{"description": [{"value": "CWE-89"}]}]}}]}


GOOD = {"nvd_published": True, "vulnerable_code": 'cursor.execute("SELECT * FROM t WHERE id=" + uid)',
       "exploit_code": "x", "patch_code": 'cursor.execute("SELECT * FROM t WHERE id=?", (uid,))'}


class OrchestratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        orch._nvd_fetch = nvd_ok
        cls.client = TestClient(orch.app)

    def test_accepts_valid_sample(self):
        s = dict(GOOD, cve="CVE-T-1", sample_id="CVE-T-1")
        r = self.client.post("/api/ingest", json=s)
        self.assertEqual(r.status_code, 200)
        self.assertIn(r.json()["status"], ("accepted", "quarantined"))

    def test_rejects_incomplete_sample_with_422(self):
        s = dict(GOOD, cve="CVE-T-2", sample_id="CVE-T-2", patch_code="")
        r = self.client.post("/api/ingest", json=s)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["status"], "rejected")

    def test_invalid_json_returns_400(self):
        r = self.client.post("/api/ingest", content=b"{not json")
        self.assertEqual(r.status_code, 400)

    def test_non_object_json_returns_400(self):
        r = self.client.post("/api/ingest", json=[1, 2, 3])
        self.assertEqual(r.status_code, 400)

    def test_accepted_samples_append_not_overwrite(self):
        data_dir = os.environ["MARSAD_DATA_DIR"]
        path = os.path.join(data_dir, "github_training_ready.jsonl")
        for cve in ("CVE-A1", "CVE-A2", "CVE-A3"):
            s = dict(GOOD, cve=cve, sample_id=cve)
            r = self.client.post("/api/ingest/github", json=s)
            self.assertEqual(r.status_code, 200)
        lines = open(path, encoding="utf-8").read().strip().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual({json.loads(l)["cve"] for l in lines}, {"CVE-A1", "CVE-A2", "CVE-A3"})

    def test_health_endpoint(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "operational")

    def test_sandbox_endpoint_routes_correctly(self):
        s = dict(GOOD, cve="CVE-SB-1", sample_id="CVE-SB-1")
        r = self.client.post("/api/ingest/sandbox", json=s)
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
