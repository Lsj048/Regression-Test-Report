# Regression-Test-Report

审核后的回归测试 HTML 报告归档站。使用 GitHub 保存源文件、GitHub Actions 生成目录、GitHub Pages 提供公开访问。无需服务器、数据库、npm 或第三方 Python 包。

## 实际更新流程

```text
LCH 每周一 10:00 生成 HTML（北京时间）
  → 人工审核报告
  → 上传到 GitHub 仓库 uploads/ 并提交
  → Actions 检查文件、生成首页和历史目录
  → Pages 发布完整站点
```

现有测试任务继续在 LCH 运行，站点不重复执行测试。工作流没有定时触发器，只有审核后提交文件才更新公开内容。报告生成时间和公开发布时间是两个不同的时间。

## 首次部署

1. 在自己的 GitHub 账号中创建公开仓库 `Regression-Test-Report`，默认分支使用 `main`。
2. 将本项目的源文件推送到仓库，包括隐藏目录 `.github`；不要上传 `incoming`、`preview` 或 `dist`。
3. 打开仓库 **Settings → Pages → Build and deployment → Source → GitHub Actions**。
4. 打开 **Actions → Publish reviewed HTML reports → Run workflow**，选择 `main`。构建和部署都变绿后即完成上线。
5. 站点地址为 `https://<GitHub用户名>.github.io/Regression-Test-Report/`；固定最新报告地址为同一地址下的 `latest/`。

第一次运行时没有真实报告，首页显示等待导入。`examples` 里的演示文件不会部署。若第一次自动部署早于启用 Pages 而失败，完成第 3 步后手动重新运行即可。

使用 GitHub CLI 时，可在本项目目录执行（先安装并完成 `gh auth login`）：

```bash
git init -b main
git add .
git commit -m "Create regression report archive"
gh repo create Regression-Test-Report --public --source=. --remote=origin --push
# 将 OWNER 替换为当前 GitHub 用户名
gh api --method POST repos/OWNER/Regression-Test-Report/pages -f build_type=workflow
gh workflow run pages.yml
```

提交作者使用你自己的 Git 配置。现有 Git 仓库无需重新初始化。如果 GitHub 提示仓库重名，先检查该仓库，不要覆盖现有内容。

## 每周上传：推荐使用 GitHub 网页

1. 在 LCH 的 `/Users/iie/Desktop/LCH-回归测试报告` 中取出当期 HTML，完成内容审核。
2. 打开仓库里的 `uploads` 目录，选择 **Add file → Upload files**。
3. 上传如 `2026-10-19.html`，提交到 `main`。提交即代表该文件可以公开发布。
4. 等待本次 Actions 运行成功，再打开站点和 `latest/` 查看结果。

单 HTML 文件名必须是 `YYYY-MM-DD.html`。同一天的另一轮测试请使用 `YYYY-MM-DD--r2.html`，例如 `2026-10-19--r2.html`。不要覆盖旧文件，这样历史列表中会保留每一轮。若确实替换同名文件，网站显示新内容，旧内容只能从 Git 提交历史恢复。

最新报告按报告日期倒序排列；同日使用文件最近提交时间，再以运行编号排序。补传较早的报告不会挤掉最新一期。页面上的“通过”“失败”取自可选元数据；仅上传 HTML 时显示“未标注”，不会从正文猜测结果。

### 从本机取回 LCH 报告

本机已有 `ssh LCH` 配置时：

```bash
python3 scripts/fetch_lch.py 2026-10-19
open incoming/2026-10-19.html
```

下载脚本只把文件放到本地 `incoming/`，不会上传。`incoming/` 已被 Git 忽略。审核通过后，可在 GitHub 网页选择该文件；也可在本地执行：

```bash
git pull --ff-only
cp incoming/2026-10-19.html uploads/2026-10-19.html
python3 scripts/report_site.py build
git add uploads/2026-10-19.html
git commit -m "Publish reviewed report for 2026-10-19"
git push origin main
```

### 可选：为首页补充标题和测试结果

与 HTML 同时上传同名 `.json`。例如 `uploads/2026-10-19.json`：

```json
{
  "title": "LCH 回归测试 · 2026-10-19",
  "status": "failed",
  "summary": "示例文字：主要流程已验证，失败项见报告正文。",
  "metrics": { "passed": 48, "failed": 2, "skipped": 1 }
}
```

以上是格式示例，数字必须替换为真实结果。`status` 可为 `passed`、`failed`、`unknown`；`metrics` 可省略，提供时三个字段都必须是非负整数。失败数大于零却标为通过，会导致构建失败。请一次提交 HTML 和 JSON，孤立的 JSON 会被拒绝。

### HTML 带图片、CSS 或其他附件

将完整报告目录放入 `uploads/YYYY-MM-DD--名称/`，默认入口是 `index.html`。保持原有相对路径：

```text
uploads/
  2026-10-19--full/
    index.html
    assets/
      chart.png
      report.css
  2026-10-19--full.json
```

如入口是 `pages/report.html`，在同名 JSON 中设置 `"entry": "pages/report.html"`。单文件上传保留原始文件名；多文件目录整体复制，文件内容不改写。站点使用项目相对链接，支持 GitHub Pages 的仓库子路径。

报告中引用的 `/assets/...` 这类站点根路径、`file://` 或内网地址不会自动修复；导出时应使用相对路径或将资源内嵌。必须是浏览器能直接打开的静态 HTML；需要运行 Python 服务、登录后端或实时查询数据库的报告无法仅靠 Pages 运行。

## 本地预览和验证

需要 Python 3.9 或更高版本。CI 使用 Python 3.12，默认时区为 `Asia/Shanghai`。

```bash
python3 -m unittest discover -s tests -v
python3 scripts/report_site.py build
python3 -m http.server 8000 --directory dist --bind 127.0.0.1
```

打开 `http://127.0.0.1:8000`。浏览器需刷新才能看到重新构建的内容。也可直接打开 `dist/index.html`，首页筛选不依赖网络 API。

查看带虚构数据的独立演示：

```bash
python3 scripts/demo.py
python3 -m http.server 8001 --directory preview --bind 127.0.0.1
```

`preview/` 与正式站点隔离，不会上传到 Pages。演示报告均明确标注为非真实测试结果。

## 目录与维护

| 路径 | 用途 |
| --- | --- |
| `uploads/` | 审核通过的报告源文件，长期保留 |
| `site.json` | 首页标题、说明和更新时间文字 |
| `web/` | 首页模板、样式和搜索筛选 |
| `scripts/report_site.py` | 报告归档、校验、静态站点生成 |
| `scripts/fetch_lch.py` | 按日期下载一份报告到待审核目录 |
| `.github/workflows/pages.yml` | 校验、构建和部署 |
| `reports/` | 使用高级 `add` 命令导入的归档，可留空 |
| `dist/` | 生成的正式站点，不提交到 Git |

高级导入可用 `python3 scripts/report_site.py add /path/to/report.html --date 2026-10-19 --run-id reviewed-1`。此方式把原文件和元数据写入 `reports/`，提交该目录即可发布；日常使用 `uploads/` 更直观。上传来源不会被本地构建改写。

每次发布都从仓库内全部报告重建，不依赖临时 Actions 缓存，因此旧报告不会因缓存过期消失。构建失败时不会运行部署，在线站点保留上一版。HTML 中的脚本可正常执行，因此只发布自己审核认可的报告。公开仓库和 Pages 的文件都可以被访问；审核时一并检查报告、附件中是否有不应公开的内容。

单份报告当前限制为 100 MiB，并拒绝符号链接、隐藏文件及非报告附件类型。大型视频等建议另行托管。累积体积需要符合 [GitHub Pages 使用限制](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)。

### 常见问题

- **Action 构建失败**：查看 build 日志；通常是日期文件名错误、入口缺失、统计矛盾或 JSON 不合法。修复源文件后重新提交。
- **部署提示 Pages 未启用**：在 Settings → Pages 选择 GitHub Actions，再重新运行。
- **找不到每周定时任务**：定时任务在 LCH 上；本仓库只负责人工审核后的发布。
- **上传后没有立刻变化**：先确认 Actions 成功，再刷新页面。缓存和部署可能使更新延迟数分钟。
- **需要撤回某份报告**：删除对应 HTML/目录及同名 JSON，提交后重建；历史公开 Git 提交仍会保留原文件。
- **想恢复站点上一版**：撤销导致问题的提交，再让 Actions 发布；不要强制覆盖仓库历史。

## 参考依据

- 参考站点 `lssbc202.github.io/ai_research/agent-harness-post-training/` 使用 GitHub Pages，页面源码带有 mdBook 资源标记。本项目采用类似的目录浏览方式，直接保存已有 HTML。
- [GitHub Pages 静态站点说明](https://docs.github.com/en/pages/getting-started-with-github-pages/about-github-pages)
- [配置 Pages 发布源](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
- [通过 Actions 部署 Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
