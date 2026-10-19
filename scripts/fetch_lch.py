#!/usr/bin/env python3
"""Download one LCH report for local review; never publish it."""
import argparse
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("date", help="YYYY-MM-DD")
args = parser.parse_args()
if date.fromisoformat(args.date).isoformat() != args.date:
    parser.error("日期格式必须为 YYYY-MM-DD")
destination = ROOT / "incoming" / (args.date + ".html")
destination.parent.mkdir(exist_ok=True)
if destination.exists():
    parser.error(f"本地文件已存在，请先完成审核或自行另存：{destination}")
partial = destination.with_suffix(".html.part")
try:
    subprocess.run(["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", f"LCH:/Users/iie/Desktop/LCH-回归测试报告/{args.date}.html", str(partial)], check=True)
    partial.rename(destination)
finally:
    if partial.exists():
        partial.unlink()
print(f"已下载到待审核目录：{destination}")
print("审核通过后，将该文件上传到 GitHub 仓库的 uploads 目录。")
