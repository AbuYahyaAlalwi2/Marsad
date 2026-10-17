import gzip
import io
import json
import sys
import urllib.error
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import historical_truth_miner_v1 as m


# ───────────── بيانات تجريبية ─────────────

PATCH_LINES = [
    "From abc123def456 Mon Sep 17 00:00:00 2001",
    "From: Dev <dev@example.com>",
    "Date: Mon, 1 Jan 2024 00:00:00 +0000",
    "Subject: [PATCH] Fix heap overflow in parse_len",
    "",
    "Check the length byte before memcpy. Found by oss-fuzz.",
    "---",
    " src/parse.c | 4 +++-",
    " 1 file changed, 3 insertions(+), 1 deletion(-)",
    "",
    "diff --git a/src/parse.c b/src/parse.c",
    "index 111..222 100644",
    "--- a/src/parse.c",
    "+++ b/src/parse.c",
    "@@ -10,7 +10,9 @@ int parse_len(const char *buf, size_t n)",
    " {",
    "     char tmp[16];",
    "     int len = buf[0];",
    "-    memcpy(tmp, buf + 1, len);",
    "+    if (len < 0 || (size_t)len > sizeof(tmp) || (size_t)len + 1 > n)",
    "+        return -1;",
    "+    memcpy(tmp, buf + 1, len);",
    "     return len;",
    " }",
    " ",
    "diff --git a/tests/test_parse.c b/tests/test_parse.c",
    "--- a/tests/test_parse.c",
    "+++ b/tests/test_parse.c",
    "@@ -1,3 +1,4 @@",
    " a",
    " b",
    "+c",
    " d",
    "-- ",
    "2.40.0",
    "",
]
PATCH = "\n".join(PATCH_LINES)

OSV = {
    "id": "OSV-2024-1",
    "summary": "Heap-buffer-overflow in parse_len",
    "details": "A heap buffer overflow occurs when the length byte exceeds the temp buffer size, "
               "allowing an out-of-bounds write.",
    "affected": [{"ranges": [{"type": "GIT", "repo": "https://github.com/acme/libfoo",
                              "events": [{"introduced": "0"}, {"fixed": "abc123def456"}]}]}],
    "references": [],
}

REPO_OK = json.dumps({"license": {"spdx_id": "MIT"}, "archived": False, "stargazers_count": 500}).encode()


class FakeHttp:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def _find(self, url):
        self.calls.append(url)
        for k, v in self.routes.items():
            if k in url:
                if isinstance(v, Exception):
                    raise v
                return v
        raise m.NotFound(url)

    def get_bytes(self, url, accept=None, max_bytes=0):
        v = self._find(url)
        return v if isinstance(v, bytes) else v.encode()

    def get_text(self, url, accept=None):
        return self.get_bytes(url).decode()


def make_miner(tmp_path, routes, **cfg_kw):
    cfg = m.Config(out_dir=tmp_path, request_delay=0, **cfg_kw)
    miner = m.Miner(m.Store(tmp_path / "state.sqlite"), FakeHttp(routes), m.ShardWriter(tmp_path, cfg.shard_size),
                    cfg, sleep=lambda s: None)
    return miner


def good_routes():
    return {"api.github.com/repos/acme/libfoo": REPO_OK, "commit/abc123def456.patch": PATCH}


def read_samples(tmp_path):
    out = []
    for f in sorted(tmp_path.glob("samples_*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            out += [json.loads(l) for l in fh]
    return out


# ───────────── تحليل ─────────────

def test_parse_patch_hunks_message_and_signature_ignored():
    msg, hunks = m.parse_patch(PATCH)
    assert msg.startswith("Fix heap overflow in parse_len")
    assert "oss-fuzz" in msg
    assert [h.path for h in hunks] == ["src/parse.c", "tests/test_parse.c"]
    h = hunks[0]
    assert len(h.before) == 7 and len(h.after) == 9
    assert h.removed == ["    memcpy(tmp, buf + 1, len);"]
    assert "parse_len" in h.context
    # توقيع "-- " الأخير لا يتحول إلى سطر محذوف
    assert hunks[1].removed == []


def test_extract_fix_commits_git_range_and_fix_ref_and_dedupe():
    rec = dict(OSV)
    rec["references"] = [
        {"type": "FIX", "url": "https://github.com/acme/libfoo/commit/abc123def456"},
        {"type": "WEB", "url": "https://github.com/acme/libfoo/commit/ffffffffffff"},
        {"type": "FIX", "url": "https://github.com/other/lib/commit/1234567"},
    ]
    got = m.extract_fix_commits(rec)
    assert ("acme", "libfoo", "abc123def456") in got
    assert ("other", "lib", "1234567") in got
    assert len(got) == 2  # WEB مُتجاهَل والمكرر مدمج


def test_extract_fix_commits_ignores_non_github():
    rec = {"affected": [{"ranges": [{"type": "GIT", "repo": "https://gitlab.com/a/b",
                                     "events": [{"fixed": "abcdef1"}]}]}]}
    assert m.extract_fix_commits(rec) == []


def test_extract_cwes_stated_inferred_none():
    assert m.extract_cwes({"details": "see CWE-79 here"}) == (["CWE-79"], "stated")
    assert m.extract_cwes({"database_specific": {"cwe_ids": ["CWE-89"]}})[0] == ["CWE-89"]
    cw, src = m.extract_cwes({"summary": "Heap-buffer-overflow in x"})
    assert cw == ["CWE-122"] and src == "inferred_from_summary"
    assert m.extract_cwes({"summary": "something odd"}) == ([], "none")


# ───────────── البوابات ─────────────

def test_license_gate():
    ok = {"license": "MIT", "archived": False, "stars": 100}
    A = m.ALLOWED_LICENSES
    assert m.gate_license(ok, A, 10) is None
    assert m.gate_license({**ok, "license": "GPL-3.0"}, A, 10).startswith("license_not_allowed")
    assert m.gate_license({**ok, "license": None}, A, 10) == "license_missing"
    assert m.gate_license({**ok, "archived": True}, A, 10) == "repo_archived"
    assert m.gate_license({**ok, "stars": 1}, A, 10) == "repo_low_confidence"
    assert m.gate_license({"gone": True}, A, 10) == "repo_gone"


def test_secret_gate_and_no_change_gate():
    base = {"vulnerable_code": "a = 1", "patched_code": "a = 2", "causal_explanation": "x" * 40}
    assert m.gate_sample(base) is None
    assert m.gate_sample({**base, "patched_code": "a=1 "}) == "no_semantic_change"
    assert m.gate_sample({**base, "patched_code": "t = 'ghp_" + "a" * 30 + "'"}) == "secret_detected"
    assert m.gate_sample({**base, "causal_explanation": "short"}) == "no_causal_explanation"
    assert m.gate_sample({**base, "patched_code": "  "}) == "no_patch"


def test_split_deterministic_ratio():
    assert m.split_of("a/b@123") == m.split_of("a/b@123")
    n_eval = sum(m.split_of(f"r/x@{i}") == "eval" for i in range(3000))
    assert 0.11 < n_eval / 3000 < 0.19


# ───────────── التشغيل الكامل ─────────────

def test_process_vuln_end_to_end(tmp_path):
    miner = make_miner(tmp_path, good_routes())
    assert miner.process_vuln(OSV) == "accepted:1"
    s = read_samples(tmp_path)
    assert len(s) == 1
    s = s[0]
    assert s["language"] == "c" and s["file"] == "src/parse.c"   # ملف الاختبار استُبعد
    assert "memcpy" in s["vulnerable_code"] and "sizeof(tmp)" in s["patched_code"]
    assert "sizeof(tmp)" not in s["vulnerable_code"]
    assert "Heap-buffer-overflow" in s["causal_explanation"] and "oss-fuzz" in s["causal_explanation"]
    assert s["cwe"] == ["CWE-122"] and s["license"] == "MIT"
    assert s["verification_level"] == "pattern_only" and s["split"] in ("train", "eval")


def test_resume_skips_done_and_makes_no_network_calls(tmp_path):
    miner = make_miner(tmp_path, good_routes())
    miner.process_vuln(OSV)
    n = len(miner.http.calls)
    assert miner.process_vuln(OSV) == "skipped_done"
    assert len(miner.http.calls) == n


def test_duplicate_content_across_vulns_rejected(tmp_path):
    miner = make_miner(tmp_path, good_routes())
    miner.process_vuln(OSV)
    twin = {**OSV, "id": "OSV-2024-2"}
    assert miner.process_vuln(twin) == "rejected:duplicate"
    assert len(read_samples(tmp_path)) == 1


def test_reject_no_fix_and_malware_ids(tmp_path):
    miner = make_miner(tmp_path, good_routes())
    assert miner.process_vuln({"id": "X-1", "summary": "s"}) == "rejected:no_fix_commit"
    assert miner.process_vuln({**OSV, "id": "MAL-2024-9"}) == "rejected:malware_or_withdrawn"
    assert miner.process_vuln({**OSV, "id": "X-2", "withdrawn": "2024-01-01"}) == "rejected:malware_or_withdrawn"
    assert miner.http.calls == []


def test_gpl_repo_rejected_without_fetching_patch(tmp_path):
    gpl = json.dumps({"license": {"spdx_id": "GPL-3.0"}, "archived": False, "stargazers_count": 999}).encode()
    miner = make_miner(tmp_path, {"api.github.com/repos/acme/libfoo": gpl, "commit/": PATCH})
    assert miner.process_vuln(OSV).startswith("rejected:license_not_allowed")
    assert not any(".patch" in c for c in miner.http.calls)


def test_network_failure_is_deferred_not_recorded(tmp_path):
    routes = {"api.github.com/repos/acme/libfoo": REPO_OK, "commit/": m.FetchFailed("boom")}
    miner = make_miner(tmp_path, routes)
    assert miner.process_vuln(OSV) == "deferred"
    assert not miner.store.is_done(OSV["id"])          # يُعاد لاحقاً
    miner.http.routes["commit/"] = PATCH
    assert miner.process_vuln(OSV) == "accepted:1"


def test_language_filter(tmp_path):
    miner = make_miner(tmp_path, good_routes(), languages={"php"})
    assert miner.process_vuln(OSV) == "rejected:no_code_hunks"


def test_comment_only_change_rejected(tmp_path):
    patch = "\n".join([
        "From a", "Subject: [PATCH] typo", "", "fix a comment typo in the file here", "---", "",
        "diff --git a/src/a.c b/src/a.c", "--- a/src/a.c", "+++ b/src/a.c", "@@ -1,4 +1,4 @@",
        " int a;", " int b;", "-// old comment", "+// new comment", " int c;", "",
    ])
    miner = make_miner(tmp_path, {"api.github.com/repos/acme/libfoo": REPO_OK, "commit/": patch})
    assert miner.process_vuln(OSV) == "rejected:comment_only_change"


def test_commit_too_broad_rejected(tmp_path):
    files = []
    for i in range(12):
        files += [f"diff --git a/src/f{i}.c b/src/f{i}.c", f"--- a/src/f{i}.c", f"+++ b/src/f{i}.c",
                  "@@ -1,3 +1,3 @@", " x", "-a", "+b", " y"]
    patch = "\n".join(["From a", "Subject: [PATCH] big refactor of everything", "", "body", "---", ""] + files + [""])
    miner = make_miner(tmp_path, {"api.github.com/repos/acme/libfoo": REPO_OK, "commit/": patch})
    assert miner.process_vuln(OSV) == "rejected:commit_too_broad"


def test_shards_are_new_files_never_overwritten(tmp_path):
    w1 = m.ShardWriter(tmp_path, shard_size=2)
    for i in range(5):
        w1.write({"i": i})
    assert len(w1.files) == 3
    w1.run_id = "OTHER"  # تشغيل لاحق
    w1.n = 0
    w1.in_shard = 0
    w1.write({"i": 99})
    assert len(list(tmp_path.glob("samples_*.jsonl.gz"))) == 4
    assert len(read_samples(tmp_path)) == 6


def test_run_ecosystem_from_zip_and_status(tmp_path):
    zp = tmp_path / "eco.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("OSV-2024-1.json", json.dumps(OSV))
        z.writestr("junk.json", "{not json")
        z.writestr("readme.txt", "x")
    miner = make_miner(tmp_path, good_routes())
    m.run_ecosystem(miner, zp, "OSS-Fuzz", lambda: False, status_every=1)
    assert miner.counts["accepted"] == 1
    m.write_status(miner.cfg, miner, "OSS-Fuzz", "finished")
    st = json.loads((tmp_path / "STATUS.json").read_text())
    assert st["vulns"]["accepted"] == 1 and st["unique_samples"] == 1


def test_stop_flag_halts_loop(tmp_path):
    zp = tmp_path / "eco.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("a.json", json.dumps(OSV))
    miner = make_miner(tmp_path, good_routes())
    m.run_ecosystem(miner, zp, "x", lambda: True)
    assert sum(miner.counts.values()) == 0


# ───────────── طبقة HTTP ─────────────

class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_http_retries_on_429_then_succeeds():
    seq = [urllib.error.HTTPError("u", 429, "slow", {"Retry-After": "3"}, None), _Resp(b"ok")]
    sleeps = []

    def opener(req, timeout=0):
        x = seq.pop(0)
        if isinstance(x, Exception):
            raise x
        return x

    h = m.Http(opener=opener, sleep=sleeps.append)
    assert h.get_bytes("https://github.com/x") == b"ok"
    assert sleeps == [3.0]


def test_http_404_is_notfound_and_exhaustion_is_fetchfailed():
    def nf(req, timeout=0):
        raise urllib.error.HTTPError("u", 404, "nf", {}, None)

    with pytest.raises(m.NotFound):
        m.Http(opener=nf, sleep=lambda s: None).get_bytes("https://github.com/x")

    def boom(req, timeout=0):
        raise urllib.error.HTTPError("u", 500, "err", {}, None)

    with pytest.raises(m.FetchFailed):
        m.Http(opener=boom, sleep=lambda s: None, max_retries=2).get_bytes("https://github.com/x")


def test_token_only_sent_to_api_github():
    seen = []

    def opener(req, timeout=0):
        seen.append((req.full_url, req.get_header("Authorization")))
        return _Resp(b"{}")

    h = m.Http(token="SECRET", opener=opener)
    h.get_bytes("https://api.github.com/repos/a/b")
    h.get_bytes("https://github.com/a/b/commit/abc.patch")
    h.get_bytes("https://osv-vulnerabilities.storage.googleapis.com/x/all.zip")
    assert seen[0][1] == "Bearer SECRET"
    assert seen[1][1] is None and seen[2][1] is None


# ───────────── الوضع المستمر ─────────────

def _zip_with(tmp_path, *recs, name="eco.zip"):
    zp = tmp_path / "cache" / name
    zp.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(zp, "w") as z:
        for i, r in enumerate(recs):
            z.writestr(f"{i}.json", json.dumps(r))
    return zp


def test_one_bad_record_does_not_stop_the_run(tmp_path):
    miner = make_miner(tmp_path, good_routes())
    real = miner.process_vuln

    def flaky(rec):
        if rec["id"] == "BAD":
            raise RuntimeError("boom")
        return real(rec)

    miner.process_vuln = flaky
    zp = _zip_with(tmp_path, {**OSV, "id": "BAD"}, OSV)
    m.run_ecosystem(miner, zp, "x", lambda: False)
    assert miner.counts["error"] == 1 and miner.counts["accepted"] == 1


def test_forever_loop_repeats_picks_up_new_records_and_idles(tmp_path):
    miner = make_miner(tmp_path, good_routes())
    _zip_with(tmp_path, OSV, name="OSS-Fuzz.zip")
    sleeps = []
    http = miner.http
    http.download = lambda url, dest: None  # الملف المخزّن حديث، لا تنزيل
    passes = m.run_loop(miner, http, ["OSS-Fuzz"], tmp_path, lambda: False, forever=True,
                        idle_seconds=10, sleep=sleeps.append, max_passes=3)
    assert passes == 3
    assert miner.counts["accepted"] == 1            # الأول فقط؛ الباقي skipped_done
    assert miner.counts["skipped_done"] == 2
    assert sum(sleeps) >= 20                         # نام بين المرورات


def test_once_mode_runs_single_pass(tmp_path):
    miner = make_miner(tmp_path, good_routes())
    _zip_with(tmp_path, OSV, name="OSS-Fuzz.zip")
    miner.http.download = lambda url, dest: None
    assert m.run_loop(miner, miner.http, ["OSS-Fuzz"], tmp_path, lambda: False, forever=False) == 1


def test_stop_interrupts_idle_sleep(tmp_path):
    miner = make_miner(tmp_path, good_routes())
    _zip_with(tmp_path, OSV, name="OSS-Fuzz.zip")
    miner.http.download = lambda url, dest: None
    state = {"n": 0}

    def stop():
        state["n"] += 1
        return state["n"] > 12   # يُطلب الإيقاف أثناء الانتظار

    sleeps = []
    m.run_loop(miner, miner.http, ["OSS-Fuzz"], tmp_path, stop, forever=True,
               idle_seconds=100000, sleep=sleeps.append)
    assert sum(sleeps) < 100000


def test_deferred_record_is_retried_on_next_pass(tmp_path):
    routes = {"api.github.com/repos/acme/libfoo": REPO_OK, "commit/": m.FetchFailed("down")}
    miner = make_miner(tmp_path, routes)
    _zip_with(tmp_path, OSV, name="OSS-Fuzz.zip")
    miner.http.download = lambda url, dest: None
    m.run_loop(miner, miner.http, ["OSS-Fuzz"], tmp_path, lambda: False, forever=True,
               idle_seconds=1, sleep=lambda s: None, max_passes=1)
    assert miner.counts["deferred"] == 1
    miner.http.routes["commit/"] = PATCH            # عادت الشبكة
    m.run_loop(miner, miner.http, ["OSS-Fuzz"], tmp_path, lambda: False, forever=False)
    assert miner.counts["accepted"] == 1


# ───────────── التشخيص والفشل المنهجي ─────────────

def test_probe_github_rejects_bad_token_and_accepts_good():
    def bad(req, timeout=0):
        raise urllib.error.HTTPError("u", 401, "Bad credentials", {}, None)

    info, err = m.probe_github(m.Http(token="...", opener=bad, sleep=lambda s: None))
    assert info is None and "401" in err

    good = json.dumps({"resources": {"core": {"limit": 5000, "remaining": 4999}}}).encode()
    info, err = m.probe_github(m.Http(token="t", opener=lambda r, timeout=0: _Resp(good)))
    assert err is None and info == {"limit": 5000, "remaining": 4999}


def test_http_401_fails_fast_without_long_retries():
    sleeps = []

    def bad(req, timeout=0):
        raise urllib.error.HTTPError("u", 401, "x", {}, None)

    with pytest.raises(m.FetchFailed):
        m.Http(token="...", opener=bad, sleep=sleeps.append).get_bytes("https://api.github.com/x")
    assert sleeps == []


def test_last_error_recorded_and_status_shows_it(tmp_path):
    routes = {"api.github.com/repos/acme/libfoo": m.FetchFailed("api.github.com -> HTTP 401")}
    miner = make_miner(tmp_path, routes)
    assert miner.process_vuln(OSV) == "deferred"
    assert "401" in miner.last_error
    m.write_status(miner.cfg, miner, "x", "running")
    assert "401" in json.loads((tmp_path / "STATUS.json").read_text())["last_error"]


def test_systemic_failure_triggers_backoff_pause(tmp_path):
    routes = {"api.github.com/repos/acme/libfoo": m.FetchFailed("HTTP 401")}
    miner = make_miner(tmp_path, routes)
    pauses = []
    miner.sleep = pauses.append
    zp = _zip_with(tmp_path, *[{**OSV, "id": f"V-{i}"} for i in range(45)])
    m.run_ecosystem(miner, zp, "x", lambda: False)
    assert miner.counts["deferred"] == 45
    assert pauses.count(60) == 2


# ───────────── ملف الأسرار ─────────────

def test_load_env_token_reads_only_github_token(tmp_path, capsys):
    f = tmp_path / "e.env"
    f.write_text("# c\nHF_TOKEN=hf_" + "a" * 30 + "\r\nexport GITHUB_TOKEN=\"ghp_" + "b" * 30 + "\"\r\nOTHER=1\n")
    tok = m.load_env_token(str(f))
    assert tok == "ghp_" + "b" * 30
    assert capsys.readouterr().out == ""            # لا يطبع شيئاً


def test_load_env_token_missing_or_absent(tmp_path):
    assert m.load_env_token(str(tmp_path / "nope")) is None
    f = tmp_path / "e.env"
    f.write_text("HF_TOKEN=x\nGITHUB_TOKEN=\n")
    assert m.load_env_token(str(f)) is None
    f.write_text("GH_TOKEN='abc123'\n")
    assert m.load_env_token(str(f)) == "abc123"


def test_env_file_overrides_stale_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "...")
    f = tmp_path / "e.env"
    f.write_text("GITHUB_TOKEN=realvalue\n")
    seen = {}
    monkeypatch.setattr(m, "probe_github", lambda http: (seen.setdefault("t", http.token) and {"remaining": 1, "limit": 2}, None))
    monkeypatch.setattr(m, "run_loop", lambda *a, **k: 1)
    m.main(["--once", "--out", str(tmp_path / "o"), "--env-file", str(f)])
    assert seen["t"] == "realvalue"


# ───────────── v1.3: ترخيص من الملف، حصة GitHub، تشخيص ─────────────

MIT_TEXT = ("MIT License\n\nCopyright (c) 2020 X\n\nPermission is hereby granted, free of charge, to any "
            "person obtaining a copy of this software and associated documentation files...")


def test_detect_license_from_text():
    d = m.detect_license_from_text
    assert d(MIT_TEXT) == "mit"
    assert d("Apache License\n Version 2.0, January 2004") == "apache-2.0"
    bsd2 = "Redistribution and use in source and binary forms, with or without modification, are permitted"
    assert d(bsd2) == "bsd-2-clause"
    assert d(bsd2 + " Neither the name of the copyright holder") == "bsd-3-clause"
    assert d(bsd2 + " All advertising materials mentioning features") == "bsd-4-clause"
    assert d("GNU GENERAL PUBLIC LICENSE Version 2") == "gpl"
    assert d("GNU Lesser General Public License") == "lgpl"
    assert d("MIT: Permission is hereby granted, free of charge, to any person obtaining a copy ... "
             "also bundles GNU General Public License code") == "gpl"          # تحفّظ
    assert d("This software is provided 'as-is' ... Altered source versions must be plainly marked") == "zlib"
    assert d("random proprietary text") is None


def test_license_fallback_from_file_recovers_sample(tmp_path):
    nolic = json.dumps({"license": None, "archived": False, "stargazers_count": 500}).encode()
    routes = {"api.github.com/repos/acme/libfoo": nolic,
              "raw.githubusercontent.com/acme/libfoo/HEAD/LICENSE": MIT_TEXT,
              "commit/abc123def456.patch": PATCH}
    miner = make_miner(tmp_path, routes)
    assert miner.process_vuln(OSV) == "accepted:1"
    assert read_samples(tmp_path)[0]["license"] == "mit"


def test_license_fallback_gpl_file_is_rejected(tmp_path):
    nolic = json.dumps({"license": {"spdx_id": "NOASSERTION"}, "archived": False, "stargazers_count": 500}).encode()
    routes = {"api.github.com/repos/acme/libfoo": nolic,
              "raw.githubusercontent.com/acme/libfoo/HEAD/COPYING": "GNU GENERAL PUBLIC LICENSE v3",
              "commit/": PATCH}
    miner = make_miner(tmp_path, routes)
    assert miner.process_vuln(OSV) == "rejected:license_not_allowed:gpl"


def test_stale_cached_meta_gets_license_file_check(tmp_path):
    miner = make_miner(tmp_path, {"raw.githubusercontent.com/acme/libfoo/HEAD/LICENSE": MIT_TEXT,
                                  "commit/": PATCH})
    miner.store.put_repo("acme/libfoo", {"license": None, "archived": False, "stars": 500})  # كاش قديم
    assert miner.repo_meta("acme", "libfoo")["license"] == "mit"
    assert miner.store.get_repo("acme/libfoo")["lf_checked"] is True


def test_fix_diagnosis_reasons(tmp_path):
    miner = make_miner(tmp_path, {})
    nongh = {"id": "A", "affected": [{"ranges": [{"type": "GIT", "repo": "https://gitlab.com/a/b",
                                                   "events": [{"fixed": "abcdef1"}]}]}]}
    nofixed = {"id": "B", "affected": [{"ranges": [{"type": "GIT", "repo": "https://github.com/a/b",
                                                     "events": [{"introduced": "0"}]}]}]}
    assert miner.process_vuln(nongh) == "rejected:no_fix_commit_non_github"
    assert miner.process_vuln(nofixed) == "rejected:no_fix_commit_no_fixed_event"
    assert miner.process_vuln({"id": "C"}) == "rejected:no_fix_commit"


def test_retry_rejected_reopens_only_named_reasons(tmp_path):
    st = m.Store(tmp_path / "s.sqlite")
    st.mark("a", "rejected", "license_missing")
    st.mark("b", "rejected", "repo_archived")
    st.mark("c", "accepted", "3")
    assert st.reset_rejected(["license_missing"]) == 1
    assert not st.is_done("a") and st.is_done("b") and st.is_done("c")
    assert st.reset_rejected([]) == 0


def test_rate_limit_waits_for_reset_without_hammering():
    calls = []
    now = [1000.0]
    reset_hdr = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1100"}

    def opener(req, timeout=0):
        calls.append(req.full_url)
        raise urllib.error.HTTPError("u", 403, "rate limit exceeded", reset_hdr, None)

    h = m.Http(opener=opener, sleep=lambda s: None, now=lambda: now[0])
    with pytest.raises(m.RateLimited) as ei:
        h.get_bytes("https://api.github.com/repos/a/b")
    assert ei.value.reset_at == 1105
    with pytest.raises(m.RateLimited):
        h.get_bytes("https://api.github.com/repos/c/d")       # أثناء الحظر: لا طلب شبكي
    assert len(calls) == 1
    now[0] = 1200.0                                            # بعد إعادة الضبط يُسمح
    with pytest.raises(m.RateLimited):
        h.get_bytes("https://api.github.com/repos/e/f")
    assert len(calls) == 2


def test_run_ecosystem_sleeps_until_reset_then_resumes(tmp_path):
    import time as _t
    exc = m.RateLimited("https://api.github.com/repos/acme/libfoo", _t.time() + 12)
    miner = make_miner(tmp_path, {"api.github.com/repos/acme/libfoo": exc})
    pauses = []
    miner.sleep = pauses.append
    zp = _zip_with(tmp_path, OSV)
    m.run_ecosystem(miner, zp, "x", lambda: False)
    assert miner.counts["deferred"] == 1
    assert sum(pauses) >= 10 and 60 not in pauses
    assert miner.rate_wait_until == 0.0


# ───────────── مفاتيح GITHUB_TOKEN_N ─────────────

def test_load_env_tokens_numbered_ordered_and_others_ignored(tmp_path, capsys):
    f = tmp_path / "e.env"
    f.write_text("\n".join([
        "GROQ_API_KEY_1=gsk_" + "x" * 30, "HF_TOKEN_1=hf_" + "y" * 30,
        "GITHUB_TOKEN_10=ten", "GITHUB_TOKEN_2=two", "GITHUB_TOKEN_1='one'",
        "export GH_TOKEN=base", "GITHUB_TOKEN_3=", "KAGGLE_KEY_1=zzz", ""]))
    assert m.load_env_tokens(str(f)) == ["base", "one", "two", "ten"]
    assert m.load_env_token(str(f)) == "base"
    assert capsys.readouterr().out == ""
    assert m.load_env_tokens(str(tmp_path / "missing")) == []


def test_main_uses_first_valid_token_failover_on_401(tmp_path, monkeypatch):
    f = tmp_path / "e.env"
    f.write_text("GITHUB_TOKEN_1=bad\nGITHUB_TOKEN_2=good\n")
    probed = []

    def fake_probe(http):
        probed.append(http.token)
        return ((None, "x -> HTTP 401") if http.token == "bad" else ({"remaining": 5000, "limit": 5000}, None))

    used = {}
    monkeypatch.setattr(m, "probe_github", fake_probe)
    monkeypatch.setattr(m, "run_loop", lambda miner, http, *a, **k: used.update(tok=http.token) or 1)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    m.main(["--once", "--out", str(tmp_path / "o"), "--env-file", str(f)])
    assert probed == ["bad", "good"] and used["tok"] == "good"


def test_main_all_tokens_rejected_runs_without_token(tmp_path, monkeypatch):
    f = tmp_path / "e.env"
    f.write_text("GITHUB_TOKEN_1=bad\n")
    used = {}
    monkeypatch.setattr(m, "probe_github", lambda http: (None, "HTTP 401"))
    monkeypatch.setattr(m, "run_loop", lambda miner, http, *a, **k: used.update(tok=http.token) or 1)
    m.main(["--once", "--out", str(tmp_path / "o"), "--env-file", str(f)])
    assert used["tok"] is None
