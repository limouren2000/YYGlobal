import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import scan_secrets


class SecretScannerTests(unittest.TestCase):
    def test_failure_output_redacts_secret_value(self) -> None:
        secret = "AKIA" + "0123456789ABCDEF"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".gitignore").write_text(".env\n.env.*\n", encoding="utf-8")
            (root / "config.txt").write_text(f"AWS_ACCESS_KEY_ID={secret}\n", encoding="utf-8")
            output = io.StringIO()

            with patch.object(scan_secrets, "ROOT", root), redirect_stdout(output):
                with self.assertRaises(SystemExit) as raised:
                    scan_secrets.main()

            self.assertEqual(raised.exception.code, 1)
            self.assertIn("config.txt:1 [AWS access key]", output.getvalue())
            self.assertNotIn(secret, output.getvalue())

    def test_placeholder_value_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "example.txt"
            path.write_text("OPENAI_API_KEY=sk-example1234567890123456\n", encoding="utf-8")

            with patch.object(scan_secrets, "ROOT", root):
                self.assertEqual(scan_secrets.scan_file(path), [])


if __name__ == "__main__":
    unittest.main()
