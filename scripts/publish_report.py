#!/usr/bin/env python3
"""Publish a reviewed LCH report and verify its deployed contents. Standard library only."""
import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from report_site import ROOT, MAX_BYTES, build_site

MOBILE_STYLE = '''
<style id="report-mobile-layout">
@media (max-width: 720px) {
  body { margin: 16px auto; padding: 0 12px; overflow-wrap: anywhere; }
  section { padding: 16px; margin: 16px 0; min-width: 0; }
  h1 { font-size: 24px; }
  h2 { font-size: 20px; }
  nav { gap: 12px 18px; }
  .table-wrap { max-width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .table-wrap table { min-width: 760px; }
  pre { max-width: 100%; box-sizing: border-box; }
}
</style>
'''


class PublishError(Exception):
    pass


def run(args, cwd=ROOT, timeout=120):
    result = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True,
                            text=True, timeout=timeout)
    if result.returncode:
        raise PublishError((result.stderr or result.stdout).strip() or f"命令失败：{args[0]}")
    return result.stdout.strip()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_source(args, config, working):
    if args.local or args.local_dir is not None:
        directory = Path(args.local_dir if args.local_dir is not None else config["remote_directory"]).expanduser()
        source = directory / (args.date + ".html")
        if not source.is_file():
            raise PublishError(f"本机报告不存在：{source}")
        print(f"读取本机报告：{source}", flush=True)
    else:
        source = working / "source.html"
        remote_path = config["remote_directory"].rstrip("/") + "/" + args.date + ".html"
        run(["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
             f"{config['ssh_host']}:{remote_path}", str(source)], timeout=180)
    # Read only this date, leave the original unchanged, and bound memory use.
    with source.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if not raw or len(raw) > MAX_BYTES:
        raise PublishError("报告为空或超过 100 MiB")
    return raw


class ReportHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.headings = {"title": [], "h1": [], "h2": []}
        self.capture = None
        self.fragments = []
        self.links = []
        self.redirect = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in self.headings:
            self.capture, self.fragments = tag, []
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "meta" and attrs.get("http-equiv", "").lower() == "refresh":
            match = re.search(r"url=(.+)$", attrs.get("content", ""), re.I)
            if match:
                self.redirect = match[1].strip()

    def handle_data(self, data):
        if self.capture:
            self.fragments.append(data)

    def handle_endtag(self, tag):
        if tag == self.capture:
            self.headings[tag].append("".join(self.fragments).strip())
            self.capture = None


def parse_html(text):
    parsed = ReportHTML()
    parsed.feed(text)
    return parsed


def prepare_report(raw, report_date):
    if not raw or len(raw) > MAX_BYTES:
        raise PublishError("报告为空或超过 100 MiB")
    text = raw.decode("utf-8")
    parsed = parse_html(text)
    if not parsed.headings["title"] and not parsed.headings["h1"]:
        raise PublishError("报告缺少 title/h1，无法确认为有效报告 HTML")
    title = (parsed.headings["h1"] or parsed.headings["title"])[0]
    meta = {"title": f"{title} · {report_date}", "status": "unknown", "summary": ""}
    # Recognize only the known LCH summary; unknown formats never become 'passed'.
    pattern = r"确定性[：:]\s*成功\s*(\d+)\s*[，,]\s*失败\s*(\d+)\s*[；;]\s*真实模型[：:]\s*成功\s*(\d+)\s*[，,]\s*失败\s*(\d+)"
    matches = [re.fullmatch(pattern, heading) for heading in parsed.headings["h2"]]
    match = next((value for value in matches if value), None)
    if match:
        dp, df, lp, lf = map(int, match.groups())
        meta["title"] = f"LCH 全量回归报告 · {report_date}"
        meta["summary"] = f"确定性测试 {dp} 成功、{df} 失败；真实模型测试 {lp} 成功、{lf} 失败。"
        if df or lf or "失败" in title:
            meta["status"] = "failed"
        elif "通过" in title:
            meta["status"] = "passed"
        if "G2 通过" in title:
            meta["summary"] += "G2 消息结构规则校验通过。"
        elif "G2 失败" in title:
            meta["summary"] += "G2 消息结构规则校验失败。"
        # This adaptation applies only to the known report template.
        if 'class="table-wrap"' in text and 'id="report-mobile-layout"' not in text:
            if "</style>" in text:
                text = text.replace("</style>", "</style>" + MOBILE_STYLE, 1)
    local_links = sum(link.startswith("file:") for link in parsed.links)
    return text.encode("utf-8"), meta, local_links


def write_report(checkout, filename, data, meta):
    target = checkout / "uploads" / filename
    if target.exists():
        if target.read_bytes() != data:
            raise PublishError("该日期/版本的报告已存在且内容不同。旧报告未覆盖；请添加 --run-id r2 发布另一版本。")
        # Keep any manually reviewed metadata on repeat runs.
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    target.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    return True


def wait_workflow(gh, repo, workflow, branch, sha, timeout, reuse, sleep=time.sleep, now=time.monotonic):
    deadline = now() + timeout
    started = now()
    dispatched = False
    chosen = None
    minimum_attempt = 1
    while now() < deadline:
        if chosen is None:
            runs = json.loads(gh("run", "list", "--repo", repo, "--workflow", workflow,
                                 "--commit", sha, "--branch", branch, "--limit", "20",
                                 "--json", "databaseId,headSha,status,conclusion,url,event"))
            candidates = [r for r in runs if r["headSha"] == sha and r.get("event") in ("push", "workflow_dispatch")]
            if candidates:
                chosen = max(candidates, key=lambda r: r["databaseId"])
                print(f"工作流：{chosen['url']}", flush=True)
                if reuse and chosen["status"] == "completed" and chosen["conclusion"] != "success":
                    previous = json.loads(gh("api", f"repos/{repo}/actions/runs/{chosen['databaseId']}"))
                    minimum_attempt = previous["run_attempt"] + 1
                    gh("run", "rerun", str(chosen["databaseId"]), "--repo", repo)
                    print("重新运行此前未成功的部署。", flush=True)
            elif not dispatched and now() - started >= 45:
                # Never dispatch another commit by accident if main moved meanwhile.
                current = json.loads(gh("api", f"repos/{repo}/commits/{branch}"))["sha"]
                if current != sha:
                    raise PublishError("远端 main 已更新，请重新执行以检查最新提交。")
                gh("workflow", "run", workflow, "--repo", repo, "--ref", branch)
                dispatched = True
        if chosen:
            state = json.loads(gh("api", f"repos/{repo}/actions/runs/{chosen['databaseId']}"))
            if state["head_sha"] != sha:
                raise PublishError("工作流提交与本次提交不一致")
            if state.get("run_attempt", 1) >= minimum_attempt and state["status"] == "completed":
                if state["conclusion"] != "success":
                    raise PublishError(f"部署未成功（{state['conclusion']}）：{chosen['url']}。修复后重跑本命令即可。")
                return chosen["url"]
        sleep(5)
    raise PublishError("等待部署超时；报告已提交时无需重新上传，稍后重跑本命令即可检查或重试。")


def get_url(url):
    with urlopen(Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "Regression-Report-Publisher"}), timeout=20) as response:
        return response.read()


def verify_site(base, sha, records, record, expected_html, assets, timeout=180,
                fetch=get_url, sleep=time.sleep, now=time.monotonic):
    deadline = now() + timeout
    last_error = ""
    def get(path):
        return fetch(urljoin(base, path) + "?verify=" + sha)
    while now() < deadline:
        try:
            online = json.loads(get("reports.json"))
            if not isinstance(online, list) or not online:
                raise ValueError("线上报告索引尚未更新")
            selected = next((m for m in online if (m["date"], m["run_id"]) == (record["date"], record["run_id"])), None)
            keys = ("date", "run_id", "title", "status", "summary", "metrics", "sha256", "entry", "url")
            if selected is None or any(selected.get(k) != record.get(k) for k in keys):
                raise ValueError("线上报告元数据与本次构建不一致")
            if get(record["url"]) != expected_html:
                raise ValueError("线上 HTML 内容校验不一致")
            home = parse_html(get("index.html").decode("utf-8"))
            if record["url"] not in home.links:
                raise ValueError("首页没有本次报告入口")
            latest = parse_html(get("latest/index.html").decode("utf-8"))
            expected_latest = urljoin(base, records[0]["url"])
            if not latest.redirect or urljoin(base + "latest/", latest.redirect) != expected_latest:
                raise ValueError("latest/ 没有指向按日期排序的最新报告")
            for path, content in assets.items():
                if get(path) != content:
                    raise ValueError(f"线上资源校验失败：{path}")
            return
        except (OSError, ValueError, KeyError, TypeError) as error:
            last_error = str(error)
        sleep(5)
    raise PublishError(f"线上验收未通过：{last_error}。可能仍在更新缓存，稍后重跑本命令即可。")


def find_gh(explicit=None):
    candidate = explicit or os.environ.get("GH_BIN") or shutil.which("gh")
    if not candidate:
        result = subprocess.run(["git", "config", "--get", "reportsite.ghPath"], cwd=ROOT,
                                capture_output=True, text=True)
        candidate = result.stdout.strip()
    if not candidate or not (shutil.which(candidate) or (Path(candidate).is_file() and os.access(candidate, os.X_OK))):
        raise PublishError("未找到 GitHub CLI。请安装 gh 并执行 gh auth login，或用 --gh /绝对路径/gh 指定。")
    return shutil.which(candidate) or str(Path(candidate).resolve())


def publish(args):
    config = json.loads((ROOT / "publish.json").read_text())
    repo, branch = config["repository"], config["branch"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or branch != "main":
        raise PublishError("配置必须指定有效的 GitHub owner/repository，分支使用 main")
    gh_path = find_gh(args.gh)
    gh = lambda *parts: run([gh_path, *parts])
    # Session-only credential helper; never write global Git settings or print a token.
    git = lambda directory, *parts: run(["git", "-c", "credential.https://github.com.helper=", "-c",
        "credential.https://github.com.helper=!" + shlex.quote(gh_path) + " auth git-credential", *parts], cwd=directory, timeout=180)
    user = json.loads(gh("api", "user"))
    print(f"[1/6] 已登录 {user['login']}，目标仓库 {repo}", flush=True)
    pages = json.loads(gh("api", f"repos/{repo}/pages"))
    base = pages["html_url"].rstrip("/") + "/"
    filename = args.date + ("--" + args.run_id if args.run_id else "") + ".html"
    with tempfile.TemporaryDirectory(prefix="reviewed-report-") as temporary:
        working = Path(temporary)
        checkout = working / "repository"
        git(ROOT, "clone", "--quiet", "--single-branch", "--branch", branch,
            f"https://github.com/{repo}.git", str(checkout))
        print("[2/6] 已建立独立发布副本；本地工作目录不参与提交", flush=True)
        original_hash = None
        created = False
        if args.check_only:
            if not (checkout / "uploads" / filename).is_file():
                raise PublishError("该日期/版本尚未上传，不能使用 --check-only")
        else:
            raw = read_source(args, config, working)
            original_hash = digest(raw)
            data, meta, local_links = prepare_report(raw, args.date)
            created = write_report(checkout, filename, data, meta)
            if local_links:
                print(f"提示：原报告有 {local_links} 处 file:// 附件链接，附件不会随 HTML 自动上传。", flush=True)
        print("[3/6] 校验并构建报告" + ("（内容相同，跳过重复提交）" if not created else ""), flush=True)
        records = build_site(checkout, checkout / "dist")
        if created:
            git(checkout, "config", "user.name", user["login"])
            git(checkout, "config", "user.email", f"{user['id']}+{user['login']}@users.noreply.github.com")
            git(checkout, "add", "--", "uploads/" + filename, "uploads/" + Path(filename).with_suffix(".json").name)
            git(checkout, "commit", "-m", f"Publish reviewed LCH report {Path(filename).stem}")
            records = build_site(checkout, checkout / "dist")
            try:
                git(checkout, "push", "origin", f"HEAD:{branch}")
            except PublishError as error:
                raise PublishError(f"推送失败；没有强制覆盖远端。请重跑本命令，从最新远端重新发布。\n{error}") from error
        sha = git(checkout, "rev-parse", "HEAD")
        run_id = "upload-" + (args.run_id or "first")
        record = next(m for m in records if (m["date"], m["run_id"]) == (args.date, run_id))
        print(f"[4/6] 等待提交 {sha[:12]} 的自动部署", flush=True)
        workflow_url = wait_workflow(gh, repo, config["workflow"], branch, sha, args.timeout, reuse=not created)
        print("[5/6] 检查线上报告内容、首页、最新链接及 CSS/JS", flush=True)
        html = (checkout / "dist" / record["url"]).read_bytes()
        assets = {path: (checkout / "dist" / path).read_bytes() for path in ("assets/site.css", "assets/site.js")}
        verify_site(base, sha, records, record, html, assets)
        result = {"date": args.date, "run_id": run_id, "commit": sha, "workflow_url": workflow_url,
                  "report_url": urljoin(base, record["url"]), "site_url": base, "latest_url": base + "latest/",
                  "source_sha256": original_hash, "published_sha256": digest(html),
                  "verified_at": datetime.now(timezone.utc).isoformat()}
        log = ROOT / "incoming" / ("publish-" + Path(filename).stem + ".json")
        log.parent.mkdir(exist_ok=True)
        log.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(f"[6/6] 发布验收通过\n报告：{result['report_url']}\n站点：{base}\n记录：{log}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="上传已人工审核的 LCH HTML；执行即表示允许公开发布。")
    parser.add_argument("date", help="报告日期 YYYY-MM-DD")
    parser.add_argument("--run-id", help="同一天的另一版，例如 r2；保留旧报告")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--local", action="store_true", help="直接读取本机 publish.json 中 remote_directory 下的报告，不使用 SSH")
    source.add_argument("--local-dir", help="直接读取指定本机目录下的 YYYY-MM-DD.html，不使用 SSH")
    parser.add_argument("--check-only", action="store_true", help="仅检查已上传版本，不读取或下载源报告")
    parser.add_argument("--gh", help="GitHub CLI 可执行文件路径")
    parser.add_argument("--timeout", type=int, default=1200, help="部署等待秒数，默认 1200")
    args = parser.parse_args()
    try:
        if date.fromisoformat(args.date).isoformat() != args.date:
            raise ValueError("日期必须为 YYYY-MM-DD")
        if args.run_id and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,59}", args.run_id):
            raise ValueError("run-id 只能含字母、数字、下划线和连字符，最长 60 位")
        if args.timeout < 1:
            raise ValueError("timeout 必须大于零")
        publish(args)
    except (PublishError, ValueError, KeyError, OSError, subprocess.TimeoutExpired) as error:
        print(f"发布未完成：{error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("已中断等待。若已推送，GitHub 部署会继续；重跑同一命令可检查结果。", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
