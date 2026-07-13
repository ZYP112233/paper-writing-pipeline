# 论文撰写全流程 · 文献追踪自动化系统

> 知网核心期刊 RSS 抓取 → 报刊风格 HTML 周报 → GitHub Pages 自动部署

---

## 快速开始

### 1. 本地运行

```bash
# 安装依赖（标准库即可，无需额外安装）
python --version  # 需要 3.10+

# 运行完整管线
python run_pipeline.py          # 去重模式（只展示新增）
python run_pipeline.py --force  # 强制模式（展示全部）
```

### 2. 输出文件

```
文献追踪/
├── 文献追踪_YYYYMMDD.md      # Markdown 报告
├── 文献追踪_YYYYMMDD.html    # 报刊风格 HTML
├── latest.md                 # 最新版 Markdown
└── latest.html               # 最新版 HTML

docs/
└── index.html                # GitHub Pages 部署文件
```

### 3. 部署到 GitHub Pages

```bash
# 首次提交
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main

# 启用 GitHub Pages
# 1. 进入仓库 Settings → Pages
# 2. Source 选择：Deploy from a branch
# 3. Branch 选择：gh-pages / root
# 4. 保存后等待 1-2 分钟
```

访问：`https://<你的用户名>.github.io/<仓库名>/`

---

## 自动化配置

### GitHub Actions（推荐）

已配置 `.github/workflows/weekly-report.yml`，自动执行：

- **触发时间**：每周一早上 10:00 (UTC+8)
- **功能**：抓取 RSS → 生成 HTML → 部署到 GitHub Pages
- **手动触发**：仓库 → Actions → 选择 workflow → Run workflow

### Hermes 定时任务（本地）

详见 [`HERMES_SETUP.md`](HERMES_SETUP.md)

---

## 项目结构

```
论文撰写全流程/
│
├── cnki_rss_fetch.py              # 知网 RSS 抓取脚本
├── run_pipeline.py                # 一键管线：抓取 + 生成 + 部署准备
│
├── 文献追踪/
│   ├── build_report.py            # Markdown → 报刊风格 HTML
│   ├── 文献追踪_YYYYMMDD.md       # 历史报告
│   ├── 文献追踪_YYYYMMDD.html     # 历史 HTML
│   ├── latest.md                  # 最新 Markdown
│   ├── latest.html                # 最新 HTML
│   └── .rss_state.json            # 去重状态（不提交）
│
├── docs/
│   └── index.html                 # GitHub Pages 部署文件
│
├── .github/
│   └── workflows/
│       └── weekly-report.yml      # GitHub Actions 配置
│
├── HERMES_SETUP.md                # Hermes 配置说明
├── .gitignore                     # Git 忽略规则
└── README.md                      # 本文件
```

---

## 核心脚本说明

### 1. `cnki_rss_fetch.py`

**功能**：抓取知网核心期刊 RSS，生成结构化 Markdown 报告

**覆盖期刊**：
- 体育科学
- 体育文化导刊
- 北京体育大学学报
- 成都体育学院学报
- 广州体育学院学报
- 武汉体育学院学报
- 北京舞蹈学院学报

**特色功能**：
- 网络重试（3 次指数退避）
- 关键词高亮：舞蹈/国标舞相关论文置顶
- 自动去重：只展示上次抓取后新增的文献
- 支持 `--force` 参数：强制展示全部

### 2. `文献追踪/build_report.py`

**功能**：读取 `文献追踪_YYYYMMDD.md`，生成报刊风格 HTML

**设计参考**：
- 《经济学人》/FT 财经社论风格
- 米白浅暖底、衬线大标题、暗红主色点缀
- 多栏报刊排版、首字下沉
- 内联 SVG 图表（期刊分布柱状图、主题分布表格）
- 重点关注卡片（舞蹈/国标舞论文）
- 响应式布局（移动端适配）

### 3. `run_pipeline.py`

**功能**：一键执行完整流程

**执行步骤**：
1. 运行 `cnki_rss_fetch.py` 抓取 RSS
2. 运行 `文献追踪/build_report.py` 生成 HTML
3. 复制 `latest.html` → `docs/index.html`（部署准备）

---

## 自定义配置

### 修改期刊列表

编辑 `cnki_rss_fetch.py` 第 36-44 行：

```python
RSS_SOURCES = {
    "TYKX": "体育科学",
    "TYWS": "体育文化导刊",
    # 添加新期刊...
}
```

### 修改舞蹈关键词

编辑 `cnki_rss_fetch.py` 第 47-53 行：

```python
DANCE_KEYWORDS = [
    "舞蹈", "国标舞", "摩登舞",
    # 添加新关键词...
]
```

### 修改 HTML 样式

编辑 `文献追踪/build_report.py` 中的 CSS 变量：

```python
:root {
  --bg: #f5f1eb;      # 背景色
  --accent: #8b1a1a;  # 强调色
  --paper: #faf7f2;   # 纸张色
}
```

---

## 故障排查

### RSS 抓取失败

- 检查网络连接
- 知网 RSS 可能有访问频率限制，等待 5-10 分钟重试
- 查看 `文献追踪/.rss_state.json` 是否损坏

### HTML 未生成

- 确认 `文献追踪/latest.md` 存在
- 检查 Python 版本（需要 3.10+）
- 运行 `python 文献追踪/build_report.py` 单独测试

### GitHub Pages 未更新

- 检查 `.github/workflows/weekly-report.yml` 是否正确提交
- 查看 GitHub Actions 日志
- 确认 Settings → Pages 配置正确

---

## 技术栈

- **Python 3.10+**：核心运行环境
- **标准库**：urllib, re, json, pathlib（无需额外安装）
- **GitHub Actions**：自动化部署
- **GitHub Pages**：静态网站托管

---

## 许可证

本项目仅供学术研究和教学使用。

---

## 联系方式

如有问题或建议，欢迎反馈。
