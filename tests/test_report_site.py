import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("report_site", PROJECT / "scripts/report_site.py")
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


class ReportSiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        (self.root / "uploads").mkdir()
        (self.root / "reports").mkdir()
        shutil.copy2(PROJECT / "site.json", self.root / "site.json")
        shutil.copytree(PROJECT / "web", self.root / "web")
        self.source = Path(self.temp.name) / "report.html"
        self.source.write_text('<!doctype html><meta charset="utf-8"><h1>测试报告</h1>', encoding="utf-8")
        self.output = self.root / "dist"

    def add(self, **kwargs):
        return site.import_report(self.root, self.source, **kwargs)

    def upload(self, filename="2026-10-19.html"):
        target = self.root / "uploads" / filename
        shutil.copy2(self.source, target)
        return target

    def test_empty_site_and_latest(self):
        self.assertEqual(site.build_site(self.root, self.output), [])
        self.assertIn("第一份报告", (self.output / "index.html").read_text())
        self.assertIn("暂无报告", (self.output / "latest/index.html").read_text())

    def test_import_is_byte_preserving(self):
        m = self.add(report_date="2026-10-19", run_id="r1")
        records = site.build_site(self.root, self.output)
        self.assertEqual((self.output / records[0]["url"]).read_bytes(), self.source.read_bytes())
        self.assertEqual(m["status"], "unknown")

    def test_browser_upload_generates_archive_without_changing_source(self):
        self.upload()
        reports = site.build_site(self.root, self.output)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["date"], "2026-10-19")
        self.assertEqual(reports[0]["run_id"], "upload-first")
        self.assertEqual(list((self.root / "reports").iterdir()), [])
        self.assertTrue((self.output / reports[0]["url"]).exists())

    def test_rebuild_stable_and_preserves_all_dates(self):
        self.upload("2026-10-12.html")
        self.upload("2026-10-19.html")
        self.upload("2026-10-19--rerun2.html")
        first = site.build_site(self.root, self.output)
        second = site.build_site(self.root, self.output)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 3)
        self.assertEqual(first[0]["date"], "2026-10-19")
        self.assertIn(first[0]["url"], (self.output / "latest/index.html").read_text())

    def test_directory_with_nondefault_entry_preserves_relative_assets(self):
        bundle = self.root / "uploads/2026-10-19--full"
        (bundle / "nested").mkdir(parents=True)
        (bundle / "nested/report.html").write_text('<link rel="stylesheet" href="../theme.css">')
        (bundle / "theme.css").write_text("body{color:green}")
        (bundle.parent / (bundle.name + ".json")).write_text(json.dumps({"entry": "nested/report.html"}))
        records = site.build_site(self.root, self.output)
        entry = self.output / records[0]["url"]
        self.assertTrue(entry.exists())
        self.assertTrue((entry.parent / "../theme.css").exists())

    def test_metadata_and_escaping(self):
        self.upload()
        data = {"title": '<script>alert(1)</script> {{COUNT}}', "summary": 'a & b', "status": "failed", "metrics": {"passed": 48, "failed": 2, "skipped": 1}}
        (self.root / "uploads/2026-10-19.json").write_text(json.dumps(data))
        records = site.build_site(self.root, self.output)
        page = (self.output / "index.html").read_text()
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("{{COUNT}}", page)
        self.assertIn("a &amp; b", page)
        self.assertEqual(records[0]["metrics"]["failed"], 2)

    def test_archive_duplicate_rejected(self):
        self.add(report_date="2026-10-19", run_id="r1")
        with self.assertRaises(ValueError):
            self.add(report_date="2026-10-19", run_id="r1")

    def test_invalid_dates_and_paths(self):
        for date in ("2026-02-30", "2026-1-1"):
            with self.assertRaises(ValueError):
                self.add(report_date=date)
        for run_id in ("../../outside", "bad id", ".hidden"):
            with self.assertRaises(ValueError):
                self.add(run_id=run_id)
        for entry in ("../report.html", "/tmp/report.html", "a\\b.html"):
            with self.assertRaises(ValueError):
                site.safe_entry(entry)

    def test_missing_and_empty_report(self):
        with self.assertRaises(ValueError):
            site.import_report(self.root, self.source.parent / "missing.html")
        self.source.write_text("")
        with self.assertRaises(ValueError):
            self.add()

    def test_symbolic_link_and_hidden_files_rejected(self):
        bundle = Path(self.temp.name) / "bundle"
        bundle.mkdir()
        (bundle / "index.html").symlink_to(self.source)
        with self.assertRaises(ValueError):
            site.import_report(self.root, bundle)
        (bundle / "index.html").unlink()
        shutil.copy2(self.source, bundle / "index.html")
        (bundle / ".env").write_text("dummy")
        with self.assertRaises(ValueError):
            site.import_report(self.root, bundle)

    def test_inconsistent_statistics_rejected(self):
        with self.assertRaises(ValueError):
            self.add(status="passed", metrics={"passed": 2, "failed": 1, "skipped": 0})
        for metrics in ({"passed": -1, "failed": 0, "skipped": 0}, {"passed": True, "failed": 0, "skipped": 0}, {"total": 2}):
            with self.assertRaises(ValueError):
                self.add(metrics=metrics)

    def test_archive_corruption_does_not_replace_existing_site(self):
        self.add(report_date="2026-10-19", run_id="r1")
        site.build_site(self.root, self.output)
        before = (self.output / "index.html").read_bytes()
        (self.root / "reports/2026-10-19/r1/html/report.html").write_text("changed")
        with self.assertRaises(ValueError):
            site.build_site(self.root, self.output)
        self.assertEqual((self.output / "index.html").read_bytes(), before)

    def test_source_and_unknown_output_directories_protected(self):
        for target in (self.root, self.root / "uploads", self.root / "web", self.root.parent):
            with self.assertRaises(ValueError):
                site.build_site(self.root, target)
        self.output.mkdir()
        (self.output / "unrelated.txt").write_text("keep")
        with self.assertRaises(ValueError):
            site.build_site(self.root, self.output)
        self.assertTrue((self.output / "unrelated.txt").exists())

    def test_bad_upload_and_orphan_metadata_fail_loudly(self):
        bad = self.upload("bad-name.html")
        with self.assertRaises(ValueError):
            site.build_site(self.root, self.output)
        bad.unlink()
        (self.root / "uploads/2026-10-19.json").write_text("{}")
        with self.assertRaises(ValueError):
            site.build_site(self.root, self.output)


if __name__ == "__main__":
    unittest.main()
