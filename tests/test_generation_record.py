"""No downloads or model execution: audit the adjunct experiment's saved evidence."""

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

EXPERIMENT = Path(__file__).resolve().parents[1] / "experiments/local-generation-smoke"


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, EXPERIMENT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GenerationRecordTests(unittest.TestCase):
    def test_record_is_consistent_and_all_three_strict_checks_failed(self):
        result = load_module("verify_recorded").verify_recorded()
        self.assertEqual(result["record_integrity"], "verified")
        self.assertEqual((result["strict_pass_count"], result["case_count"]), (0, 3))

    def test_exact_abstention_does_not_normalize_punctuation_or_spaces(self):
        check = load_module("verify_recorded").format_checks
        self.assertTrue(check("unsupported", "INSUFFICIENT_EVIDENCE")["exact_abstention_marker"])
        for content in ("INSUFFICIENT_EVIDENCE.", " INSUFFICIENT_EVIDENCE", ""):
            self.assertFalse(check("unsupported", content)["exact_abstention_marker"])

    def test_required_citation_is_literal_not_a_claim_of_semantic_quality(self):
        check = load_module("verify_recorded").format_checks
        self.assertFalse(check("english_supported", "S1.")["required_citation"])
        self.assertTrue(check("english_supported", "[S1]")["required_citation"])

    def test_tampered_response_is_rejected(self):
        module = load_module("verify_recorded")
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "experiment"
            target.mkdir()
            for name in ("cases.json", "run_smoke.py"):
                shutil.copy2(EXPERIMENT / name, target / name)
            shutil.copytree(EXPERIMENT / "recorded", target / "recorded")
            (target / "recorded/unsupported-response.raw.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Raw response changed"):
                module.verify_recorded(target)

    def test_download_checksum_rejects_wrong_bytes(self):
        verify = load_module("prepare").verify
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample"
            path.write_bytes(b"fixture")
            verify(path, 7, hashlib.sha256(b"fixture").hexdigest())
            with self.assertRaises(ValueError):
                verify(path, 8, hashlib.sha256(b"fixture").hexdigest())
            with self.assertRaises(ValueError):
                verify(path, 7, hashlib.sha256(b"different").hexdigest())

    def test_record_cli_is_offline_and_reports_failed_model_checks(self):
        result = subprocess.run([sys.executable, str(EXPERIMENT / "verify_recorded.py")],
                                capture_output=True, text=True, check=True, timeout=10)
        self.assertEqual(json.loads(result.stdout)["strict_pass_count"], 0)


if __name__ == "__main__":
    unittest.main()
