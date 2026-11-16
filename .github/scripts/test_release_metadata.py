import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, call


MODULE_PATH = Path(__file__).with_name("release_metadata.py")
SPEC = importlib.util.spec_from_file_location("release_metadata", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


RELEASE_SUMMARY = """<!-- release-summary:start -->
## English
### Highlights
Repository release automation now requires a detailed summary.
### Behavior and why
No Hamartia user behavior changes; this documents what the release will contain.
### How to use
No new user action is needed.
### Compatibility / migration
No data or API compatibility changes.
### Verification
The release metadata tests passed.
### Not run / known limitations
No full package build was run for this documentation-only change.
## Türkçe
### Öne çıkanlar
Sürüm otomasyonu artık ayrıntılı bir özet gerektiriyor.
### Davranış ve nedeni
Hamartia kullanıcı davranışı değişmedi; sürüm içeriği belgeleniyor.
### Kullanım
Yeni bir kullanıcı işlemi gerekmiyor.
### Uyumluluk / geçiş
Veri veya API uyumluluğu değişmedi.
### Doğrulama
Sürüm metadata testleri geçti.
### Çalıştırılmayanlar / bilinen sınırlamalar
Bu yalnızca belge değişikliği için tam paket derlemesi çalıştırılmadı.
<!-- release-summary:end -->"""


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
            "body": RELEASE_SUMMARY,
        }
        self.assertIsNone(module.find_merged_pull_request([{
            **pull, "state": "open", "merged_at": None,
        }]))
        self.assertEqual(module.find_merged_pull_request([pull]), pull)
        notes = module.render_notes("ARETE-001", pull)
        self.assertIn("## English", notes)
        self.assertIn("## Türkçe", notes)
        self.assertIn("PR #42", notes)
        self.assertIn("### Compatibility / migration", notes)
        self.assertIn("### Uyumluluk / geçiş", notes)
        self.assertIn("No Hamartia user behavior changes", notes)
        self.assertIn("Hamartia kullanıcı davranışı değişmedi", notes)
        for field in module.RELEASE_SUMMARY_FIELDS:
            self.assertEqual(notes.count(f"### {field}"), 1)
        for field in module.TURKISH_RELEASE_FIELDS.values():
            self.assertEqual(notes.count(f"### {field}"), 1)
        release = {"tag_name": "ARETE-001", "body": notes}
        self.assertEqual(module.existing_release_for_pull_request([release], pull["html_url"]), release)
        ledger = module.append_release_content("# Releases / Sürümler\n", "ARETE-001", notes)
        self.assertIn("## ARETE-001", ledger)
        self.assertIn("## Türkçe", ledger)
        self.assertEqual(module.append_release_content(ledger, "ARETE-001", notes), ledger)

    def test_release_summary_requires_all_fields_in_both_languages(self):
        self.assertEqual(set(module.parse_release_summary(RELEASE_SUMMARY)), {"English", "Türkçe"})
        incomplete = RELEASE_SUMMARY.replace("No new user action is needed.", "")
        with self.assertRaisesRegex(ValueError, "English release summary has empty or missing fields: How to use"):
            module.render_notes("ARETE-001", {
                "number": 42, "title": "Docs", "html_url": "https://example.test/pr/42", "body": incomplete,
            })
        incomplete_turkish = RELEASE_SUMMARY.replace("Yeni bir kullanıcı işlemi gerekmiyor.", "")
        with self.assertRaisesRegex(ValueError, "Türkçe release summary has empty or missing fields: How to use"):
            module.render_notes("ARETE-001", {
                "number": 42, "title": "Docs", "html_url": "https://example.test/pr/42", "body": incomplete_turkish,
            })
        with self.assertRaisesRegex(ValueError, "marked bilingual release summary"):
            module.parse_release_summary("")

    def test_release_assets_detect_and_repair_missing_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact_paths = [Path(directory) / name for name in (
                "Hamartia-win-x64.exe", "Hamartia-linux-x64.deb", "Hamartia-linux-x64.AppImage",
            )]
            for path in artifact_paths:
                path.touch()
            release = {"assets": [{"name": "Hamartia-win-x64.exe"}, {"name": "Hamartia-linux-x64.AppImage"}]}
            missing = module.missing_release_assets(release, artifact_paths)
            self.assertEqual([path.suffix.lower() for path in missing], [".deb"])
            completed = {"assets": [{"name": path.name} for path in artifact_paths]}
            self.assertEqual(module.missing_release_assets(completed, artifact_paths), [])
            module.validate_artifacts(artifact_paths)
            with patch.object(module.subprocess, "run") as run, patch.object(module, "fetch_release", return_value=completed):
                self.assertEqual(module.ensure_release_assets("ARETE-001", release, artifact_paths), completed)
                self.assertEqual(run.call_args.args[0], ["gh", "release", "upload", "ARETE-001", str(artifact_paths[1])])
            with patch.object(module.subprocess, "run"), patch.object(module, "fetch_release", return_value=release):
                with self.assertRaisesRegex(RuntimeError, "still missing required assets"):
                    module.ensure_release_assets("ARETE-001", release, artifact_paths)
            with self.assertRaisesRegex(RuntimeError, "Missing release package artifacts: .deb"):
                module.validate_artifacts([artifact_paths[0], artifact_paths[2]])

    def test_first_publication_creates_release_and_fetches_its_assets(self):
        pull = {
            "number": 42,
            "title": "Ship the desktop app",
            "html_url": "https://github.com/Nec0ti/hamartia/pull/42",
            "state": "closed",
            "merged_at": "2026-11-14T19:00:00Z",
            "body": RELEASE_SUMMARY,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pulls_path = root / "pulls.json"
            pulls_path.write_text(json.dumps([pull]))
            artifacts = root / "artifacts"
            artifacts.mkdir()
            for name in ("Hamartia-win-x64.exe", "Hamartia-linux-x64.deb", "Hamartia-linux-x64.AppImage"):
                (artifacts / name).touch()
            notes_path = root / "notes.md"
            output_path = root / "github-output"
            created_release = {
                "tag_name": "ARETE-001",
                "body": module.render_notes("ARETE-001", pull),
                "assets": [{"name": path.name} for path in artifacts.iterdir()],
            }

            def fake_check_output(command, **_kwargs):
                if command[0:2] == ["gh", "api"]:
                    return "[[]]"
                if command[0:3] == ["git", "tag", "--list"]:
                    return ""
                raise AssertionError(f"Unexpected command: {command}")

            with patch.dict(os.environ, {"GITHUB_REPOSITORY": "Nec0ti/hamartia"}), \
                 patch.object(module.subprocess, "check_output", side_effect=fake_check_output), \
                 patch.object(module.subprocess, "run", return_value=module.subprocess.CompletedProcess([], 0, "", "")) as run, \
                 patch.object(module, "fetch_release", return_value=created_release):
                module.publish_release(pulls_path, artifacts, "abc123", notes_path, output_path)

            create_call = next(item for item in run.call_args_list if item.args[0][:3] == ["gh", "release", "create"])
            self.assertIn("ARETE-001", create_call.args[0])
            self.assertEqual(output_path.read_text(), "tag=ARETE-001\npr_number=42\n")
            self.assertIn("## English", notes_path.read_text(encoding="utf-8"))
            self.assertIn("## Türkçe", notes_path.read_text(encoding="utf-8"))
            self.assertIn("Sürüm otomasyonu artık ayrıntılı bir özet gerektiriyor", notes_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
