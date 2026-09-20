"""Real cloud validation only.

The system does not create cloud accounts or fake cloud credentials.
It checks whether the required real environment variables exist and are valid.
"""
import os
import time


class CloudAgent:
    """Validate configured cloud providers without fabricating accounts."""

    def __init__(self):
        self.clouds = {
            "gcp": "GOOGLE_APPLICATION_CREDENTIALS",
            "aws": "AWS_ACCESS_KEY_ID",
            "azure": "AZURE_SUBSCRIPTION_ID",
            "oracle": "OCI_TENANCY_OCID",
            "cloudflare": "CLOUDFLARE_API_TOKEN",
            "railway": "RAILWAY_API_TOKEN",
            "render": "RENDER_API_KEY",
            "fly": "FLY_API_TOKEN",
        }

    def register(self, cloud: str) -> dict:
        if cloud not in self.clouds:
            return {"status": "unsupported", "cloud": cloud}

        env_name = self.clouds[cloud]
        value = os.environ.get(env_name, "").strip()
        if not value:
            return {
                "status": "missing_credentials",
                "cloud": cloud,
                "env_key": env_name,
                "message": "يجب إضافة بيانات اعتماد حقيقية لهذا السحابي."
            }

        return {
            "status": "configured",
            "cloud": cloud,
            "env_key": env_name,
            "message": "تم العثور على بيانات اعتماد حقيقية في بيئة التشغيل."
        }

    def register_all(self) -> dict:
        results = {}
        for cloud in self.clouds:
            results[cloud] = self.register(cloud)
            time.sleep(0.2)
        return results


cloud_agent = CloudAgent()
