# Regression-Test-Report

审核后的回归测试 HTML 报告归档站。使用 GitHub 保存源文件、GitHub Actions 生成目录、GitHub Pages 提供公开访问。无需服务器、数据库、npm 或第三方 Python 包。

## 当前站点与上传入口

- [公开报告站点](https://lsj048.github.io/Regression-Test-Report/)
- [固定最新报告链接](https://lsj048.github.io/Regression-Test-Report/latest/)
- [上传审核后的 HTML](https://github.com/Lsj048/Regression-Test-Report/upload/main/uploads)
- [查看发布状态](https://github.com/Lsj048/Regression-Test-Report/actions/workflows/pages.yml)

日常更新只需上传当期 `YYYY-MM-DD.html` 并提交到 `main`，等待本次发布成功即可。没有报告时，站点显示等待导入。

## 实际更新流程

```text
LCH 每周一 10:00 生成 HTML（北京时间）
  → 人工审核报告
  → 上传到 GitHub 仓库 uploads/ 并提交
  → Actions 检查文件、生成首页和历史目录
  → Pages 发布完整站点
```

现有测试任务继续在 LCH 运行，站点不重复执行测试。工作流没有定时触发器，只有审核后提交文件才更新公开内容。报告生成时间和公开发布时间是两个不同的时间。

## 首次部署到其他仓库

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

## 每周上传：推荐一键脚本

审核完成后，在本项目目录运行，参数是报告日期：

```bash
./publish.sh 2026-10-26
```

执行命令表示当期报告已经审核，可以公开发布。脚本不创建定时任务，不跳过人工审核。

脚本自动连接 `ssh LCH`，下载对应日期的 HTML，在独立临时 Git 副本中构建，只提交本次报告和摘要，然后等待该提交的 GitHub Actions 部署。最后从公网检查报告 HTML 内容、首页索引、`latest/` 重定向和 CSS/JS 文件；验收通过后输出报告地址，并在本地 `incoming/publish-日期.json` 保存提交号、工作流地址和文件校验值。

首次使用需要 Python 3.9+、Git、SSH，以及已登录的 GitHub CLI（`gh`）。本机的 GitHub CLI 路径已配置，直接运行即可。在另一台 Mac 上可先执行 `brew install gh`，然后 `gh auth login --hostname github.com --git-protocol https --web --scopes workflow`，并配置好 `ssh LCH`。也可通过 `--gh /绝对路径/gh` 或环境变量 `GH_BIN` 指定 CLI。

```bash
# 内容相同：不会重复提交，会重新检查发布结果
./publish.sh 2026-10-19

# 同一天的另一版：保留第一版，新增 r2
./publish.sh 2026-10-19 --run-id r2

# 不重新下载，只检查已上传版本；必要时重试失败的部署
./publish.sh 2026-10-19 --check-only

# 延长等待部署的时间，单位为秒
./publish.sh 2026-10-19 --timeout 1800
```

同日期、同版本若内容不同，脚本会停止，要求使用新版本编号；不会覆盖旧报告。它不会提交本地其他未提交改动，也不强制推送。网络或部署失败后，修复原因，再运行同一条命令即可；已上传的相同报告会被复用，失败的工作流可重新运行。默认最多等待部署 20 分钟、线上缓存更新 3 分钟，失败时退出码为非零，并输出原因。

补传旧日期时，`latest/` 仍指向日期最新的报告；脚本按这一规则验收。发布使用临时副本，因此本地仓库不会被自动拉取或改动；需要查看新发布的本地归档时，可自行执行 `git pull --ff-only`。

对已识别的 LCH 标准报告，脚本提取明确写出的成功/失败摘要，并补充手机端表格横向滚动样式；未知报告格式标为“未标注”。不会推断缺失的统计，也不会随 HTML 上传 `file://` 附件。自动验收核对文件与链接，不代替对报告内容和图表的人工审核。

仓库、SSH 别名和远端报告目录在 `publish.json` 中配置。

### 直接在 LCH 机器上上传

LCH 本机已有报告时，使用 `--local`，直接读取 `/Users/iie/Desktop/LCH-回归测试报告/YYYY-MM-DD.html`。该目录来自 `publish.json` 的 `remote_directory`，无需配置 SSH 连接自己。

首次在 LCH 上使用，需要 Git、Python 3.9+ 和 GitHub CLI。若已安装 Homebrew，可用 `brew install git python gh` 安装缺少的工具。然后登录具有本仓库写权限的 GitHub 账号并获取项目：

```bash
gh auth login --hostname github.com --git-protocol https --web --scopes workflow
# 按提示完成网页授权；通过 SSH 操作 LCH 时，可在自己的电脑浏览器输入终端显示的验证码。
git clone https://github.com/Lsj048/Regression-Test-Report.git
cd Regression-Test-Report
```

如果 LCH 上已经有这个仓库，进入已有目录执行 `git pull --ff-only` 更新脚本即可。另一台电脑上的 GitHub CLI 登录不会自动同步到 LCH，需要在 LCH 上单独授权。

每周审核后，在仓库目录执行（替换日期）：

```bash
./publish.sh 2026-10-26 --local
```

只读取这一份 HTML，不扫描或批量上传其他报告，也不修改原报告。发布、重复内容检测、版本保留和线上验收与默认模式相同。看到 `[6/6] 发布验收通过` 表示完成。

报告目录变更时，可直接指定：

```bash
./publish.sh 2026-10-26 --local-dir "/其他目录/回归报告"
```

同日修订版使用 `./publish.sh 2026-10-26 --local --run-id r2`；只复查已上传报告使用 `./publish.sh 2026-10-26 --check-only`。`--local` 和 `--local-dir` 二选一；不传这两个参数时仍默认从 `ssh LCH` 下载。

## 每周上传：也可使用 GitHub 网页

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
| `publish.sh`、`scripts/publish_report.py` | 一键下载、发布、等待部署并核对线上内容 |
| `publish.json` | 发布目标、SSH 别名和远端报告目录 |
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
