import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import publish_report as publisher

REPORT = b'''<!doctype html><meta charset="utf-8"><title>Example</title><style>table{width:100%}</style><h1>EXAMPLE</h1><h2>SUMMARY</h2><div class="table-wrap"><table><tr><td>data</td></tr></table></div>'''


def lch_report(failed=2, title="失败 / G2 通过"):
    return REPORT.decode().replace("EXAMPLE", "LCH 全量回归 · " + title).replace(
        "SUMMARY", f"确定性：成功 87，失败 0；真实模型：成功 62，失败 {failed}").encode()


class Clock:
    def __init__(self): self.tick = 0
    def now(self): return self.tick
    def sleep(self, seconds): self.tick += seconds


class PublishTests(unittest.TestCase):
    def test_adaptation_idempotent_and_does_not_modify_links(self):
        raw = lch_report() + b'<a href="file:///example">attachment</a>'
        data, meta, count = publisher.prepare_report(raw, "2026-10-19")
        again, _, _ = publisher.prepare_report(data, "2026-10-19")
        self.assertEqual(data, again)
        self.assertEqual(count, 1)
        self.assertEqual(meta["status"], "failed")
        self.assertEqual(publisher.parse_html(raw.decode()).links, publisher.parse_html(data.decode()).links)
        self.assertIn(b'report-mobile-layout', data)

    def test_unknown_format_never_becomes_passed(self):
        _, meta, _ = publisher.prepare_report(REPORT, "2026-10-19")
        self.assertEqual(meta["status"], "unknown")
        _, meta, _ = publisher.prepare_report(lch_report(0, "通过 / G2 通过"), "2026-10-19")
        self.assertEqual(meta["status"], "passed")
        _, meta, _ = publisher.prepare_report(lch_report(0, "通过 / G2 失败"), "2026-10-19")
        self.assertEqual(meta["status"], "failed")

    def test_duplicate_keeps_reviewed_metadata_and_conflict_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertTrue(publisher.write_report(root, "2026-10-19.html", REPORT, {"title": "reviewed"}))
            self.assertFalse(publisher.write_report(root, "2026-10-19.html", REPORT, {"title": "new"}))
            self.assertEqual(json.loads((root / "uploads/2026-10-19.json").read_text())["title"], "reviewed")
            with self.assertRaises(publisher.PublishError):
                publisher.write_report(root, "2026-10-19.html", REPORT + b"changed", {})
            self.assertEqual((root / "uploads/2026-10-19.html").read_bytes(), REPORT)
            self.assertTrue(publisher.write_report(root, "2026-10-19--r2.html", REPORT + b"changed", {}))

    def test_failed_deployment_is_not_reported_as_success(self):
        def gh(*args):
            if args[:2] == ("run", "list"):
                return json.dumps([{"databaseId": 1, "headSha": "abc", "status": "completed", "conclusion": "failure", "url": "run/1", "event": "push"}])
            return json.dumps({"head_sha": "abc", "status": "completed", "conclusion": "failure", "run_attempt": 1})
        clock = Clock()
        with self.assertRaisesRegex(publisher.PublishError, "failure"):
            publisher.wait_workflow(gh, "a/b", "pages.yml", "main", "abc", 30, False, clock.sleep, clock.now)

    def test_retry_waits_for_new_attempt_not_old_failure(self):
        rerun = []
        reads = []
        def gh(*args):
            if args[:2] == ("run", "list"):
                return json.dumps([{"databaseId": 1, "headSha": "abc", "status": "completed", "conclusion": "failure", "url": "run/1", "event": "push"}])
            if args[:2] == ("run", "rerun"):
                rerun.append(True); return ""
            reads.append(True)
            attempt = 1 if len(reads) <= 2 else 2
            return json.dumps({"head_sha": "abc", "status": "completed", "conclusion": "failure" if attempt == 1 else "success", "run_attempt": attempt})
        clock = Clock()
        self.assertEqual(publisher.wait_workflow(gh, "a/b", "pages.yml", "main", "abc", 30, True, clock.sleep, clock.now), "run/1")
        self.assertEqual(len(rerun), 1)
        self.assertEqual(clock.tick, 5)

    def test_does_not_accept_another_commit_success(self):
        def gh(*args):
            return json.dumps([{"databaseId": 2, "headSha": "other", "status": "completed", "conclusion": "success", "url": "run/2", "event": "push"}])
        clock = Clock()
        with self.assertRaisesRegex(publisher.PublishError, "超时"):
            publisher.wait_workflow(gh, "a/b", "pages.yml", "main", "abc", 10, False, clock.sleep, clock.now)

    def test_online_verification_rejects_wrong_html_and_handles_backfill(self):
        record = {"date": "2026-10-12", "run_id": "upload-first", "url": "reports/old.html"}
        latest = {"date": "2026-10-19", "run_id": "upload-first", "url": "reports/new.html"}
        base = "https://example.test/site/"
        responses = {
            "reports.json": json.dumps([latest, record]).encode(),
            "reports/old.html": REPORT,
            "index.html": b'<a href="reports/old.html">older</a>',
            "latest/index.html": b'<meta http-equiv="refresh" content="0;url=../reports/new.html">',
            "assets/site.css": b"style",
        }
        fetch = lambda url: responses[url.removeprefix(base).split("?")[0]]
        clock = Clock()
        publisher.verify_site(base, "abc", [latest, record], record, REPORT,
                              {"assets/site.css": b"style"}, 10, fetch, clock.sleep, clock.now)
        responses["reports/old.html"] = b"stale report"
        with self.assertRaisesRegex(publisher.PublishError, "HTML"):
            publisher.verify_site(base, "abc", [latest, record], record, REPORT, {}, 10, fetch, clock.sleep, clock.now)

    def test_new_publish_uses_isolated_clone_and_repeat_makes_no_commit(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            temporary = Path(tmp)
            local = temporary / "local"
            remote = temporary / "remote.git"
            local.mkdir()
            execute = lambda *cmd, cwd=local: subprocess.check_output(cmd, cwd=cwd, stderr=subprocess.DEVNULL, text=True).strip()
            execute("git", "init", "--bare", str(remote))
            execute("git", "init", "-b", "main")
            execute("git", "config", "user.name", "fixture")
            execute("git", "config", "user.email", "fixture@example.test")
            shutil.copytree(publisher.ROOT / "web", local / "web")
            shutil.copy2(publisher.ROOT / "site.json", local / "site.json")
            (local / ".gitignore").write_text("incoming/\ndist/\n")
            (local / "publish.json").write_text(json.dumps({"repository": "fixture/reports", "branch": "main", "workflow": "pages.yml", "ssh_host": "LCH", "remote_directory": "/reports"}))
            execute("git", "add", ".")
            execute("git", "commit", "-m", "fixture")
            execute("git", "remote", "add", "origin", str(remote))
            execute("git", "push", "origin", "main")
            old_head = execute("git", "rev-parse", "HEAD")
            (local / "site.json").write_text('{"unrelated": "uncommitted"}')
            real_run = publisher.run
            fail_push = [True]
            def fake_run(args, cwd=None, timeout=120):
                args = list(args)
                if args[0] == "fake-gh":
                    if args[1:] == ["api", "user"]: return '{"login":"fixture","id":1}'
                    return '{"html_url":"https://example.test/reports/"}'
                if args[0] == "scp":
                    Path(args[-1]).write_bytes(lch_report()); return ""
                if "clone" in args:
                    args[args.index("https://github.com/fixture/reports.git")] = str(remote)
                if args[0] == "git" and "push" in args and fail_push[0]:
                    fail_push[0] = False
                    raise publisher.PublishError("simulated network failure")
                return real_run(args, cwd or local, timeout)
            args = Namespace(date="2026-10-19", run_id=None, check_only=False, gh=None, timeout=30)
            with patch.object(publisher, "ROOT", local), patch.object(publisher, "run", side_effect=fake_run), patch.object(publisher, "find_gh", return_value="fake-gh"), patch.object(publisher, "wait_workflow", return_value="https://example.test/run/1"), patch.object(publisher, "verify_site") as verify:
                with self.assertRaisesRegex(publisher.PublishError, "推送失败"):
                    publisher.publish(args)
                self.assertEqual(execute("git", "--git-dir", str(remote), "rev-parse", "main"), old_head)
                publisher.publish(args)
                first_head = execute("git", "--git-dir", str(remote), "rev-parse", "main")
                publisher.publish(args)
                second_head = execute("git", "--git-dir", str(remote), "rev-parse", "main")
                self.assertEqual(verify.call_count, 2)
            self.assertEqual(first_head, second_head)
            self.assertEqual(execute("git", "rev-parse", "HEAD"), old_head)
            self.assertIn("unrelated", (local / "site.json").read_text())
            changed = execute("git", "--git-dir", str(remote), "diff-tree", "--no-commit-id", "--name-only", "-r", first_head).splitlines()
            self.assertEqual(changed, ["uploads/2026-10-19.html", "uploads/2026-10-19.json"])


if __name__ == "__main__":
    unittest.main()
