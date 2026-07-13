#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键管线：知网 RSS 抓取 → 报刊风格 HTML 生成
Hermes 每天只需调这一个脚本，输出即为可部署的静态网站。

用法：
  python run_pipeline.py          # 正常去重模式
  python run_pipeline.py --force  # 强制展示全部（忽略去重）

输出：
  文献追踪/latest.md          ← 最新一期 Markdown
  文献追踪/latest.html        ← 最新一期报刊 HTML（也是 index.html 的来源）
  文献追踪/文献追踪_YYYYMMDD.md
  文献追踪/文献追踪_YYYYMMDD.html
"""
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
SCRIPT_DIR = ROOT / "文献追踪"
PYTHON = sys.executable

def main():
    force = "--force" in sys.argv
    date_tag = datetime.now().strftime("%Y%m%d")
    print(f"=== 文献追踪管线启动 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    print(f"模式：{'force（展示全部）' if force else '去重（仅新增）'}")
    print()

    # ---- Step 1: RSS 抓取 ----
    print("【1/2】抓取知网核心期刊 RSS ...")
    fetch_cmd = [PYTHON, str(ROOT / "cnki_rss_fetch.py")]
    if force:
        fetch_cmd.append("--force")

    result = subprocess.run(fetch_cmd, capture_output=True, text=True, cwd=str(ROOT))
    print(result.stdout.strip() if result.stdout.strip() else "(无 stdout)")
    if result.stderr:
        print(result.stderr.strip())

    if result.returncode != 0:
        print(f"[ERROR] RSS 抓取失败 (exit {result.returncode})", file=sys.stderr)
        # 即使抓取失败，如果已有历史数据，仍然可以生成 HTML
        latest_md = SCRIPT_DIR / "latest.md"
        if not latest_md.exists():
            # 也检查日期文件
            candidates = list(SCRIPT_DIR.glob("文献追踪_*.md"))
            if not candidates:
                print("[FATAL] 无历史数据可用，退出", file=sys.stderr)
                sys.exit(1)
            print("[WARN] 使用历史数据生成 HTML")

    # ---- Step 2: HTML 生成 ----
    print()
    print("【2/2】生成报刊风格 HTML ...")
    build_cmd = [PYTHON, str(SCRIPT_DIR / "build_report.py")]
    result2 = subprocess.run(build_cmd, capture_output=True, text=True, cwd=str(ROOT))
    print(result2.stdout.strip() if result2.stdout.strip() else "(无 stdout)")
    if result2.stderr:
        print(result2.stderr.strip())

    if result2.returncode != 0:
        print(f"[ERROR] HTML 生成失败 (exit {result2.returncode})", file=sys.stderr)
        sys.exit(1)

    # ---- Step 3: 部署准备（复制 latest.html → docs/index.html）----
    latest_html = SCRIPT_DIR / "latest.html"
    if latest_html.exists():
        docs_dir = ROOT / "docs"
        docs_dir.mkdir(exist_ok=True)
        import shutil
        shutil.copy2(str(latest_html), str(docs_dir / "index.html"))
        print()
        print(f"[OK] 已同步 docs/index.html（用于 GitHub Pages 部署）")

    # ---- 完成 ----
    print()
    print(f"=== 管线完成 ===")
    print(f"  Markdown: 文献追踪/文献追踪_{date_tag}.md")
    print(f"  HTML:     文献追踪/文献追踪_{date_tag}.html")
    print(f"  部署文件: docs/index.html")
    print(f"  在线查看: 推送到 GitHub 后自动发布")


if __name__ == "__main__":
    main()
