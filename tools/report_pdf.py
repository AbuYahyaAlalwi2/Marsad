"""report_pdf.py — تقارير PDF احترافية للعملاء."""
from __future__ import annotations
import os, time, logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import logging
logger = logging.getLogger(__name__)

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                     Table, TableStyle, PageBreak)
    from reportlab.lib.enums import TA_RIGHT, TA_LEFT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    _HAS_PDF = True
    # ─── دعم العربية ─────────────────────────────────
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        _HAS_ARABIC = True
    except ImportError:
        _HAS_ARABIC = False
    # سجّل الخط العربي إن وُجد
    _FONT_REGULAR = "Helvetica"
    _FONT_BOLD = "Helvetica-Bold"
    _FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    try:
        reg = _FONT_PATH / "Amiri-Regular.ttf"
        bld = _FONT_PATH / "Amiri-Bold.ttf"
        if reg.exists():
            pdfmetrics.registerFont(TTFont("NotoAr", str(reg)))
            _FONT_REGULAR = "NotoAr"
        if bld.exists():
            pdfmetrics.registerFont(TTFont("NotoAr-Bold", str(bld)))
            _FONT_BOLD = "NotoAr-Bold"
    except Exception as e:
        logger.warning("font registration failed: %s", e)
except ImportError:
    _HAS_PDF = False

OUT = Path(os.environ.get("CG_REPORTS_DIR",
                          str(Path.home() / "marsad_reports")))
OUT.mkdir(parents=True, exist_ok=True)

SEVERITY_COLORS = {
    "CRITICAL": colors.HexColor("#8B0000"),
    "HIGH": colors.HexColor("#DC143C"),
    "MEDIUM": colors.HexColor("#FF8C00"),
    "LOW": colors.HexColor("#FFD700"),
    "INFO": colors.HexColor("#4682B4"),
}




import re as _re

_TAG_RE = _re.compile(r"(<[^>]+>)")

# إيموجي شائعة يجب إزالتها قبل reshape
_EMOJI_RE = _re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F000-\U0001F02F"
    "]+", flags=_re.UNICODE)


def ar(text) -> str:
    """يحوّل النص العربي: إزالة الإيموجي → reshape → bidi على النص كاملاً."""
    if text is None:
        return ""
    s = str(text)
    if not _HAS_ARABIC:
        return s

    # 1. أزل الإيموجي (تكسر arabic_reshaper)
    s = _EMOJI_RE.sub("", s)

    # 2. لا تفصل HTML tags — سيبقى النص عربياً + إنجليزياً
    #    get_display على النص كاملاً هو الصحيح
    try:
        reshaped = arabic_reshaper.reshape(s)
        return get_display(reshaped)
    except Exception:
        return s


def _styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("Title", parent=ss["Title"], fontName=_FONT_BOLD,
                                fontSize=22, textColor=colors.HexColor("#1a1a1a"),
                                spaceAfter=20, alignment=TA_RIGHT),
        "h1": ParagraphStyle("H1", parent=ss["Heading1"], fontName=_FONT_BOLD,
                             fontSize=16, textColor=colors.HexColor("#0d3b66"),
                             spaceAfter=10, alignment=TA_RIGHT),
        "h2": ParagraphStyle("H2", parent=ss["Heading2"], fontName=_FONT_BOLD,
                             fontSize=13, textColor=colors.HexColor("#1e6091"),
                             spaceAfter=8, alignment=TA_RIGHT),
        "body": ParagraphStyle("Body", parent=ss["BodyText"], fontName=_FONT_REGULAR,
                               fontSize=11, alignment=TA_RIGHT, leading=16),
        "mono": ParagraphStyle("Mono", parent=ss["Code"], fontName=_FONT_REGULAR,
                               fontSize=9, alignment=TA_LEFT,
                               backColor=colors.HexColor("#f4f4f4")),
    }


def build_vulnerability_report(
    vuln: Dict[str, Any],
    client_name: str = "العميل",
    author: str = "Marsad CyberAgent",
    output_name: Optional[str] = None,
) -> str:
    """ينشئ تقرير PDF لثغرة واحدة."""
    if not _HAS_PDF:
        raise RuntimeError("reportlab غير مثبت: pip install reportlab")

    cve = vuln.get("cve", "UNKNOWN")
    nvd = vuln.get("nvd", {})
    score = nvd.get("cvss_score") or 0
    severity = nvd.get("cvss_severity", "UNKNOWN").upper()

    fname = output_name or f"report_{cve}_{int(time.time())}.pdf"
    fpath = OUT / fname

    doc = SimpleDocTemplate(str(fpath), pagesize=A4,
                            rightMargin=2 * cm, leftMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    st = _styles()
    story: List[Any] = []

    # ─── غلاف ─────────────────────────────────────────────
    story.append(Spacer(1, 60))
    story.append(Paragraph(ar("تقرير ثغرة أمنية"), st["title"]))
    story.append(Spacer(1, 20))
    story.append(Paragraph(ar(f"العميل: {client_name}"), st["body"]))
    story.append(Paragraph(ar(f"معرّف الثغرة: {cve}"), st["body"]))
    story.append(Paragraph(
        ar(f"التاريخ: {datetime.now().strftime('%Y-%m-%d')}"), st["body"]))
    story.append(Paragraph(ar(f"المُعِدّ: {author}"), st["body"]))
    story.append(Spacer(1, 40))

    # ─── ملخص تنفيذي ──────────────────────────────────────
    story.append(Paragraph(ar("ملخص تنفيذي"), st["h1"]))
    summary = (
        f"تم رصد ثغرة أمنية بدرجة خطورة <b>{severity}</b> "
        f"(CVSS: {score}/10) في النظام. "
    )
    if vuln.get("cisa_exploited"):
        summary += "<b>⚠️ هذه الثغرة مُستغلة فعلياً في العالم (CISA KEV).</b> "
    if vuln.get("exploit_available"):
        summary += "<b>يوجد استغلال جاهز منشور علناً.</b> "
    summary += "يجب معالجتها بأولوية عالية."
    story.append(Paragraph(summary, st["body"]))
    story.append(Spacer(1, 20))

    # ─── بطاقة التفاصيل ────────────────────────────────────
    story.append(Paragraph(ar("تفاصيل الثغرة"), st["h1"]))
    sev_color = SEVERITY_COLORS.get(severity, colors.grey)
    data = [
        [ar("الحقل"), ar("القيمة")],
        [ar("المعرّف"), cve],
        [ar("الخطورة"), severity],
        [ar("درجة CVSS"), f"{score}/10"],
        [ar("المتجه"), nvd.get("vector", "—")],
        [ar("تاريخ النشر"), (nvd.get("published") or "—")[:10]],
    ]
    tbl = Table(data, colWidths=[4 * cm, 11 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), sev_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), _FONT_REGULAR),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f9f9f9")]),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 20))

    # ─── الوصف التقني ─────────────────────────────────────
    story.append(Paragraph(ar("الوصف التقني"), st["h1"]))
    desc = nvd.get("description", "—")
    story.append(Paragraph(desc, st["body"]))
    story.append(Spacer(1, 20))

    # ─── الاستغلالات المنشورة ─────────────────────────────
    if vuln.get("exploits"):
        story.append(Paragraph(ar("استغلالات منشورة"), st["h1"]))
        story.append(Paragraph(
            ar("الاستغلالات التالية متوفرة علناً في"),
            st["body"]))
        story.append(Spacer(1, 8))
        edata = [["ID", ar("التاريخ"), ar("الوصف")]]
        for e in vuln["exploits"][:10]:
            edata.append([
                e.get("id", "—"),
                e.get("date", "—"),
                (e.get("description", "") or "")[:70],
            ])
        etbl = Table(edata, colWidths=[2 * cm, 3 * cm, 10 * cm])
        etbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e6091")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), _FONT_BOLD),
            ("FONTNAME", (0, 1), (-1, -1), _FONT_REGULAR),
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(etbl)
        story.append(Spacer(1, 20))

    # ─── التوصيات ─────────────────────────────────────────
    story.append(Paragraph(ar("التوصيات الفورية"), st["h1"]))
    recs = [
        "تحديث النظام إلى آخر إصدار متوفر فوراً.",
        "تطبيق الضوابط الأمنية الموصى بها من المزود.",
        "فحص السجلات (logs) بحثاً عن محاولات استغلال سابقة.",
        "عزل الأنظمة المتأثرة عن الإنترنت إن أمكن.",
    ]
    if vuln.get("cisa_exploited"):
        recs.insert(0, "الثغرة مُستغلة فعلياً — عالجها خلال 24 ساعة.")
    for i, r in enumerate(recs, 1):
        story.append(Paragraph(ar(f"{i}. {r}"), st["body"]))
    story.append(Spacer(1, 30))

    # ─── المراجع ──────────────────────────────────────────
    story.append(Paragraph(ar("المراجع"), st["h1"]))
    for ref in (nvd.get("references") or [])[:8]:
        story.append(Paragraph(f"• {ref}", st["body"]))

    # ─── تذييل ────────────────────────────────────────────
    story.append(Spacer(1, 30))
    footer_text = (f"تم إنشاء هذا التقرير آلياً بواسطة {author} - "
                   f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    story.append(Paragraph(ar(footer_text), st["body"]))

    doc.build(story)
    logger.info("[report_pdf] saved: %s", fpath)
    return str(fpath)


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("usage: report_pdf.py CVE-XXXX-YYYY [client_name]")
        sys.exit(1)
    cve = sys.argv[1]
    client = sys.argv[2] if len(sys.argv) > 2 else "عميل تجريبي"
    from tools.cyber_senses import threat_summary
    print(f"⏳ جلب {cve}...")
    vuln = threat_summary(cve)
    print(f"⏳ إنشاء التقرير...")
    path = build_vulnerability_report(vuln, client_name=client)
    print(f"✅ {path}")
    print(f"📄 الحجم: {Path(path).stat().st_size // 1024} KB")
