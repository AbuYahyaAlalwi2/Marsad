"""فحص robots.txt قبل أي عملية جمع (بند 2 من الدستور). ملاحظة: هذا لا يغني عن التصريح القانوني."""

import urllib.robotparser
from urllib.parse import urlparse


def check_allowed(url: str, user_agent: str = "MarsadCollector") -> dict:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        allowed = rp.can_fetch(user_agent, url)
    except Exception:
        allowed = False  # تعذّر القراءة → الافتراضي رفض، لا سماح
    return {
        "robots_url": robots_url,
        "allowed": allowed,
        "note": "robots.txt ليس بديلاً عن التصريح القانوني — تحقق من ToS أيضاً.",
    }
