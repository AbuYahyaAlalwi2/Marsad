# CyberAgent Blueprint — خطة Marsad السيبرانية
> محفوظ: 2026-09-27 | قرار: D (Termux → Kaggle)

## المعمارية
Termux (تحكم) → Render (API) → Kaggle T4 (تنفيذ)

## المراحل

### 1. صهر النموذج
- النماذج: DeepSeek-R1 (0.7) + Nous-Llama-3 (0.3)
- طريقة: ties | Hermes مستبعد (vocab mismatch)
- Kernel الحالي: marsad-merge-1790489695
- الرفع: abuyahya/deepseek-marsad

### 2. طبقة الرفض
- core/reframing.py — إعادة تأطير بحثي
- دمج في orchestrator_v2.dispatch()

### 3. أدوات توليد الملفات
- tools/report_pdf.py — reportlab
- tools/report_pptx.py — python-pptx
- tools/report_mermaid.py — مخططات هجوم
- tools/report_md.py — تقارير Markdown

### 4. الحواس السيبرانية
- tools/cyber_senses.py
  * cve_lookup → NVD API
  * search_exploits → ExploitDB
  * scan_target → nuclei/nmap
  * read_code → قراءة كمهاجم

### 5. العقل الهجومي
- core/cyber_reasoning.py
  * threat_model | chain_vulns | verify_exploit | report_finding

### 6. الذاكرة الترافعية
- ChromaDB + embeddings
- مصادر: OWASP, HackerOne, CVE DB

## من ECC (مؤجل)
- AgentShield | Skill Loader | Memory Vault | Instincts

## مؤجل
- MoE Franken-Merge | Abliteration | LoRA سيبراني | بوت تليجرام
