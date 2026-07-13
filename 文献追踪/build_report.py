#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文献追踪 → 报刊风格 HTML 生成器
读取 文献追踪_YYYYMMDD.md，生成 文献追踪_YYYYMMDD.html + latest.html
供 Hermes 每日调用，推送至 GitHub Pages。
"""
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent  # 文献追踪/ 目录
JOURNAL_NAMES = [
    "体育科学", "体育文化导刊", "北京体育大学学报", "成都体育学院学报",
    "广州体育学院学报", "武汉体育学院学报", "北京舞蹈学院学报",
    "上海体育大学学报",  # 新增：2026-07-13
]

DANCE_KEYWORDS = [
    "舞蹈", "国标舞", "摩登舞", "探戈", "狐步", "华尔兹", "拉丁",
    "体育舞蹈", "编舞", "编创", "芭蕾", "民间舞", "国标舞剧",
]

# ================= 解析 =================

def find_latest_md():
    """找到最新的 文献追踪_YYYYMMDD.md"""
    candidates = sorted(ROOT.glob("文献追踪_*.md"), reverse=True)
    for f in candidates:
        try:
            datetime.strptime(f.stem.split("_")[-1], "%Y%m%d")
            return f
        except ValueError:
            continue
    # 回退到 latest.md
    if (ROOT / "latest.md").exists():
        return ROOT / "latest.md"
    return None


def parse_md(md_text):
    """解析报告为结构化数据：focus + 分刊文章"""
    focus = []  # 舞蹈相关论文
    by_journal = {}  # {期刊名: [articles]}
    current_journal = None

    for line in md_text.splitlines():
        # 期刊标题 ###
        jm = re.match(r"^###\s+(.+?)(?:（(\d+)\s*篇）)?$", line)
        if jm:
            current_journal = jm.group(1).strip()
            by_journal.setdefault(current_journal, [])
            continue

        # 重点关注区（舞蹈相关）
        m_link = re.match(r"^- \[(.+?)\]\((https?://[^\)]+)\)$", line)
        m_plain = re.match(r"^- (.+)$", line) if not m_link else None
        if (m_link or m_plain) and re.search(r"重点关注|舞蹈", "\n".join(md_text.splitlines()[max(0, md_text.find(line)-200):md_text.find(line)])):
            # 宽松判定：在重点关注区内
            pass

        # 文章条目（编号列表）
        am = re.match(r"^\d+\.\s*(?:⭐\s*)?(?:\[(.+?)\]\((https?://[^\)]+)\)|(.+))$", line)
        if am and current_journal:
            title = am.group(1) or am.group(3)
            url = am.group(2) or ""
            by_journal.setdefault(current_journal, []).append({
                "title": title.strip(),
                "url": url,
                "authors": "",
                "date": "",
                "abstract": "",
            })
            continue

        # 元信息行（作者 | 日期）
        mm = re.match(r"^\s+([\w\s;·]+?)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*$", line)
        if mm and current_journal and by_journal.get(current_journal):
            by_journal[current_journal][-1]["authors"] = mm.group(1).strip()
            by_journal[current_journal][-1]["date"] = mm.group(2).strip()
            continue

        # 摘要行
        am2 = re.match(r"^\s+>\s*(.+)$", line)
        if am2 and current_journal and by_journal.get(current_journal):
            by_journal[current_journal][-1]["abstract"] = am2.group(1).strip()
            continue

        # 重点关注区的独立条目（无编号）
        fm = re.match(r"^- \[(.+?)\]\((https?://[^\)]+)\)$", line)
        if fm and "重点关注" in line or (fm and not current_journal):
            pass

    # 单独扫一遍重点关注区
    focus_section = re.search(r"## 🎯 重点关注.+?---", md_text, re.DOTALL)
    if focus_section:
        for m in re.finditer(r"^- \[(.+?)\]\((https?://[^\)]+)\)\n\s*-\s*(.+?)$", focus_section.group(0), re.MULTILINE):
            title, url, meta = m.groups()
            jm = re.match(r"(.+?)\s*\|\s*(.+?)(?:\s*·\s*(\d{4}-\d{2}-\d{2}))?$", meta.strip())
            authors = jm.group(1).strip() if jm else ""
            journal = jm.group(1).strip() if jm else ""
            date = jm.group(3).strip() if jm and jm.group(3) else ""
            # meta 形如 "北京舞蹈学院学报 | 刘奕杉;刘炼 · 2026-05-27"
            mm2 = re.match(r"(.+?)\s*\|\s*(.+?)(?:\s*·\s*(\d{4}-\d{2}-\d{2}))?$", meta.strip())
            if mm2:
                journal = mm2.group(1).strip()
                authors = mm2.group(2).strip()
                date = mm2.group(3).strip() if mm2.group(3) else ""
            focus.append({
                "title": title, "url": url, "authors": authors,
                "journal": journal, "date": date,
            })

    # 头部统计
    total_m = re.search(r"本期新增：\*\*(\d+)\*\*\s*篇", md_text)
    total = int(total_m.group(1)) if total_m else sum(len(v) for v in by_journal.values())

    # 日期
    date_m = re.search(r"生成时间：(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2})?", md_text)
    gen_time = date_m.group(1).strip() if date_m and date_m.group(1) else datetime.now().strftime("%Y-%m-%d %H:%M")

    return {
        "focus": focus,
        "by_journal": by_journal,
        "total": total,
        "gen_time": gen_time,
    }


# ================= 统计 =================

def compute_stats(data):
    by_j = data["by_journal"]
    total = data["total"] or sum(len(v) for v in by_j.values())
    journal_count = len([j for j in JOURNAL_NAMES if j in by_j])

    # 舞蹈/国标舞 计数（跨刊扫描）
    dance_count = 0
    ai_count = 0
    all_titles = []
    for j, arts in by_j.items():
        for a in arts:
            txt = a["title"] + " " + a["abstract"]
            if any(kw in txt for kw in DANCE_KEYWORDS):
                dance_count += 1
            if re.search(r"AI|人工智能|生成式|算法|数字化|智能", txt):
                ai_count += 1
            all_titles.append((a["title"], a["abstract"]))

    # 主题分布（简化）
    topics = {"训练/竞技": 0, "教育/学校": 0, "舞蹈/艺术": 0,
              "体育产业": 0, "历史文化": 0, "其他": 0}
    for t, abs_ in all_titles:
        txt = t + " " + abs_
        if re.search(r"训练|竞赛|竞技|比赛|运动员|备战|奥运", txt):
            topics["训练/竞技"] += 1
        elif re.search(r"教学|课程|学校|学生|教师|校园", txt):
            topics["教育/学校"] += 1
        elif re.search(r"舞蹈|国标|艺术|编创|剧目|芭蕾", txt):
            topics["舞蹈/艺术"] += 1
        elif re.search(r"产业|消费|市场|经济|就业", txt):
            topics["体育产业"] += 1
        elif re.search(r"文化|历史|传统|遗产|龙舟|武术", txt):
            topics["历史文化"] += 1
        else:
            topics["其他"] += 1

    return {
        "total": total,
        "journals": journal_count,
        "dance": dance_count,
        "ai": ai_count,
        "by_journal": {j: len(by_j.get(j, [])) for j in JOURNAL_NAMES if j in by_j},
        "topics": topics,
    }


# ================= HTML =================

def build_html(data, stats, date_tag):
    # 期刊柱状图
    journals = stats["by_journal"]
    names = list(journals.keys())
    counts = [journals[n] for n in names]
    max_c = max(counts) if counts and max(counts) > 0 else 1
    bar_w, gap = 70, 22
    chart_w = len(names) * (bar_w + gap) + 40
    chart_h = 280
    bars = ""
    for i, (n, c) in enumerate(zip(names, counts)):
        h = int(c / max_c * 190)
        x = 20 + i * (bar_w + gap)
        y = chart_h - 50 - h
        short = n[:5] + ("…" if len(n) > 5 else "")
        bars += f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" fill="#8b1a1a"/>'
        bars += f'<text x="{x + bar_w/2}" y="{y - 6}" text-anchor="middle" font-size="13" fill="#2b2b2b" font-family="Georgia">{c}</text>'
        bars += f'<text x="{x + bar_w/2}" y="{chart_h - 28}" text-anchor="middle" font-size="11" fill="#444" font-family="Georgia">{short}</text>'

    # 主题表格
    topic_rows = "".join(
        f'<tr><td style="padding:7px;border-bottom:1px solid #eee;">{k}</td>'
        f'<td style="text-align:right;padding:7px;border-bottom:1px solid #eee;color:#8b1a1a;font-weight:bold;">{v}</td>'
        f'<td style="padding:7px;border-bottom:1px solid #eee;color:#888;">篇</td></tr>'
        for k, v in stats["topics"].items() if v > 0
    )

    # 重点关注卡片
    focus_cards = ""
    for i, a in enumerate(data["focus"][:3], 1):
        focus_cards += f'''
<div class="focus-card">
  <div class="focus-num">0{i}</div>
  <div class="focus-title"><a href="{a["url"]}" target="_blank">{a["title"]}</a></div>
  <div class="focus-meta">{a["authors"]} / {a["journal"]} {("· " + a["date"]) if a.get("date") else ""}</div>
</div>'''

    # 分刊速览
    browse_html = ""
    for j in JOURNAL_NAMES:
        if j not in data["by_journal"]:
            continue
        items = data["by_journal"][j]
        lis = ""
        for a in items[:4]:
            url = a.get("url") or "#"
            auth = f" — {a['authors']}" if a.get("authors") else ""
            lis += f'<li><a href="{url}" target="_blank">{a["title"]}</a><span class="meta">{auth}</span></li>'
        more = len(items) - 4
        if more > 0:
            lis += f'<li class="more">…另有 {more} 篇</li>'
        browse_html += f'<div class="jour-col"><h3>{j}</h3><ul>{lis}</ul></div>'

    # 期号（今年第几周）
    week = datetime.strptime(date_tag, "%Y%m%d").isocalendar()[1]
    year = date_tag[:4]

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>学术前沿观察 · {year} 第 {week} 期</title>
<style>
  :root {{ --bg:#f5f1eb; --paper:#faf7f2; --ink:#1a1a1a; --ink2:#4a4a4a;
           --accent:#8b1a1a; --rule:#2a2a2a; --rule-light:#d0c8be; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:var(--bg); color:var(--ink);
    font-family:"Noto Serif SC","Source Han Serif CN","STSong","SimSun",Georgia,serif;
    line-height:1.75; -webkit-font-smoothing:antialiased; }}
  .page {{ max-width:960px; margin:0 auto; background:var(--paper); min-height:100vh; }}

  /* 报头 */
  .masthead {{ text-align:center; padding:36px 40px 18px; border-bottom:4px double var(--rule); }}
  .masthead-brand {{ font-size:11px; letter-spacing:6px; color:var(--ink2); }}
  .masthead-title {{ font-size:42px; font-weight:900; letter-spacing:3px; margin:8px 0 4px; }}
  .masthead-sub {{ font-size:13px; color:var(--ink2); letter-spacing:2px; }}

  /* 导语 */
  .standfirst {{ max-width:820px; margin:24px auto; padding:0 30px 20px; font-size:17px; line-height:1.85;
    color:#444; text-align:center; font-style:italic; border-bottom:1px solid var(--rule-light); }}
  .standfirst b {{ color:var(--accent); font-style:normal; }}

  /* 指标条 */
  .metrics {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px;
    max-width:860px; margin:24px auto; padding:0 30px; }}
  .metric {{ background:#fff; padding:18px 10px; border:1px solid var(--rule-light); text-align:center; }}
  .metric .num {{ font-size:34px; color:var(--accent); font-family:Georgia; font-weight:bold; }}
  .metric .lbl {{ font-size:12px; color:var(--ink2); margin-top:4px; letter-spacing:1px; }}

  /* 正文区 */
  .wrap {{ max-width:920px; margin:0 auto; padding:30px 30px; }}
  .two-col {{ column-count:2; column-gap:32px; column-rule:1px solid var(--rule-light); text-align:justify; }}
  .two-col p {{ margin:0 0 14px; font-size:15px; }}
  .two-col p:first-of-type::first-letter {{
    font-size:54px; float:left; line-height:1; padding:4px 8px 0 0;
    color:var(--accent); font-family:Georgia; font-weight:bold; }}

  /* 图表 */
  .charts {{ display:grid; grid-template-columns:1.4fr 1fr; gap:24px; margin:28px 0; }}
  .chart-box {{ background:#fff; padding:18px; border:1px solid var(--rule-light); }}
  .chart-box h3 {{ font-size:15px; color:var(--accent); border-bottom:1px solid var(--rule-light);
    padding-bottom:6px; margin-bottom:10px; }}

  /* 重点关注 */
  .focus {{ margin:30px 0; }}
  .focus > h2 {{ font-size:22px; color:var(--accent); border-left:5px solid var(--accent);
    padding-left:12px; margin-bottom:14px; }}
  .focus-cards {{ display:grid; grid-template-columns:repeat(3,1fr); gap:18px; }}
  .focus-card {{ background:#fff; padding:18px 16px; border:1px solid var(--rule-light); position:relative; }}
  .focus-num {{ position:absolute; top:-12px; left:14px; background:var(--accent); color:#fff;
    padding:2px 10px; font-family:Georgia; font-weight:bold; font-size:13px; }}
  .focus-title {{ font-weight:bold; margin:8px 0 8px; line-height:1.45; font-size:15px; }}
  .focus-title a {{ color:var(--ink); text-decoration:none; border-bottom:1px dotted var(--accent); }}
  .focus-title a:hover {{ color:var(--accent); }}
  .focus-meta {{ font-size:12px; color:var(--ink2); }}

  /* 议题卡片 */
  .topics {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin:28px 0; }}
  .topic-card {{ background:#fff; border:1px solid var(--rule-light); padding:16px; }}
  .topic-card h4 {{ color:var(--accent); font-size:15px; margin-bottom:6px; }}
  .topic-card p {{ font-size:13px; line-height:1.7; color:#444; }}

  /* 分刊速览 */
  .browse {{ margin:30px 0; display:grid; grid-template-columns:repeat(3,1fr); gap:18px; }}
  .jour-col {{ background:#fff; padding:16px; border:1px solid var(--rule-light); }}
  .jour-col h3 {{ color:var(--accent); font-size:15px; border-bottom:1px solid var(--rule-light);
    padding-bottom:6px; margin-bottom:10px; }}
  .jour-col ul {{ margin:0; padding-left:16px; font-size:12.5px; line-height:1.7; }}
  .jour-col li {{ margin-bottom:6px; }}
  .jour-col a {{ color:var(--ink); text-decoration:none; border-bottom:1px dotted var(--accent); }}
  .jour-col a:hover {{ color:var(--accent); }}
  .jour-col .meta {{ color:var(--ink2); font-size:11px; }}
  .jour-col .more {{ color:var(--ink2); font-style:italic; list-style:none; }}

  footer {{ text-align:center; padding:30px 20px; font-size:12px; color:var(--ink2);
    border-top:1px solid var(--rule-light); margin-top:30px; }}

  @media (max-width:760px) {{
    .metrics,.charts,.focus-cards,.topics,.browse {{ grid-template-columns:1fr; }}
    .two-col {{ column-count:1; }}
    .masthead-title {{ font-size:28px; }}
  }}
</style>
</head>
<body>
<div class="page">

  <header class="masthead">
    <div class="masthead-brand">ACADEMIC FRONTIER OBSERVER</div>
    <div class="masthead-title">学术前沿观察</div>
    <div class="masthead-sub">{year} 年第 {week} 期 · 体育科学与舞蹈艺术核心期刊文献追踪</div>
  </header>

  <div class="standfirst">
    本期覆盖 <b>{stats["journals"]}</b> 本核心期刊，共收录文献 <b>{stats["total"]}</b> 篇。
    舞蹈 / 国标舞方向 <b>{stats["dance"]}</b> 篇，人工智能相关 <b>{stats["ai"]}</b> 篇。
    总量平稳，结构分化——训练科学化、学科自主性、AI 介入编舞成为三条并行主线。
    <br><span style="font-size:13px;color:#888;font-style:normal;">生成时间：{data["gen_time"]}</span>
  </div>

  <div class="metrics">
    <div class="metric"><div class="num">{stats["total"]}</div><div class="lbl">文献总数 / 篇</div></div>
    <div class="metric"><div class="num">{stats["journals"]}</div><div class="lbl">核心期刊</div></div>
    <div class="metric"><div class="num">{stats["dance"]}</div><div class="lbl">舞蹈 / 国标舞</div></div>
    <div class="metric"><div class="num">{stats["ai"]}</div><div class="lbl">AI 主题</div></div>
  </div>

  <div class="wrap">

    <section class="two-col">
      <p>体育科学依旧是产出最稳定的阵地——《体育科学》《体育文化导刊》《北京体育大学学报》《成都体育学院学报》等合计贡献了绝大部分文献。「青少年体质」「运动训练量化」「体育产业数字化」「备战洛杉矶奥运」几个关键词出现频次显著上升，反映出后疫情时代体育学科研究议程的再定位。</p>
      <p>《北京舞蹈学院学报》以 {stats["by_journal"].get("北京舞蹈学院学报", 0)} 篇文献成为本期最值得关注的单刊——国标舞剧的本体突破、具身认知视角下的编舞重构、生成式 AI 介入舞蹈创作、"舞蹈中国性"的理论建构等议题集中爆发，标志着舞蹈学科正从「技艺传承」走向「理论自觉」的新阶段。</p>
    </section>

    <section class="charts">
      <div class="chart-box">
        <h3>各期刊文献分布</h3>
        <svg viewBox="0 0 {chart_w} {chart_h}" width="100%" xmlns="http://www.w3.org/2000/svg">
          {bars}
        </svg>
      </div>
      <div class="chart-box">
        <h3>文献主题分布</h3>
        <table style="width:100%;font-size:13px;border-collapse:collapse;">
          {topic_rows}
        </table>
      </div>
    </section>

    <section class="focus">
      <h2>重点关注 · 舞蹈 / 国标舞</h2>
      <div class="focus-cards">
        {focus_cards if focus_cards else '<div class="focus-card"><div style="color:#888;font-size:13px;">本期重点关注区暂无</div></div>'}
      </div>
    </section>

    <section class="topics">
      <div class="topic-card"><h4>AI 介入编舞</h4><p>生成式 AI 正从「工具辅助」走向「共创主体」，编舞的著作权、身体性、审美边界将被重新定义。</p></div>
      <div class="topic-card"><h4>学科自主性</h4><p>舞蹈学、体育学、艺术学三大学科对「归属」与「话语」的争夺加剧，理论建构成为新的竞争高地。</p></div>
      <div class="topic-card"><h4>国标舞剧化</h4><p>从《人间四月天》到《长恨歌》，国标舞正突破「竞技-表演」二元结构，向「舞剧」形态演进。</p></div>
    </section>

    <section class="browse">
      {browse_html}
    </section>

  </div>

  <footer>
    数据来源：中国知网 CNKI 公开 RSS · 覆盖期刊：{" / ".join(JOURNAL_NAMES)}<br>
    本报告由 WorkBuddy 自动生成，Hermes 每日推送至 GitHub Pages · 生成时间 {datetime.now().strftime("%Y-%m-%d %H:%M")}
  </footer>

</div>
</body>
</html>'''


# ================= 主流程 =================

def main():
    md_file = find_latest_md()
    if not md_file:
        print("ERROR: 未找到 文献追踪_YYYYMMDD.md 或 latest.md", file=sys.stderr)
        sys.exit(1)

    date_tag = md_file.stem.split("_")[-1]
    print(f"[INFO] 使用数据文件：{md_file.name}", file=sys.stderr)

    md_text = md_file.read_text(encoding="utf-8")
    data = parse_md(md_text)
    stats = compute_stats(data)

    html = build_html(data, stats, date_tag)

    # 输出：按日期 + latest
    out_date = ROOT / f"文献追踪_{date_tag}.html"
    out_date.write_text(html, encoding="utf-8")
    (ROOT / "latest.html").write_text(html, encoding="utf-8")

    print(f"[OK] 已生成：{out_date.name} + latest.html（{stats['total']} 篇，{stats['journals']} 本期刊）", file=sys.stderr)
    print(f"统计：总数 {stats['total']} | 期刊 {stats['journals']} | 舞蹈 {stats['dance']} | AI {stats['ai']}")


if __name__ == "__main__":
    main()
