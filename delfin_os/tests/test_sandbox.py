import os, unittest
from delfin.sandbox.executor import LocalSandbox, RemoteSandbox


class Sandbox(unittest.TestCase):
    def test_locked_by_default(self):
        r = LocalSandbox().run_python("print(1)")
        self.assertEqual(r["status"], "refused")

    def test_dev_mode(self):
        sb = LocalSandbox(dev_mode=True, require_network_isolation=False)
        os.environ["SECRET_X"] = "topsecret"
        self.assertEqual(sb.run_python("print(2+2)")["stdout"].strip(), "4")
        env = sb.run_python("import os;print(os.environ.get('SECRET_X'), len(os.environ))")["stdout"]
        self.assertTrue(env.startswith("None"))
        self.assertEqual(sb.run_python("while True: pass", timeout=2)["status"], "timeout")
        self.assertIn(sb.run_python("x='a'*(10**9)")["status"], ("error", "memory"))
        self.assertEqual(sb.run_python("raise SystemExit(3)")["status"], "error")
        self.assertLessEqual(len(sb.run_python("print('a'*100000)")["stdout"]), 20000)

    def test_memory_watchdog_alone(self):
        """نظام لا يصلح فيه حد الذاكرة (مثل Android): المراقب وحده يجب أن يقتل التسريب التدريجي."""
        sb = LocalSandbox(dev_mode=True, require_network_isolation=False, use_rlimit_mem=False, mem_mb=128)
        r = sb.run_python("l=[]\nwhile True:\n    l.append(b'x'*(10**7))", timeout=20)
        self.assertEqual(r["status"], "memory")
        self.assertEqual(r["mem_mode"], "watchdog")
        self.assertEqual(sb.run_python("print(7)")["stdout"].strip(), "7")

    def test_refuses_without_any_mem_limit(self):
        sb = LocalSandbox(dev_mode=True, require_network_isolation=False, use_rlimit_mem=False)
        import delfin.sandbox.executor as ex
        orig, ex._rss = ex._rss, (lambda pid: None)
        try:
            self.assertEqual(sb.run_python("print(1)")["status"], "refused")
        finally:
            ex._rss = orig

    def test_net_requirement(self):
        sb = LocalSandbox(dev_mode=True, require_network_isolation=True)
        r = sb.run_python("print(1)")
        if sb.netns:
            self.assertEqual(r["stdout"].strip(), "1")
            net = sb.run_python("import socket\ns=socket.socket();s.settimeout(2)\n"
                                "try:\n s.connect(('1.1.1.1',80));print('CONNECTED')\nexcept Exception:\n print('BLOCKED')")
            self.assertEqual(net["stdout"].strip(), "BLOCKED")
        else:
            self.assertEqual(r["status"], "refused")

    def test_remote_requires_https(self):
        with self.assertRaises(ValueError):
            RemoteSandbox("http://x.com", "t")


if __name__ == "__main__":
    unittest.main()
