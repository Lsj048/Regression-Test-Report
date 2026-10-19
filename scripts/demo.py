#!/usr/bin/env python3
"""Build an isolated preview with explicitly fictional examples."""
import shutil
import tempfile
from pathlib import Path
from report_site import ROOT, build_site, import_report

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    shutil.copy2(ROOT / "site.json", root / "site.json")
    shutil.copytree(ROOT / "web", root / "web")
    for date, run_id, status, summary in [
        ("2026-10-19", "demo-03", "failed", "演示数据：48 项通过，2 项失败，1 项跳过。查看报告中的实验结果与说明。"),
        ("2026-10-12", "demo-02", "unknown", "演示数据：保留完整 HTML，支持原有样式、图表和交互。"),
        ("2026-10-05", "demo-01", "unknown", "演示数据：历史版本按日期归档，每一份报告都有独立链接。"),
        ("2026-09-28", "demo-00", "unknown", "演示数据：可通过月份导航、关键词和测试结果查找报告。"),
    ]:
        import_report(root, ROOT / "examples/demo-report", date, run_id, title=f"回归测试周报 · {date}（演示）", status=status, summary=summary, metrics={"passed": 48, "failed": 2, "skipped": 1} if status == "failed" else None)
    build_site(root, ROOT / "preview")
print(f"演示预览：{ROOT / 'preview/index.html'}")
print("演示报告不会进入正式站点。")
