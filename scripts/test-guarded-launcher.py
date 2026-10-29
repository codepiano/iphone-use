#!/usr/bin/env python3
"""Check credential binding without starting a daemon or sending input."""
import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("launcher", Path(__file__).with_name("run-guarded.py"))
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.path = self.home / "Library/LaunchAgents/com.leeguoo.iphone-use.plist"
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(plistlib.dumps({"EnvironmentVariables": {
            "IPHONE_USE_PORT": "44321", "IPHONE_USE_AGENT_TOKEN": "fixture-private-token"}}))

    def test_local_origin_gets_its_configured_credential(self):
        env = launcher.local_environment({}, self.home)
        self.assertEqual(env["IPHONE_USE_URL"], "http://127.0.0.1:44321")
        self.assertEqual(env["IPHONE_USE_AGENT_TOKEN"], "fixture-private-token")

    def test_never_exports_local_credential_to_another_origin(self):
        for url in ("https://example.test", "http://127.0.0.1:44322",
                    "http://user@127.0.0.1:44321", "http://127.0.0.1:44321/other"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                launcher.local_environment({"IPHONE_USE_URL": url}, self.home)

    def test_explicit_remote_credential_does_not_get_replaced(self):
        env = launcher.local_environment({"IPHONE_USE_URL": "https://example.test",
            "IPHONE_USE_AGENT_TOKEN": "explicit-fixture-token"}, self.home)
        self.assertEqual(env["IPHONE_USE_AGENT_TOKEN"], "explicit-fixture-token")

    def test_named_instance_does_not_borrow_default_instance_token(self):
        with self.assertRaises(ValueError):
            launcher.local_environment({"IPHONE_USE_INSTANCE": "second"}, self.home)

    def test_instance_cannot_escape_configuration_directory(self):
        with self.assertRaises(ValueError):
            launcher.local_environment({"IPHONE_USE_INSTANCE": "../other"}, self.home)


if __name__ == "__main__":
    unittest.main()
