#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键管线：知网 RSS 抓取 → 报刊风格 HTML 生成 → 主页目录更新
Hermes 每天只需调这一个脚本，输出即为可部署的静态网站。

用法：
  python run_pipeline.py          # 正常去重模式
  python run_pipeline.py --force  # 强制展示全部（忽略去重）

输出：
  文献追踪/latest.md          ← 最新一期 Markdown
  文献追踪/latest.html        ← 最新一期报刊 HTML
  文献追踪/文献追踪_YYYYMMDD.md
  文献追踪/文献追踪_YYYYMMDD.html
  docs/index.html             ← 主页（报告目录）
  docs/reports/YYYYMMDD.html  ← 每期报告（含返回主页按钮）
"""
import subprocess
import sys
import os
import re
import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
SCRIPT_DIR = ROOT / "文献追踪"
PYTHON = sys.executable


def collect_reports():
    """扫描所有已生成的报告，返回 [{date, week, year, path, stats, issue_number}]"""
    reports = []
    docs_reports_dir = ROOT / "docs" / "reports"
    if not docs_reports_dir.exists():
        return reports
    for f in sorted(docs_reports_dir.glob("*.html"), reverse=True):
        m = re.search(r"(\d{8})", f.stem)
        if not m:
            continue
        date_tag = m.group(1)
        try:
            dt = datetime.strptime(date_tag, "%Y%m%d")
        except ValueError:
            continue

        # 从 HTML 中提取统计信息
        html = f.read_text(encoding="utf-8")
        total_m = re.search(r"本期新增：\*\*(\d+)\*\*\s*篇", html)
        total = int(total_m.group(1)) if total_m else "—"

        # 从 metrics 区域提取数据
        nums = re.findall(r'class="num">(\d+)<', html)
        total = nums[0] if len(nums) > 0 else "—"
        journals = nums[1] if len(nums) > 1 else "—"
        dance = nums[2] if len(nums) > 2 else "—"
        ai = nums[3] if len(nums) > 3 else "—"

        week = dt.isocalendar()[1]
        reports.append({
            "date": date_tag,
            "date_fmt": f"{dt.year}.{dt.month:02d}.{dt.day:02d}",
            "year": str(dt.year),
            "week": str(week),
            "total": total,
            "journals": journals,
            "dance": dance,
            "ai": ai,
            "filename": f.name,
        })
    
    # 按期数从 1 开始编号（最早的报告是第 1 期）
    for idx, r in enumerate(reports):
        r["issue_number"] = len(reports) - idx
    
    return reports


def build_index_html(reports):
    """生成主页 HTML"""
    # 报告卡片
    cards_html = ""
    for r in reports:
        cards_html += f'''
    <a href="reports/{r["date"]}.html" class="report-card">
      <div class="card-date">{r["date_fmt"]}</div>
      <div class="card-issue">第 {r["issue_number"]} 期</div>
      <div class="card-stats">
        <span><b>{r["total"]}</b> 篇文献</span>
        <span><b>{r["journals"]}</b> 本期刊</span>
        <span>舞蹈 <b>{r["dance"]}</b></span>
        <span>AI <b>{r["ai"]}</b></span>
      </div>
      <div class="card-arrow">→</div>
    </a>'''

    total_reports = len(reports)
    latest_date = reports[0]["date_fmt"] if reports else "—"

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>学术前沿观察 · 文献追踪主页</title>
<style>
  :root {{ --bg:#f5f1eb; --paper:#faf7f2; --ink:#1a1a1a; --ink2:#4a4a4a;
           --accent:#8b1a1a; --rule:#2a2a2a; --rule-light:#d0c8be; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:var(--bg); color:var(--ink);
    font-family:"Noto Serif SC","Source Han Serif CN","STSong","Georgia",serif;
    line-height:1.75; -webkit-font-smoothing:antialiased; }}
  .page {{ max-width:960px; margin:0 auto; background:var(--paper); min-height:100vh; }}

  /* 报头 */
  .masthead {{ text-align:center; padding:48px 40px 24px; border-bottom:4px double var(--rule); }}
  .masthead-brand {{ font-size:11px; letter-spacing:6px; color:var(--ink2); }}
  .masthead-title {{ font-size:46px; font-weight:900; letter-spacing:3px; margin:8px 0 4px; }}
  .masthead-sub {{ font-size:14px; color:var(--ink2); letter-spacing:2px; margin-top:8px; }}

  /* 概览条 */
  .overview {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px;
    max-width:860px; margin:28px auto; padding:0 30px; }}
  .ov-item {{ background:#fff; padding:20px 14px; border:1px solid var(--rule-light); text-align:center; }}
  .ov-item .num {{ font-size:38px; color:var(--accent); font-family:Georgia; font-weight:bold; }}
  .ov-item .lbl {{ font-size:12px; color:var(--ink2); margin-top:4px; letter-spacing:1px; }}

  /* 目录区 */
  .archive {{ max-width:860px; margin:0 auto; padding:30px 30px 50px; }}
  .archive-title {{ font-size:22px; color:var(--accent); border-left:5px solid var(--accent);
    padding-left:12px; margin-bottom:20px; }}

  /* 报告卡片 */
  .report-card {{ display:flex; align-items:center; padding:18px 20px; margin-bottom:12px;
    background:#fff; border:1px solid var(--rule-light); text-decoration:none; color:var(--ink);
    transition:all .2s; position:relative; }}
  .report-card:hover {{ border-color:var(--accent); box-shadow:0 2px 8px rgba(139,26,26,0.1);
    transform:translateY(-1px); }}
  .card-date {{ font-size:20px; font-weight:bold; color:var(--accent); min-width:120px;
    font-family:Georgia; }}
  .card-issue {{ font-size:13px; color:var(--ink2); min-width:100px; margin-left:16px; }}
  .card-stats {{ flex:1; display:flex; gap:16px; font-size:13px; color:var(--ink2); margin-left:16px; }}
  .card-stats b {{ color:var(--ink); }}
  .card-arrow {{ font-size:20px; color:var(--accent); margin-left:auto; padding-left:16px; }}

  footer {{ text-align:center; padding:30px 20px; font-size:12px; color:var(--ink2);
    border-top:1px solid var(--rule-light); }}

  @media (max-width:760px) {{
    .overview {{ grid-template-columns:1fr; }}
    .report-card {{ flex-wrap:wrap; }}
    .card-date {{ min-width:auto; }}
    .card-issue {{ min-width:auto; margin-left:0; margin-top:4px; }}
    .card-stats {{ margin-left:0; margin-top:8px; flex-wrap:wrap; gap:8px; }}
    .masthead-title {{ font-size:30px; }}
  }}
</style>
</head>
<body>
<div class="page">

  <header class="masthead">
    <div class="masthead-brand">ACADEMIC FRONTIER OBSERVER</div>
    <div class="masthead-title">学术前沿观察</div>
    <div class="masthead-sub">体育科学与舞蹈艺术 · 核心期刊文献追踪系统</div>
  </header>

  <div class="overview">
    <div class="ov-item"><div class="num">{total_reports}</div><div class="lbl">累计期数</div></div>
    <div class="ov-item"><div class="num">8</div><div class="lbl">追踪期刊</div></div>
    <div class="ov-item"><div class="num">{latest_date}</div><div class="lbl">最近更新</div></div>
  </div>

  <section class="archive">
    <h2 class="archive-title">全部报告</h2>
    {cards_html if cards_html else '<p style="color:#888;font-size:14px;">暂无报告，等待首次生成…</p>'}
  </section>

  <footer>
    数据来源：中国知网 CNKI 公开 RSS · 覆盖期刊：体育科学 / 体育文化导刊 / 北京体育大学学报 / 成都体育学院学报 / 广州体育学院学报 / 武汉体育学院学报 / 北京舞蹈学院学报 / 上海体育大学学报<br>
    本报告由 Hermes 自动生成并每日推送至 GitHub Pages · {datetime.now().strftime("%Y-%m-%d %H:%M")}
  </footer>

</div>
</body>
</html>'''


def main():
    force = "--force" in sys.argv
    date_tag = datetime.now().strftime("%Y%m%d")
    print(f"=== 文献追踪管线启动 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    print(f"模式：{'force（展示全部）' if force else '去重（仅新增）'}")
    print()

    # ---- Step 1: RSS 抓取 ----
    print("【1/3】抓取知网核心期刊 RSS ...")
    fetch_cmd = [PYTHON, str(ROOT / "cnki_rss_fetch.py")]
    if force:
        fetch_cmd.append("--force")

    result = subprocess.run(fetch_cmd, capture_output=True, text=True, cwd=str(ROOT))
    print(result.stdout.strip() if result.stdout.strip() else "(无 stdout)")
    if result.stderr:
        print(result.stderr.strip())

    if result.returncode != 0:
        print(f"[ERROR] RSS 抓取失败 (exit {result.returncode})", file=sys.stderr)
        latest_md = SCRIPT_DIR / "latest.md"
        if not latest_md.exists():
            candidates = list(SCRIPT_DIR.glob("文献追踪_*.md"))
            if not candidates:
                print("[FATAL] 无历史数据可用，退出", file=sys.stderr)
                sys.exit(1)
            print("[WARN] 使用历史数据生成 HTML")

    # ---- Step 2: HTML 生成 ----
    print()
    print("【2/3】生成报刊风格 HTML ...")
    build_cmd = [PYTHON, str(SCRIPT_DIR / "build_report.py")]
    result2 = subprocess.run(build_cmd, capture_output=True, text=True, cwd=str(ROOT))
    print(result2.stdout.strip() if result2.stdout.strip() else "(无 stdout)")
    if result2.stderr:
        print(result2.stderr.strip())

    if result2.returncode != 0:
        print(f"[ERROR] HTML 生成失败 (exit {result2.returncode})", file=sys.stderr)
        sys.exit(1)

    # ---- Step 3: 部署准备 ----
    print()
    print("【3/3】更新主页目录 ...")
    docs_dir = ROOT / "docs"
    reports_dir = docs_dir / "reports"
    docs_dir.mkdir(exist_ok=True)
    reports_dir.mkdir(exist_ok=True)

    # 复制当期报告到 docs/reports/
    latest_html = SCRIPT_DIR / "latest.html"
    if latest_html.exists():
        shutil.copy2(str(latest_html), str(reports_dir / f"{date_tag}.html"))
        print(f"  → 已复制 docs/reports/{date_tag}.html")

    # 生成主页目录
    reports = collect_reports()
    index_html = build_index_html(reports)
    (docs_dir / "index.html").write_text(index_html, encoding="utf-8")
    print(f"  → 已更新 docs/index.html（{len(reports)} 期报告）")

    # ---- 完成 ----
    print()
    print(f"=== 管线完成 ===")
    print(f"  Markdown: 文献追踪/文献追踪_{date_tag}.md")
    print(f"  HTML:     文献追踪/文献追踪_{date_tag}.html")
    print(f"  主页:     docs/index.html")
    print(f"  报告目录: docs/reports/ ({len(reports)} 期)")
    print(f"  在线查看: 推送到 GitHub 后自动发布")


if __name__ == "__main__":
    main()
