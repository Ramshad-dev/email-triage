import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import outlook_triage as triage  # noqa: E402
from clawlink_mcp import read_api_key  # noqa: E402


class ExtractMessagesTests(unittest.TestCase):
    def test_reads_value_list(self):
        result = {"value": [{"id": "1"}, {"id": "2"}]}
        self.assertEqual(triage.extract_messages(result), [{"id": "1"}, {"id": "2"}])

    def test_reads_messages_key(self):
        result = {"messages": [{"id": "1"}]}
        self.assertEqual(triage.extract_messages(result), [{"id": "1"}])

    def test_reads_clawlink_output_envelope(self):
        result = {"output": {"value": [{"id": "1"}]}}
        self.assertEqual(triage.extract_messages(result), [{"id": "1"}])

    def test_reads_bare_list(self):
        self.assertEqual(triage.extract_messages([{"id": "1"}]), [{"id": "1"}])

    def test_returns_empty_for_unknown_shape(self):
        self.assertEqual(triage.extract_messages({"unexpected": True}), [])


class MailboxTypeTests(unittest.TestCase):
    def test_personal_outlook(self):
        profile = {"mail": "person@outlook.com"}
        self.assertEqual(triage.mailbox_type(profile), "personal")

    def test_work_school(self):
        profile = {"mail": "person@contoso.com"}
        self.assertEqual(triage.mailbox_type(profile), "work/school")

    def test_user_principal_name_fallback(self):
        profile = {"userPrincipalName": "person@hotmail.com"}
        self.assertEqual(triage.mailbox_type(profile), "personal")

    def test_unknown(self):
        self.assertEqual(triage.mailbox_type({}), "unknown")
        self.assertEqual(triage.mailbox_type(None), "unknown")


class ReadApiKeyTests(unittest.TestCase):
    def test_reads_config_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.yaml"
            config.write_text("x-clawlink-api-key: 'secret-value'\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CLAWLINK_API_KEY", None)
                self.assertEqual(read_api_key(config), "secret-value")

    def test_env_value_wins(self):
        with mock.patch.dict(os.environ, {"CLAWLINK_API_KEY": "env-value"}):
            self.assertEqual(
                read_api_key(Path("missing-config.yaml")), "env-value"
            )

    def test_missing_key_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.yaml"
            config.write_text("other: value\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CLAWLINK_API_KEY", None)
                with self.assertRaises(SystemExit):
                    read_api_key(config)


if __name__ == "__main__":
    unittest.main()
