#!/usr/bin/env python3
"""Import existing HTML reports and build a static site. Python standard library only."""
import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import tempfile
import uuid
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {"passed": "全部通过", "failed": "存在失败", "unknown": "未标注"}
EXTENSIONS = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".woff", ".woff2", ".ttf", ".txt", ".csv", ".pdf", ".mp4", ".webm", ".zip", ".map", ".wasm"}
MAX_BYTES = 100 * 1024 * 1024


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_entry(value):
    p = PurePosixPath(value)
    if not value or "\\" in value or p.is_absolute() or any(x in ("..", ".") for x in value.split("/")) or p.suffix.lower() not in (".html", ".htm"):
        raise ValueError("entry 必须是报告目录内的相对 HTML 路径")
    return p


def validate_metrics(metrics):
    if metrics is None:
        return None
    if not isinstance(metrics, dict) or set(metrics) != {"passed", "failed", "skipped"}:
        raise ValueError("metrics 必须包含且只包含 passed、failed、skipped")
    if any(type(v) is not int or v < 0 for v in metrics.values()):
        raise ValueError("测试数量必须是非负整数")
    return metrics


def check_bundle(source):
    if source.is_symlink():
        raise ValueError("报告不能使用符号链接")
    files = [source] if source.is_file() else list(source.rglob("*"))
    total = 0
    for p in files:
        if p.is_symlink():
            raise ValueError(f"报告不能包含符号链接：{p.name}")
        relative = p.relative_to(source) if source.is_dir() else Path(p.name)
        if any(part.startswith(".") for part in relative.parts):
            raise ValueError(f"报告目录含隐藏文件，请使用专用导出目录：{relative}")
        if p.is_file():
            if p.suffix.lower() not in EXTENSIONS:
                raise ValueError(f"不支持的报告附件类型：{relative}")
            total += p.stat().st_size
    if total > MAX_BYTES:
        raise ValueError("单份报告超过 100 MiB，请移出大文件后重试")


def bundle_digest(source):
    digest = hashlib.sha256()
    for p in sorted(source.rglob("*")):
        if p.is_file():
            digest.update(p.relative_to(source).as_posix().encode())
            digest.update(b"\0")
            digest.update(p.read_bytes())
    return digest.hexdigest()


def import_report(root, source, report_date=None, run_id=None, entry="index.html", title=None, status="unknown", summary="", metrics=None):
    root = Path(root).resolve()
    source = Path(source).absolute()
    if not source.exists():
        raise ValueError(f"报告路径不存在：{source}")
    if status not in STATUSES:
        raise ValueError("未知报告状态")
    metrics = validate_metrics(metrics)
    if status == "passed" and metrics and metrics["failed"]:
        raise ValueError("报告标为通过，但 failed 大于 0")
    zone = ZoneInfo(read_json(root / "site.json")["timezone"])
    now = datetime.now(zone)
    report_date = report_date or now.date().isoformat()
    if date.fromisoformat(report_date).isoformat() != report_date:
        raise ValueError("日期格式必须为 YYYY-MM-DD")
    run_id = run_id or now.strftime("%H%M%S") + "-" + uuid.uuid4().hex[:8]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_id):
        raise ValueError("run-id 只能包含字母、数字、下划线、连字符，最长 80 位")
    entry_path = safe_entry(entry if source.is_dir() else source.name)
    check_bundle(source)
    source_entry = source / str(entry_path) if source.is_dir() else source
    if not source_entry.is_file() or not source_entry.stat().st_size:
        raise ValueError("HTML 入口不存在或内容为空")
    destination = root / "reports" / report_date / run_id
    if destination.exists():
        raise ValueError("该日期和 run-id 已存在；请使用新 run-id 保留历史")
    if source.is_dir() and (destination == source.resolve() or source.resolve() in destination.parents):
        raise ValueError("归档目录不能位于输入目录中")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="report-import-") as temporary:
        staging = Path(temporary) / "run"
        bundle = staging / "html"
        if source.is_dir():
            shutil.copytree(source, bundle)
        else:
            bundle.mkdir(parents=True)
            shutil.copy2(source, bundle / source.name)
        record = {"schema": 1, "date": report_date, "run_id": run_id, "title": title or f"回归测试报告 · {report_date}", "status": status, "summary": summary, "metrics": metrics, "entry": entry_path.as_posix(), "imported_at": now.isoformat(), "sha256": bundle_digest(bundle)}
        write_json(staging / "metadata.json", record)
        # Copy into a hidden staging directory on the destination filesystem, then rename.
        local_stage = destination.parent / (".import-" + uuid.uuid4().hex)
        try:
            shutil.copytree(staging, local_stage)
            local_stage.rename(destination)
        finally:
            if local_stage.exists():
                shutil.rmtree(local_stage)
    return record


def load_reports(root):
    records = []
    for metadata in (root / "reports").glob("*/*/metadata.json"):
        m = read_json(metadata)
        if m.get("schema") != 1 or m["status"] not in STATUSES:
            raise ValueError(f"不合法的元数据：{metadata}")
        if m["date"] != metadata.parent.parent.name or m["run_id"] != metadata.parent.name:
            raise ValueError("元数据日期/run-id 与归档目录不一致")
        date.fromisoformat(m["date"])
        imported = datetime.fromisoformat(m["imported_at"])
        if imported.tzinfo is None:
            raise ValueError("imported_at 必须包含时区")
        validate_metrics(m.get("metrics"))
        if m["status"] == "passed" and m.get("metrics") and m["metrics"]["failed"]:
            raise ValueError("通过状态与失败用例数不一致")
        entry = safe_entry(m["entry"])
        bundle = metadata.parent / "html"
        check_bundle(bundle)
        if not (bundle / str(entry)).is_file() or bundle_digest(bundle) != m["sha256"]:
            raise ValueError(f"报告缺失或内容发生修改：{metadata.parent}")
        m["url"] = quote((metadata.parent.relative_to(root) / "html" / str(entry)).as_posix(), safe="/")
        records.append(m)
    return sorted(records, key=lambda m: (m["date"], datetime.fromisoformat(m["imported_at"]), m["run_id"]), reverse=True)


def build_archive(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    # Never allow a clean build to remove source files or an arbitrary existing directory.
    if output == root or output in root.parents or root / "reports" == output or root / "reports" in output.parents:
        raise ValueError("输出目录不能覆盖项目或报告源文件")
    if output.exists() and any(output.iterdir()) and not (output / ".report-site-build").exists():
        raise ValueError("输出目录非空且不是本工具生成的站点")
    records = load_reports(root)
    config = read_json(root / "site.json")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (output / ".report-site-build").touch()
    (output / ".nojekyll").touch()
    for m in records:
        relative = Path("reports") / m["date"] / m["run_id"]
        shutil.copytree(root / relative, output / relative)
    shutil.copytree(root / "web" / "assets", output / "assets")
    escape = lambda x: html.escape(str(x), quote=True)
    cards = []
    for m in records:
        counts = m.get("metrics")
        details = (f'{counts["passed"]} 通过 / {counts["failed"]} 失败 / {counts["skipped"]} 跳过' if counts else "未提供用例统计")
        cards.append(f'''<article class="report-card" data-status="{m['status']}" data-month="{m['date'][:7]}">
<div class="report-date"><strong>{m['date'][8:]}</strong><span>{m['date'][:7]}</span></div>
<div class="report-info"><div class="report-heading"><h3><a href="{m['url']}">{escape(m['title'])}</a></h3><span class="badge {m['status']}">{STATUSES[m['status']]}</span></div>
<p>{escape(m['summary'] or '打开完整 HTML 查看实验过程与结果。')}</p><div class="report-meta"><span>{escape(details)}</span><span>运行 {escape(m['run_id'])}</span></div></div>
<a class="report-arrow" href="{m['url']}" aria-label="打开 {escape(m['title'])}">↗</a></article>''')
    latest = records[0] if records else None
    latest_html = (f'''<span class="eyebrow">LATEST REPORT / 最新报告</span><div class="latest-heading"><h2>{escape(latest['title'])}</h2><span class="badge {latest['status']}">{STATUSES[latest['status']]}</span></div><p>{escape(latest['summary'] or '查看本次回归测试的完整结果。')}</p><div class="latest-footer"><span>{latest['date']} <span class="dot">·</span> 运行 {escape(latest['run_id'])}</span><a class="button" href="{latest['url']}">阅读完整报告 <span>↗</span></a></div>''' if latest else '<span class="eyebrow">READY FOR YOUR FIRST REPORT</span><h2>第一份报告，准备就绪后见。</h2><p>导入已有的 HTML 报告后，这里会显示最新结果和历史记录。</p>')
    months = sorted({m["date"][:7] for m in records}, reverse=True)
    month_links = ''.join(f'<button class="month-filter" data-value="{month}"><span>{month}</span><span>{sum(m["date"].startswith(month) for m in records):02d}</span></button>' for month in months)
    data = {"TITLE": escape(config["title"]), "DESCRIPTION": escape(config["description"]), "SCHEDULE": escape(config["schedule"]), "LATEST": latest_html, "CARDS": ''.join(cards) or '<div class="empty">还没有归档报告。</div>', "MONTHS": month_links, "COUNT": str(len(records)), "DATE": latest["date"] if latest else "—", "FAILED": str(sum(m["status"] == "failed" for m in records)), "STATUS": STATUSES[latest["status"]] if latest else "等待导入"}
    template = (root / "web" / "index.html").read_text(encoding="utf-8")
    # One-pass replacement: report text is never interpreted as a template.
    rendered = re.sub(r"\{\{([A-Z]+)\}\}", lambda match: data[match[1]], template)
    (output / "index.html").write_text(rendered, encoding="utf-8")
    write_json(output / "reports.json", records)
    (output / "latest").mkdir()
    if latest:
        target = "../" + latest["url"]
        (output / "latest" / "index.html").write_text(f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={escape(target)}"><title>最新报告</title><a href="{escape(target)}">打开最新报告</a></html>', encoding="utf-8")
    else:
        (output / "latest" / "index.html").write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>暂无报告</title><p>暂无报告。</p><a href="../">返回首页</a></html>', encoding="utf-8")
    return records


def build_site(root, output):
    """Materialize browser uploads in a temporary archive; never mutate tracked input."""
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root or output in root.parents or any(output == root / p or root / p in output.parents for p in ("reports", "uploads", "web", "scripts", "tests", ".github")):
        raise ValueError("输出目录不能覆盖项目源文件")
    with tempfile.TemporaryDirectory(prefix="report-build-") as temporary:
        staging = Path(temporary)
        shutil.copy2(root / "site.json", staging / "site.json")
        shutil.copytree(root / "web", staging / "web")
        if (root / "reports").exists():
            shutil.copytree(root / "reports", staging / "reports", symlinks=True)
        for source in sorted((root / "uploads").glob("*")):
            if source.name.startswith(".") or source.suffix == ".json":
                continue
            match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})(?:--([A-Za-z0-9][A-Za-z0-9_-]{0,59}))?(?:\.html)?", source.name)
            if not match or not (source.is_dir() or source.suffix == ".html"):
                raise ValueError(f"上传文件必须命名为 YYYY-MM-DD.html 或 YYYY-MM-DD--运行编号.html：{source.name}")
            report_date, suffix = match.groups()
            # The optional run group must not absorb the extension.
            run_id = "upload-" + (suffix or "first")
            sidecar = source.with_suffix(".json") if source.is_file() else source.parent / (source.name + ".json")
            meta = read_json(sidecar) if sidecar.exists() else {}
            allowed = {"title", "status", "summary", "metrics", "entry"}
            if not isinstance(meta, dict) or set(meta) - allowed:
                raise ValueError(f"元数据字段不受支持：{sidecar.name}")
            for field in ("title", "status", "summary", "entry"):
                if field in meta and not isinstance(meta[field], str):
                    raise ValueError(f"{field} 必须是字符串")
            record = import_report(staging, source, report_date, run_id, **meta)
            # Use the source commit time so sorting does not change on rebuild.
            committed = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%cI", "--", str(source.relative_to(root))], capture_output=True, text=True)
            stamp = committed.stdout.strip() if committed.returncode == 0 else ""
            record["imported_at"] = stamp or datetime.fromtimestamp(source.stat().st_mtime, ZoneInfo("Asia/Shanghai")).isoformat()
            write_json(staging / "reports" / report_date / run_id / "metadata.json", record)
        # A sidecar without its HTML is likely a mistaken upload, not a report.
        for sidecar in (root / "uploads").glob("*.json"):
            if not sidecar.with_suffix(".html").exists() and not sidecar.with_suffix("").is_dir():
                raise ValueError(f"元数据没有对应报告：{sidecar.name}")
        return build_archive(staging, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="导入单个 HTML 文件或完整报告目录")
    add.add_argument("source", type=Path)
    add.add_argument("--date")
    add.add_argument("--run-id")
    add.add_argument("--entry", default="index.html")
    add.add_argument("--title")
    add.add_argument("--status", choices=STATUSES, default="unknown")
    add.add_argument("--summary", default="")
    add.add_argument("--metrics", type=Path, help="含 passed/failed/skipped 的 JSON 文件")
    build = commands.add_parser("build")
    build.add_argument("--output", type=Path)
    commands.add_parser("validate")
    args = parser.parse_args()
    try:
        if args.command == "add":
            record = import_report(args.root, args.source, args.date, args.run_id, args.entry, args.title, args.status, args.summary, read_json(args.metrics) if args.metrics else None)
            print(f"已归档：reports/{record['date']}/{record['run_id']}/")
        elif args.command == "build":
            output = args.output or args.root / "dist"
            records = build_site(args.root, output)
            print(f"已构建 {len(records)} 份报告：{output}")
        else:
            print(f"验证通过：{len(load_reports(args.root))} 份报告")
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, f"错误：{error}\n")


if __name__ == "__main__":
    main()
