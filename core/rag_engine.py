"""
RAG Engine — نظام الاسترجاع الذكي
يعطي النموذج "ذاكرة حية" بثغرات مشابهة قبل كل تحليل
بدون GPU — يعمل على أي جهاز
"""

import json
import math
import re
import time
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
from knowledge_store import get_store, KnowledgeStore


# ─── TF-IDF Vectorizer (بدون مكتبات ثقيلة) ───────────────────────────────────

class LightVectorizer:
    """
    TF-IDF بسيط بدون sklearn أو numpy
    يعمل على أي جهاز بدون GPU
    إذا كان chromadb متاح يستخدمه، وإلا يعمل بـ TF-IDF
    """

    def __init__(self):
        self._idf: Dict[str, float] = {}
        self._docs: List[dict] = []
        self._use_chroma = self._try_chroma()

    def _try_chroma(self) -> bool:
        try:
            import chromadb
            self._chroma_client = chromadb.PersistentClient(
                path=str(Path(__file__).parent.parent / "database" / "chroma")
            )
            self._collection = self._chroma_client.get_or_create_collection(
                name="marsad_security",
                metadata={"hnsw:space": "cosine"}
            )
            return True
        except ImportError:
            return False

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        # كلمات أمنية مهمة كـ tokens منفصلة
        security_terms = [
            "sql injection", "buffer overflow", "xss", "csrf", "rce",
            "privilege escalation", "path traversal", "xxe", "ssrf",
            "deserialization", "command injection", "ldap injection",
        ]
        for term in security_terms:
            text = text.replace(term, term.replace(" ", "_"))

        tokens = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b', text)
        return tokens

    def _tf(self, tokens: List[str]) -> Dict[str, float]:
        freq = defaultdict(int)
        for t in tokens:
            freq[t] += 1
        total = len(tokens) or 1
        return {t: c / total for t, c in freq.items()}

    def build_index(self, docs: List[dict]):
        """يبني الفهرس من السجلات"""
        self._docs = docs
        N = len(docs)

        # حساب IDF
        df = defaultdict(int)
        for doc in docs:
            text = f"{doc.get('description','')} {doc.get('explanation','')} {doc.get('vulnerable_code','')}"
            for t in set(self._tokenize(text)):
                df[t] += 1

        self._idf = {
            t: math.log((N + 1) / (count + 1)) + 1
            for t, count in df.items()
        }

        # إذا كان chroma متاح، استخدمه للتخزين الدائم
        if self._use_chroma:
            self._build_chroma_index(docs)

    def _build_chroma_index(self, docs: List[dict]):
        existing_ids = set(self._collection.get()["ids"])
        new_docs  = [d for d in docs if d.get("record_id") not in existing_ids]
        if not new_docs:
            return

        texts = [
            f"{d.get('title','')} {d.get('description','')} {d.get('explanation','')}"
            for d in new_docs
        ]
        ids = [d["record_id"] for d in new_docs]

        # chroma يحسب embeddings داخلياً إذا استخدمنا النص مباشرة
        self._collection.add(
            documents=texts,
            ids=ids,
            metadatas=[{"cve_id": d.get("cve_id",""), "severity": d.get("severity","")} for d in new_docs]
        )

    def search(self, query: str, top_k: int = 5) -> List[dict]:
        if self._use_chroma and self._collection.count() > 0:
            return self._chroma_search(query, top_k)
        return self._tfidf_search(query, top_k)

    def _chroma_search(self, query: str, top_k: int) -> List[dict]:
        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, self._collection.count()),
        )
        ids      = results["ids"][0]
        store    = get_store()
        hits     = []
        for rid in ids:
            with store._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM records WHERE record_id=?", (rid,)
                ).fetchone()
            if row:
                hits.append(store._row_to_dict(row))
        return hits

    def _tfidf_search(self, query: str, top_k: int) -> List[dict]:
        q_tokens = self._tokenize(query)
        q_tf     = self._tf(q_tokens)
        q_vec    = {t: q_tf[t] * self._idf.get(t, 1.0) for t in q_tf}

        scores = []
        for doc in self._docs:
            text = f"{doc.get('description','')} {doc.get('explanation','')} {doc.get('vulnerable_code','')}"
            d_tokens = self._tokenize(text)
            d_tf     = self._tf(d_tokens)
            d_vec    = {t: d_tf[t] * self._idf.get(t, 1.0) for t in d_tf}

            # Cosine similarity
            dot   = sum(q_vec.get(t, 0) * d_vec.get(t, 0) for t in q_vec)
            norm_q = math.sqrt(sum(v**2 for v in q_vec.values())) or 1
            norm_d = math.sqrt(sum(v**2 for v in d_vec.values())) or 1
            score  = dot / (norm_q * norm_d)
            scores.append((score, doc))

        scores.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scores[:top_k]]


# ─── RAG Engine ───────────────────────────────────────────────────────────────

class RAGEngine:
    """
    يعطي النموذج سياقاً ذكياً قبل كل تحليل:
    1. يبحث عن ثغرات مشابهة
    2. يجلب أخطاء النموذج السابقة في هذا السياق
    3. يبني prompt محسّن يمنع الأخطاء المتكررة
    """

    def __init__(self):
        self.store      = get_store()
        self.vectorizer = LightVectorizer()
        self._last_build = 0
        self._build_interval = 3600  # أعد بناء الفهرس كل ساعة

    def _ensure_index(self):
        now = time.time()
        if now - self._last_build < self._build_interval:
            return

        with self.store._conn() as conn:
            rows = conn.execute("""
                SELECT record_id, cve_id, title, description, explanation,
                       vulnerable_code, severity, cvss_score
                FROM records WHERE verified=1
            """).fetchall()

        docs = [
            {
                "record_id":      r[0],
                "cve_id":         r[1],
                "title":          r[2],
                "description":    r[3],
                "explanation":    r[4],
                "vulnerable_code": r[5],
                "severity":       r[6],
                "cvss_score":     r[7],
            }
            for r in rows
        ]

        if docs:
            self.vectorizer.build_index(docs)
            self._last_build = now

    def build_context(self, code_or_query: str, top_k: int = 3) -> str:
        """
        يبني السياق الكامل للنموذج:
        - ثغرات مشابهة من قاعدة البيانات
        - أخطاء سابقة في هذا النوع من الكود
        - تحذيرات محددة

        هذا الـ context يُضاف قبل prompt المستخدم
        """
        self._ensure_index()

        similar = self.vectorizer.search(code_or_query, top_k=top_k)
        errors  = self.store.get_errors_for_context(code_or_query, limit=3)

        parts = []

        # ── ثغرات مشابهة ──────────────────────────────────────────────────────
        if similar:
            parts.append("=== ثغرات مشابهة من قاعدة المعرفة ===")
            for i, s in enumerate(similar, 1):
                parts.append(
                    f"[{i}] {s.get('cve_id','N/A')} | CVSS={s.get('cvss_score',0):.1f} | {s.get('severity','')}\n"
                    f"    {s.get('title','')}\n"
                    f"    التفسير: {s.get('explanation','')[:150]}..."
                )

        # ── أخطاء سابقة ───────────────────────────────────────────────────────
        if errors:
            parts.append("\n=== تحذير: أخطاء سابقة في سياق مشابه ===")
            for e in errors:
                parts.append(
                    f"⚠ خطأ سابق ({e['times_repeated']+1}x): {e['error_type']}\n"
                    f"  الإجابة الخاطئة: {e['wrong_answer'][:80]}...\n"
                    f"  الدرس: {e['lesson']}"
                )

        if not parts:
            return ""  # لا سياق — النموذج يعمل بدونه

        context = "\n".join(parts)
        return f"""
<security_context>
{context}

⚠ تعليمات: استخدم المعلومات أعلاه كمرجع، لكن حلل الكود المعطى بشكل مستقل.
لا تفترض أن الثغرة هي نفسها — قد تكون مشابهة أو مختلفة.
</security_context>

"""

    def augmented_prompt(self, user_prompt: str, code: str = "") -> str:
        """
        يبني الـ prompt الكامل مع السياق:
        context + prompt الأصلي
        """
        context = self.build_context(code or user_prompt)
        return f"{context}{user_prompt}"

    def stats(self) -> dict:
        with self.store._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM records WHERE verified=1").fetchone()[0]
        return {
            "indexed_records": total,
            "using_chroma":    self.vectorizer._use_chroma,
            "last_build":      time.strftime("%H:%M:%S", time.localtime(self._last_build)) if self._last_build else "لم يبنَ بعد",
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

_rag: Optional[RAGEngine] = None

def get_rag() -> RAGEngine:
    global _rag
    if _rag is None:
        _rag = RAGEngine()
    return _rag
