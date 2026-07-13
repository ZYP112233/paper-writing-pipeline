# 文献追踪自动化系统

## 快速开始

### 手动运行（本地测试）

```bash
# 正常模式（去重，只展示新增）
python run_pipeline.py

# 强制模式（展示全部，忽略去重）
python run_pipeline.py --force
```

### 输出文件

```
文献追踪/
├── 文献追踪_YYYYMMDD.md      # Markdown 报告
├── 文献追踪_YYYYMMDD.html    # 报刊风格 HTML
├── latest.md                 # 最新版 Markdown
└── latest.html               # 最新版 HTML

docs/
└── index.html                # GitHub Pages 部署文件
```

---

## Hermes 配置

### 方式一：GitHub Actions（推荐）

已配置 `.github/workflows/weekly-report.yml`，自动执行：
- **触发时间**：每周一早上 10:00 (UTC+8)
- **功能**：抓取 RSS → 生成 HTML → 部署到 GitHub Pages
- **在线查看**：`https://<你的用户名>.github.io/<仓库名>/`

#### 启用 GitHub Pages：

1. 推送代码到 GitHub
2. 进入仓库 Settings → Pages
3. Source 选择：`Deploy from a branch`
4. Branch 选择：`gh-pages` / `root`
5. 保存后等待 1-2 分钟

---

### 方式二：Hermes 定时任务（本地）

#### 1. 创建 Hermes 任务

在 Hermes 中创建新任务，配置如下：

```json
{
  "name": "文献追踪周报",
  "type": "command",
  "schedule": {
    "type": "weekly",
    "day": "monday",
    "time": "10:00",
    "timezone": "Asia/Shanghai"
  },
  "command": "cd C:\\Users\\54778\\Desktop\\论文撰写全流程 && python run_pipeline.py --force",
  "working_directory": "C:\\Users\\54778\\Desktop\\论文撰写全流程",
  "env": {
    "PYTHONIOENCODING": "utf-8"
  }
}
```

#### 2. 自动推送 HTML 到 GitHub（可选）

创建 `push_to_github.bat`（Windows）：

```batch
@echo off
cd /d C:\Users\54778\Desktop\论文撰写全流程
git add docs/
git add 文献追踪/
git commit -m "📊 自动生成文献追踪周报 %date:~0,4%%date:~5,2%%date:~8,2%"
git push
```

然后在 Hermes 任务中添加第二步：

```json
{
  "name": "文献追踪周报",
  "type": "command",
  "schedule": {
    "type": "weekly",
    "day": "monday",
    "time": "10:00",
    "timezone": "Asia/Shanghai"
  },
  "commands": [
    {
      "command": "cd C:\\Users\\54778\\Desktop\\论文撰写全流程 && python run_pipeline.py --force"
    },
    {
      "command": "C:\\Users\\54778\\Desktop\\论文撰写全流程\\push_to_github.bat"
    }
  ]
}
```

---

## 文件说明

### 核心脚本

| 文件 | 功能 |
|------|------|
| `cnki_rss_fetch.py` | 知网 RSS 抓取，生成 Markdown |
| `文献追踪/build_report.py` | Markdown → 报刊风格 HTML |
| `run_pipeline.py` | 一键执行：抓取 + 生成 + 部署准备 |

### 配置文件

| 文件 | 功能 |
|------|------|
| `.github/workflows/weekly-report.yml` | GitHub Actions 自动部署 |
| `文献追踪/.rss_state.json` | 去重状态（记录已见文献 ID） |

---

## 自定义

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

## 联系

如有问题，检查：
1. GitHub Actions 日志：仓库 → Actions → 最新 workflow run
2. 本地日志：运行脚本时的 stdout/stderr 输出
3. 状态文件：`文献追踪/.rss_state.json`
