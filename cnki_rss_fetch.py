#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知网核心期刊 RSS 抓取脚本 v2.0
每周执行一次，抓取最新论文，生成结构化 Markdown 报告。

功能：
  - 网络重试（3 次，指数退避）
  - 关键词高亮：舞蹈/国标舞/摩登舞/探戈/狐步 等相关论文置顶展示
  - 自动去重：只展示上次抓取后新增的文献
  - 支持 --force 参数：强制展示全部（忽略去重状态）

RSS 源（知网公开 RSS，无需校园网）：
  TYKX - 体育科学        TYWS - 体育文化导刊
  BJTD - 北京体育大学学报   SORT - 成都体育学院学报
  GZTX - 广州体育学院学报   WTXB - 武汉体育学院学报
  BJWD - 北京舞蹈学院学报
"""

import sys
import json
import hashlib
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import ssl
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from html import unescape


# ==================== 配置 ====================

BASE_RSS_URL = "https://rss.cnki.net/knavi/rss/{code}?pcode=CJFD,CCJD"

RSS_SOURCES = {
    "TYKX": "体育科学",
    "TYWS": "体育文化导刊",
    "BJTD": "北京体育大学学报",
    "SORT": "成都体育学院学报",
    "GZTX": "广州体育学院学报",
    "WTXB": "武汉体育学院学报",
    "BJWD": "北京舞蹈学院学报",
    "STYB": "上海体育大学学报",  # 新增：2026-07-13
}

# 关键词高亮：匹配到的论文会在"重点关注"区置顶
DANCE_KEYWORDS = [
    "舞蹈", "国标舞", "摩登舞", "探戈", "狐步", "华尔兹", "维也纳",
    "拉丁", "伦巴", "恰恰", "华尔兹", "体育舞蹈", "形体", "身韵",
    "编舞", "编创", "舞台", "表演", "剧场", "演出", "剧目",
    "芭蕾", "民间舞", "民族舞", "舞蹈教育", "舞蹈训练",
    "周子骞", "周志平",  # 可扩展：关注的学者
]

OUTPUT_DIR = Path(__file__).parent / "文献追踪"
STATE_FILE = OUTPUT_DIR / ".rss_state.json"
MAX_RETRIES = 3
RETRY_DELAY = 2  # 秒（指数退避基数）
REQUEST_TIMEOUT = 30
ITEMS_PER_JOURNAL = 15  # 每刊最多展示条目数

CST = timezone(timedelta(hours=8))


# ==================== 网络抓取（带重试） ====================

def fetch_rss(url: str) -> str | None:
    """抓取 RSS XML 内容，支持 3 次重试 + 指数退避"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    # 跳过 SSL 验证（知网证书在某些环境不匹配）
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=REQUEST_TIMEOUT, context=ctx) as resp:
                data = resp.read()
                for enc in ("utf-8", "gbk", "gb2312", "latin-1"):
                    try:
                        return data.decode(enc)
                    except UnicodeDecodeError:
                        continue
                return data.decode("utf-8", errors="replace")
        except (URLError, HTTPError, Exception) as e:
            print(f"[WARN] 第 {attempt}/{MAX_RETRIES} 次抓取失败 {url}: {e}", file=sys.stderr)
            if attempt < MAX_RETRIES:
                wait = RETRY_DELAY * (2 ** (attempt - 1))
                print(f"[INFO] {wait}s 后重试...", file=sys.stderr)
                time.sleep(wait)
    print(f"[ERROR] 最终失败：{url}", file=sys.stderr)
    return None


# ==================== RSS 解析 ====================

def parse_rss_manually(xml_text: str) -> list[dict]:
    item_pattern = re.compile(r"<item>(.*?)</item>", re.DOTALL)
    title_pattern = re.compile(r"<title>(.*?)</title>", re.DOTALL)
    link_pattern = re.compile(r"<link>(.*?)</link>", re.DOTALL)
    desc_pattern = re.compile(r"<description>(.*?)</description>", re.DOTALL)
    author_pattern = re.compile(r"<author>(.*?)</author>", re.DOTALL)
    date_pattern = re.compile(r"<pubDate>(.*?)</pubDate>", re.DOTALL)

    items = []
    for m in item_pattern.finditer(xml_text):
        block = m.group(1)
        item = {}
        t = title_pattern.search(block)
        item["title"] = unescape(t.group(1).strip()) if t else ""
        l = link_pattern.search(block)
        item["link"] = unescape(l.group(1).strip()) if l else ""
        d = desc_pattern.search(block)
        item["description"] = unescape(d.group(1).strip()) if d else ""
        a = author_pattern.search(block)
        item["author"] = unescape(a.group(1).strip()) if a else ""
        pd = date_pattern.search(block)
        item["pub_date"] = pd.group(1).strip() if pd else ""
        items.append(item)
    return items


def get_item_id(item: dict) -> str:
    raw = item.get("link") or item.get("title", "")
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def is_dance_related(item: dict) -> bool:
    text = (item.get("title", "") + item.get("description", "")).lower()
    return any(kw in text for kw in DANCE_KEYWORDS)


# ==================== 状态管理 ====================

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"seen_ids": [], "last_run": None}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ==================== 报告生成 ====================

def format_pub_date(raw: str) -> str:
    """将 RSS pubDate 转为可读格式"""
    if not raw:
        return ""
    # 格式如 "Sat, 14 Feb 2026 16:00:00 GMT"
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(raw)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return raw


def generate_report(all_items: dict[str, list[dict]], failed: list[str]) -> str:
    now = datetime.now(CST)
    date_str = now.strftime("%Y-%m-%d %H:%M")

    total = sum(len(v) for v in all_items.values())
    dance_items = []  # 收集所有舞蹈相关论文

    # 先收集舞蹈相关
    for code, items in all_items.items():
        for item in items:
            if is_dance_related(item):
                dance_items.append((code, item))

    lines = [
        "# 知网核心期刊文献追踪周报",
        "",
        f"> 生成时间：{date_str}",
        f"> 数据来源：中国知网（CNKI）公开 RSS",
        f"> 本期新增：**{total}** 篇（覆盖 {len(RSS_SOURCES)} 本期刊）",
        "",
    ]

    if failed:
        lines.append(f"> ⚠️ 抓取失败：{', '.join(failed)}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ---- 重点关注 ----
    if dance_items:
        lines.append("## 🎯 重点关注（舞蹈/国标舞相关）")
        lines.append("")
        for code, item in dance_items:
            journal = RSS_SOURCES[code]
            title = item.get("title", "")
            authors = item.get("author", "").rstrip(";")
            link = item.get("link", "")
            pub_date = format_pub_date(item.get("pub_date", ""))
            date_part = f" · {pub_date}" if pub_date else ""
            if link:
                lines.append(f"- [{title}]({link})")
            else:
                lines.append(f"- {title}")
            meta = f"  - {journal} | {authors}{date_part}"
            lines.append(meta)
            lines.append("")
        lines.append("---")
        lines.append("")

    # ---- 分刊列表 ----
    lines.append("## 📚 分刊详情")
    lines.append("")

    for code, name in RSS_SOURCES.items():
        items = all_items.get(code, [])
        lines.append(f"### {name}（{len(items)} 篇）")
        lines.append("")

        if not items:
            lines.append("*本期无新增*")
            lines.append("")
            continue

        for i, item in enumerate(items, 1):
            title = item.get("title", "无标题")
            authors = item.get("author", "").rstrip(";")
            desc = item.get("description", "")
            link = item.get("link", "")
            pub_date = format_pub_date(item.get("pub_date", ""))

            # 舞蹈相关加星标
            star = "⭐ " if is_dance_related(item) else ""

            if link:
                lines.append(f"{i}. {star}[{title}]({link})")
            else:
                lines.append(f"{i}. {star}{title}")

            meta_parts = []
            if authors:
                meta_parts.append(authors)
            if pub_date:
                meta_parts.append(pub_date)
            if meta_parts:
                lines.append(f"   {' | '.join(meta_parts)}")

            if desc:
                # 截断摘要避免过长
                short_desc = desc[:120] + ("..." if len(desc) > 120 else "")
                lines.append(f"   > {short_desc}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # 尾部统计
    lines.append(f"**统计**：{len(RSS_SOURCES)} 本期刊 | {total} 篇新增" +
                 (f" | 舞蹈相关 {len(dance_items)} 篇" if dance_items else ""))
    lines.append("")

    return "\n".join(lines)


# ==================== 主流程 ====================

def main():
    force_mode = "--force" in sys.argv
    print(f"[INFO] 开始抓取知网核心期刊 RSS（force={force_mode}）...", file=sys.stderr)

    state = load_state()
    seen_ids = set(state.get("seen_ids", []))

    all_items = {}
    failed_sources = []

    for code, name in RSS_SOURCES.items():
        url = BASE_RSS_URL.format(code=code)
        print(f"[INFO] 正在抓取：{name}", file=sys.stderr)

        xml_text = fetch_rss(url)
        if not xml_text:
            failed_sources.append(name)
            all_items[code] = []
            continue

        items = parse_rss_manually(xml_text)
        print(f"[INFO] {name}：解析到 {len(items)} 篇", file=sys.stderr)

        if force_mode:
            # --force 模式：展示全部
            all_items[code] = items[:ITEMS_PER_JOURNAL]
            for item in items:
                seen_ids.add(get_item_id(item))
        else:
            # 正常模式：只展示新增
            new_items = []
            for item in items:
                iid = get_item_id(item)
                if iid not in seen_ids:
                    new_items.append(item)
                    seen_ids.add(iid)
            all_items[code] = new_items[:ITEMS_PER_JOURNAL]
            print(f"[INFO] {name}：新增 {len(new_items)} 篇", file=sys.stderr)

    # 生成报告
    report = generate_report(all_items, failed_sources)

    # 保存
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_tag = datetime.now(CST).strftime("%Y%m%d")
    report_file = OUTPUT_DIR / f"文献追踪_{date_tag}.md"
    report_file.write_text(report, encoding="utf-8")

    latest = OUTPUT_DIR / "latest.md"
    latest.write_text(report, encoding="utf-8")

    print(f"[INFO] 报告已保存：{report_file}", file=sys.stderr)

    # 更新状态
    seen_list = list(seen_ids)
    if len(seen_list) > 500:
        seen_list = seen_list[-500:]
    state["seen_ids"] = seen_list
    state["last_run"] = datetime.now(CST).isoformat()
    save_state(state)

    # stdout 摘要
    total = sum(len(v) for v in all_items.values())
    dance_count = sum(1 for items in all_items.values() for it in items if is_dance_related(it))
    print(f"抓取完成：{len(RSS_SOURCES)} 本期刊，{total} 篇新增，"
          f"舞蹈相关 {dance_count} 篇" +
          (f"，失败 {len(failed_sources)} 本" if failed_sources else ""))


if __name__ == "__main__":
    main()
