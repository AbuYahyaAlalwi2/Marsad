import contextlib, io, os, tempfile, unittest
from delfin.__main__ import main
from delfin.security.layer import KeyStore


def cli(*args):
    out = io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(out):
            main(list(args))
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        if isinstance(e.code, str):
            out.write(e.code)
    return code, out.getvalue()


class Keys(unittest.TestCase):
    def test_lost_key_recovery_flow(self):
        home = tempfile.mkdtemp()
        _, out = cli("init", "--home", home)
        old_key = [l for l in out.splitlines() if l.startswith("dlf_")][0]
        old_id = [l for l in out.splitlines() if l.startswith("المعرّف")][0].split(": ")[1]
        ks = KeyStore(os.path.join(home, "keys.db"))
        self.assertIsNotNone(ks.verify(old_key))
        # ضاع المفتاح: لا يمكن استرجاعه من أي مكان في الملفات
        for f in os.listdir(home):
            p = os.path.join(home, f)
            if os.path.isfile(p):
                self.assertNotIn(old_key.encode(), open(p, "rb").read(), f)
        # إصدار بديل ثم إلغاء القديم
        _, out2 = cli("newkey", "--home", home, "--name", "admin2", "--scopes", "admin")
        new_key = [l for l in out2.splitlines() if l.startswith("dlf_")][0]
        code, listing = cli("listkeys", "--home", home)
        self.assertIn(old_id, listing)
        self.assertNotIn(old_key, listing + out2.split(new_key)[0])
        self.assertEqual(cli("revoke", "--home", home, "--id", old_id)[0], 0)
        ks = KeyStore(os.path.join(home, "keys.db"))
        self.assertIsNone(ks.verify(old_key))
        self.assertIsNotNone(ks.verify(new_key))
        self.assertIn("ملغى", cli("listkeys", "--home", home)[1])
        self.assertEqual(cli("verify", "--home", home)[0], 0)           # السجل سليم بعد العمليات

    def test_revoke_errors(self):
        home = tempfile.mkdtemp()
        self.assertNotEqual(cli("revoke", "--home", home)[0], 0)
        self.assertNotEqual(cli("revoke", "--home", home, "--id", "deadbeef")[0], 0)
        self.assertNotEqual(cli("newkey", "--home", home, "--scopes", "root")[0], 0)


if __name__ == "__main__":
    unittest.main()
