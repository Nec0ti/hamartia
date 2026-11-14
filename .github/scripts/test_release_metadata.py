import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("release_metadata.py")
SPEC = importlib.util.spec_from_file_location("release_metadata", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ReleaseMetadataTests(unittest.TestCase):
    def test_release_codes_increment_numeric_arete_tags(self):
        self.assertEqual(module.next_arete_code([]), "ARETE-001")
        self.assertEqual(module.next_arete_code(["ARETE-002", "v9.0.0", "ARETE-010"]), "ARETE-011")

    def test_only_a_merged_pull_request_creates_release_notes(self):
        pull = {
            "number": 42,
            "title": "Ship the desktop app",
            "html_url": "https://github.com/Nec0ti/hamartia/pull/42",
            "state": "closed",
            "merged_at": "2026-11-14T19:00:00Z",
        }
        self.assertIsNone(module.find_merged_pull_request([{
            **pull, "state": "open", "merged_at": None,
        }]))
        self.assertEqual(module.find_merged_pull_request([pull]), pull)
        notes = module.render_notes("ARETE-001", pull)
        self.assertIn("## English", notes)
        self.assertIn("## Türkçe", notes)
        self.assertIn("PR #42", notes)
        release = {"tag_name": "ARETE-001", "body": notes}
        self.assertEqual(module.existing_release_for_pull_request([release], pull["html_url"]), release)
        ledger = module.append_release_content("# Releases / Sürümler\n", "ARETE-001", notes)
        self.assertIn("## ARETE-001", ledger)
        self.assertIn("## Türkçe", ledger)
        self.assertEqual(module.append_release_content(ledger, "ARETE-001", notes), ledger)


if __name__ == "__main__":
    unittest.main()
