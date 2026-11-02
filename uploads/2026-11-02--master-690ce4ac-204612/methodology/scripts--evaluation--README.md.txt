# 本地回归评测操作手册

本文维护流水线、工具链、运行命令和产物位置。文档分工见[入口](../../docs/testing/README.md)；归因方法统一见[失败归因指南](../../docs/testing/failure-attribution.md)。

最新结果见 [Case 台账](../../test/e2e/cases/README.md)，不要把定向验证写成正式全集通过。

## 1. 首次准备

直接在当前代码树开发或排障前，先安装锁定依赖和 Chromium：

```bash
npm ci
npm run test:e2e:install
```

项目使用 `package-lock.json` 固定依赖，评测总入口还会在临时源码树中重新安装依赖和浏览器。不要使用全局包替代 lockfile 中的版本。

## 2. 两个完整入口

### 2.1 确定性基础自检与异常恢复

```bash
LCH_EVAL_PROFILE=deterministic LCH_EVAL_REPEAT_EACH=5 npm run evaluate:local
```

这是默认通路，不需要真实模型密钥。它会准备临时源码树、固定工具链、安装依赖、执行类型检查、运行确定性 Playwright 基础自检及项目自动测试，最后核对运行产物。

该通路运行`standard.infrastructure-smoke`及已注册的确定性异常Case。基础自检不调用业务Tool；业务Case按声明执行真实Tool、故障和恢复审计，不证明真实模型选路能力。阶段资格及未收敛项以Case台账为准，不能因为注册了就计稳定。

崩溃窗口Case只终止自己启动的隔离Host，不操作8088。除常规audit、timings、service log外，保留`recovery-before.json`（实际故障窗口）、`recovery-state.json`（恢复后耐久事实）和`recovery-fixture.json`（模型交换与旧/新进程身份）；失败也应在环境清理前落盘。它们不能由重跑后的成功状态补写，缺少窗口证据时不得声称已覆盖该恢复路径。

当前确定性替身 revision 为 `deterministic-model-server.v5`。自检按运行时发现结果核对 Mode 标识合法、唯一并包含必要 Mode，不再假定系统恰好只有 `assistant`、`ptc`、`standard` 三项；Standard 请求中的固定自检任务、Plan entry guidance 和时间上下文按语义各核对一次，不固定相邻 user 消息是否被 Provider 聚合、消息总数或内容块位置。当前 Standard 的 Contract Ledger 在 binding 中明确 `enabled=false`，自检要求零 Ledger 服务调用和零 Ledger 私态；不要重新启用该组件来匹配旧 v4 剧本。该 smoke 不会实际进入 Plan，Plan 审批和退出流程需要独立 Case。

模型产物统一使用套件身份`deterministic-model-suite.v19`，基础自检脚本仍为v5，故障脚本身份另记在`deterministic-fixture.json`及audit中。上述命令会执行当前注册全集；开发调试可用`LCH_EVAL_PROFILE=deterministic npm run test:e2e -- --grep 'deterministic-provider-500-recovery'`选择单项，确定性单项开发资格另开冻结版本三轮，全量仍要求五轮。保留计划内故障，不送入网络补样；替身校验失败不能冒充注入500。429沿用生产65秒基础退避及最多30秒抖动，不能为加速实验修改产品参数。已有干净隔离树可使用`npm run evaluate:ci`完成无远端拉取的确定性联合检查；这不证明已合并最新master。

冷子任务和MCP恢复另外保留`child-before-crash.json`或`registration-before-crash.json`及旧/新Host身份；MCP RPC按进程generation关联，新的客户端请求ID可能从头计数，不能跨进程要求传输ID全局唯一。外置结果故障保留实际Policy观察及删除前的原文件证据。到达批次修正上限的Case保留代码和失败证据，不借共享修复静态计PASS；是否存在暂缓项以当前 Case 台账为准，不静默筛掉失败项后报告原全集通过。

回答落盘和取消补消息窗口另保存`approval-before-crash.json`或`cancellation-before-crash.json`以及夹具的Host重启记录。计划内两次崩溃只用于`host-approval-cancel-crash`，不是Playwright retry；其他重启Case仍默认最多一次。故障标记只用于定位挂起，不能替代独立数据库检查。取样期间不得修改源码或重建共享dist。

PTC嵌套异常另保存`nested-backend.json`，便于区分执行保护失败与页面冷投影失败。该附件只证明其中已核对的后台事实，不能替代整例PASS或常规准出附件。

筛选Case时，Playwright的grep匹配完整测试标题，而不是终端排版中的`›`分隔符。可用`--grep 'standard\.deterministic-host-approval-restart( |$)'`精确选择一项，先加`--list`确认集合；`No tests found`不是业务FAIL，更不能作为成功样本。冻结分批取样后按实际选择的Contract校验附件，不冒充整份profile准出；计划内SIGKILL、拒绝及硬限制失败不进入外部网络补样。

### 2.2 真实模型评测

确定性实验发现并修复生产代码后，按改动面复验已有Case：PTC取消修复需重跑直接程序异常与取消；后台读取取消修复需重跑启动、输出等待、停止及资源清理。冻结全集结果与单批结果分别记录。它们不会自动更新live资格；恢复live实验时仍需定向复验相应PTC/进程Case。若测试因已知Kernel缺陷失败，保留失败并报告阻断，不临时排除后宣称原全集通过。

```bash
LCH_EVAL_PROFILE=live \
LCH_EVAL_ALLOW_LIVE=1 \
LCH_EVAL_LIVE_MODEL=LongCat-2.0 \
LCH_EVAL_LIVE_BASE_URL=https://provider.example/v1 \
LCH_EVAL_LIVE_API_KEY=... \
LCH_EVAL_LIVE_MODEL_REVISION=provider-unreported \
npm run evaluate:local
```

这条通路运行当前 `live` profile 选择的全部可执行真实模型 Playwright Case，是 G1 的主要执行入口。注册表中标为 `pending_requalification` 的Case暂不执行，结果明确输出为 `EXCLUDED`，不再称为开放产品缺陷；Mode 不兼容项按 Contract 预检结果处理。具体数量、原因和逐项状态只在 Case 台账维护，运行时以本次生成的 `evaluation-run-contract.json` 为准。只对人工确认可信的候选代码使用低权限、可撤销、有限额的评测密钥。

两个完整入口都固定为每个可执行 Case 连续运行 5 个样本、零重试、单 worker。最终计入资格的五个有效样本必须各自产生 audit、timings 和 service log，且原始样本序号完整为 `0/1/2/3/4`；被外部条件作废的原样本则保留 failure diagnostics 和 service log，并由替补样本补齐资格证据。缺失、重复、越界、发生 Playwright 重试或跨样本拼接产物都会使验证失败。直接运行 `test:e2e` 仍默认每个 Case 1 个样本，便于开发排障；它不等同于正式准出。两项 Compaction 的专项六轮门槛另行保留，不因全集五轮自动降级。

`05b-retry-external.sh` 在同一冻结树上有界补足符合规则的有效样本，原始失败不删除；映射记录在 `artifacts/external-invalid.json`，替补写独立目录。出现非外部替补失败或预算耗尽时会停止其余补样并返回失败。哪些外因可以作废、如何证明直接因果，只在[归因指南第 5 节](../../docs/testing/failure-attribution.md#5-网络429长尾与补样)维护。

当前真实模型基线不仅固定模型名，还固定以下请求设置：

```text
LongCat-2.0
maxOutputTokens=4096
contextWindowTokens=1048576（默认）
temperature=0
thinking=true
thinkingBudget=1024
```

设置由评测代码写入隔离Web Host的临时配置，无需额外环境变量。Case可声明专属窗口和输出上限，实际值必须写入元数据和审计：当前自动压缩为32768/8192，手动为32768/16384；Host仍按现有合同封顶维护输出，不改日常设置。自动压力输入须跨过8000-token近期保留预算；手动源资料须超过其按有效窗口计算的保留预算，同时能以完整消息装入摘要请求。参数改变须新冻结，不能沿用旧61440/24000成绩。

评测通过给 Web 子进程设置临时 `HOME`、`USERPROFILE` 和 XDG 目录，并使用独立 `LONGCAT_STATE_DIR`，使日常用户设置、Skill 和权限规则不可见；不依赖产品级 CLI 开关。需要复用日常 `~/.longcat-harness/settings.yaml` 中已经配置的 Provider 时，只能由运行者把 `baseUrl` 和 `apiKey` 显式映射到上述 `LCH_EVAL_LIVE_BASE_URL`、`LCH_EVAL_LIVE_API_KEY`；模型名、revision、token、上下文窗口、temperature 和 thinking 参数仍以本节冻结的评测基线写入隔离设置，不能直接继承日常配置。

`live` 通路运行 profile 所选的全部真实模型 Case，并在打开浏览器前拒绝 ID/Mode 身份不一致或组件不兼容的 Contract。完整清单、每项设计与评判规则、最新成绩和失败归因统一见 [Case 台账](../../test/e2e/cases/README.md)，本手册不复制易变进展。完整入口不会只挑已稳定 Case；任何非外部失败都会让命令和准出结论返回失败，外部作废样本也必须在有界补样中补足。未来若再次出现暂退项，恢复前必须先迁移目标机制或 Mode 归属，不能直接用 `--grep` 绕过兼容预检。

单 Case 调试命令见第 9 节，完整接入与冻结取样见[新增 SOP](../../docs/testing/new-playwright-case-sop.md)。取得单项重复样本之后，还需固定候选文件树执行相应集合的联合验证，不能把调试命令当成完整准出。

已有集合的稳定性巩固可以用一个显式、逐项转义的 `--grep` 表达式选择 Case 台账声明的候选子集，并保持 `--repeat-each=5 --retries=0 --workers=1`。选择性运行不得修改注册表，也不得把未执行的Case写入本轮成绩；`evaluation-run-contract.json`仍描述所选profile全集，所以这种运行只形成阶段样本，不冒充正式七步准出。该规则同样适用于每批5项的确定性实验。阶段报告必须另按显式ID集合核对每项规定次数的原始结果和成功附件，所有失败原样保留。当前候选子集、旧资格变化及暂不运行项只在Case台账维护。

稳定性批次的选项、样本门槛及止损按[设计准则](../../docs/testing/case-design.md#5-什么叫稳定什么叫全量通过)执行；每场使用新产物目录，修订后另冻结，不在运行中改动源码、编译产物或实验脚本。

## 3. 执行结果

计划内故障保留在原始结果里，Case 失败不自动终止后续 Case；测试依然必须保留失败证据及清理状态。完整判定流程如下。

全部步骤成功时，命令输出最终结论、摘要文件路径和保留的临时评测目录。准备、构建或项目自动测试失败时脚本立即停止。第五步的 Playwright 非零结果会先保留并进入第六步；第六步只识别并补足符合规则的外部样本，不改写原始非外部失败。第七步统一核对原始结果和替补证据；任何非外部失败或补样不足都会让最终命令返回非零退出码。

无论成功或失败，临时评测目录都会保留，便于查看日志、Playwright trace、截图、JUnit 和审计产物。脚本不会修改当前工作树，也不会连接、停止、重启或读写 `127.0.0.1:8088`；系统存在 `lsof` 时还会比较运行前后的监听快照，缺少 `lsof` 时无法验证外部监听进程是否变化。

排查模型正文污染时，可按responseId比对代理`modelResponse.wireTextEvidence`与耐久响应的文本哈希；该字段只说明传输文本，不改原始PASS/FAIL或网络判定。HTTP429只有直接、未恢复地阻断任务且无独立业务失败时才按现有规则补样；HTTP200空正文、候选不合格仍不补样。周运行入口见下节；分析层不替换现有硬断言或正式校验器。

### 3.1 每周评测远端 master

```bash
node scripts/evaluation/run-weekly.mjs
```

这与 `evaluate:local` 的候选合并实验不同：先 fetch `origin/master`，冻结远端提交；把本地已提交的 `devops/luoshijie02` 中 `test/e2e/**`、`scripts/evaluation/**` 及 `test/e2e/suite-companions.json` 逐项登记的评测自检放到隔离树，绝不合入该分支的产品修复。自检直接依赖 E2E 或评测脚本，与它们一同冻结，避免新注册表搭配旧 known-gap/TODO 合同。清单只允许明确的 `test/unit/*.test.ts` 或 `test/integration/*.test.ts` 路径，不允许产品路径或目录通配；完整覆盖范围写入 plan。`src/**`、`config/**`、`spec/**`、依赖清单/锁文件以及清单外的 Core/Web UI 产品测试逐字保持 master。两路独立源码目录必须得到相同 evaluated tree，每步前后继续执行源码漂移检查。主工作区的未提交文件不参与实验。

测试基线可显式指定 `--suite-ref <commit-or-ref>`；默认每次冻结上述本地分支的提交头，而非默认当前 checkout，也不静默退回 master 的旧 Case 集合。报告分别记录 master SHA、测试 SHA 和实际 tree。新 master 与基线不兼容时保留准备/构建失败并报告阻断，不修改产品或 Case 来刷绿。Core/Web UI 产品测试用 master 自带的版本，评测自检与 E2E 用测试基线；master 新增而基线尚未包含的 E2E 不自动获得覆盖。

后台任务应先用 `git archive` 把该已提交基线的 `scripts/evaluation/` 导出到仓库外，再用 `--repository /absolute/project --suite-ref <冻结SHA>` 启动导出的入口。这使操作脚本也属于固定提交，不执行主工作区未提交的脚本，也无需切换用户分支。

默认完整执行 deterministic、live 两个已注册全集，每项五样本、单 worker、零 Playwright retry；另预先登记两项 Compaction 各第六个样本。外部补样复用当前白名单、因果规则及每项最多三轮限制，不把模型空响应、非法工具参数、摘要污染作废。Compaction 第六样本另外校验冻结 audit/timings、JUnit 附件及完整轨迹/清理状态；不是用第六次 PASS 抵消前五次失败。最终 PASS 要求两路正式摘要均 PASS 及两项第六样本证据通过。

默认输出 `~/Desktop/LCH-每周全量回归/<北京时间>-<pid>/`，运行开始即写 `plan.json`、`progress.json`、`report.json`、`report.html`，准备失败也保留报告。目录保留两份源码归档、冻结 runner、Git 对象引用、各步骤日志、原始及替补 JUnit、trace、截图和轨迹。密钥仅在进程内从日常 `~/.longcat-harness/settings.yaml` 的 `model.baseUrl/apiKey` 显式映射，模型及参数继续采用冻结基线；不复制整个日常配置，不把密钥写入计划或报告。无凭据时报告阻断，不降级为替身。

部署自检可用 `--prepare-only`（只验证远端冻结与测试覆盖边界）或 `--preflight-only`（再安装锁定环境、类型检查及 Core/Web UI 测试，不采样真实模型）。这些结果明确为 PREPARED_ONLY / PREFLIGHT_ONLY，不能称为全量通过。`--root` 仅接受仓库外空的绝对目录。运行锁 `~/.codex/lch-weekly-regression.lock/owner.json` 记录精确 PID 与产物路径；存在锁则拒绝重入，崩溃遗留锁须先核实旧进程已退出再人工清理。最多运行十小时；只中断自己持有的进程组，超时及清理不足留为未完成，不模糊杀进程。macOS 执行期间使用本任务自己的 `caffeinate`，不保证唤醒关机/睡眠的机器；不操作 8088。

调度由运行机器配置，例如 Asia/Shanghai 每周一 00:00；仓库代码不会创建或恢复定时任务。套件长期维护在 `devops/luoshijie02`，Case PR 合向该分支，产品修复另从 master 开分支，见[分支约定](../../docs/testing/harness-evaluation.md#4-分支与交付方式)。新机器先更新本地已提交 suite 基线；入口 fetch 的是 master，不会自动拉新远端 suite 覆盖本地分支。

周任务还需逐失败样本分析，不能只执行脚本后交一张成绩表。按[归因指南](../../docs/testing/failure-attribution.md)填写本次目录的 `analysis.json`，其中第 7～9 节集中定义代码/作者溯源、字段、报告重点和封存检查。用本次目录里冻结的报告器重新生成：

```bash
node /absolute/weekly-root/runner/weekly-report.mjs /absolute/weekly-root
```

HTML 概览数量和成绩，正文集中失败项；全部 Case 明细及样本映射在 JSON。归因不修改原判分，也不授权自动修代码、提交或推送。任务依赖运行机器、调度器、仓库网络/权限、评测凭据及裁判可用；准备检查和旧材料回放不算新的全量实验，不能保证关机后仍按时运行。

排查非法工具JSON或`PROVIDER_MISSING_FINISH`时，默认读取`wireDiagnostics`的参数哈希、JSON合法性和finish标记，与同一调用的耐久事件对照。需原文回放时，在该次隔离实验显式设置`LCH_EVAL_CAPTURE_MODEL_WIRE=1`；代理只记录最多1MiB的上游响应，并替换已知API密钥/临时令牌，不记录请求正文或请求头。诊断原文仍可能包含业务资料，仅保存在隔离产物，不提交仓库。只有未超限、UTF-8无损、未脱敏且归档正文重新计算的哈希等于`wireSha256`时，才能逐字回放；标志为true不代替归档校验。哈希不符时保留证据缺口，不能修补原文后声称完整。若另有代理在转发前计算的正文/推理哈希，可独立比较耐久文本，但不能替代完整传输复演。保留原样本，不因回放或诊断重跑通过而补记资格。响应头前错误看`causeCodes`，不能只凭本机代理生成502就判上游网关故障。

### 3.2 G2 消息结构与代码影响

周入口在 G1 全部采样结束后，复用本次轨迹运行冻结的 G2 自检、逐请求分析和 Codex 裁判，生成 `g2/report.html`、`g2/report.json` 和逐请求索引；主报告链接 G2 结果。G1 FAIL 仍分析，用户中断则不启动后处理。准备失败或缺失轨迹记为未执行/证据不足，不换用历史实验。Codex 需要新机器安装并登录；运行失败保留待审结果，不自动修复或重跑。

规则只维护 [g2/rules.md](g2/rules.md) 一份，静态定位与动态核对共用规则 ID。不要求每次实验覆盖全部规则，有源码依据但未触发的规则不产生待审项。HTML 聚焦违反规则、涉及 Case、具体偏离和代码溯源，逐请求计数及正常/未触发明细留在 JSON；已触发但证据不足单独说明。报告单独指出组装代码变化，即使本次未触发该路径；按冻结提交保留代码片段、完整 SHA、作者邮箱及时间。规则仍待人工确认，G2 结果不改 G1 原始判分。离线复核已有实验、PR 两提交比较、退出码和取证限制见 [G2 手册](g2/README.md)。

## 4. 七个步骤

`run-local.sh` 只负责串联流程，每一步可以独立排查：

| 顺序 | 脚本 | 工作 | 失败条件示例 |
|---:|---|---|---|
| 1 | `01-prepare-source.sh` | 获取目标基线并构造临时待测源码树 | fetch、合并或本地修改应用失败 |
| 2 | `02-prepare-toolchain.sh` | 安装并核对固定 Node、npm 和 Bun | 实际版本与预期不一致 |
| 3 | `03-install-dependencies.sh` | 执行 `npm ci` 并安装指定浏览器 | lockfile 变化或浏览器缺失 |
| 4 | `04-typecheck.sh` | 执行主包和 Web UI 类型检查 | 任一类型检查失败 |
| 5 | `05-run-regression.sh` | 以 5 样本、零重试、单 worker 运行所选 Playwright 通路和项目自动测试，并保留原始结果 | Case 或项目测试失败；Case 失败会先进入第六步归因，其他失败直接阻断 |
| 6 | `05b-retry-external.sh` | 只对最后一个未恢复模型请求有明确网络/网关失败、且最新 Turn 或失败信息直接关联该请求的样本作废，并在同一冻结树有界补样 | 替补出现非外部失败、补样预算耗尽、替补运行或映射不完整；原始非外部失败保留给第七步统一拒绝 |
| 7 | `06-verify-results.sh` | 联合核对原始与替补样本、逐 Case 产物和测试汇总 | 有效样本不足/重复/越界、发生 retry、产物身份不一致、存在非外部失败或跳过 |

步骤间通过 `$LCH_EVAL_ROOT/metadata/*.passed` 确认前置步骤已经成功。第七步只核对运行产物、外部作废与替补映射、有效样本和自动测试结论，不使用另一套离线语义规则重新解释真实模型答案；每个 Case 的业务真值和机制证据由其 Playwright Driver 负责。原始 JUnit 可以保留已作废的外部失败，但不能因此省掉替补，也不能掩盖非外部失败。若审计包含 `policyDiagnostics`，后置校验要求合法诊断来源、同 Session/Turn 的绑定身份、原始服务交换与响应，并原样转存到 `evaluation-summary.json`；最终 PASS 行另显示诊断数量，不代表参与副模型全部健康。

## 5. 源码固定方式

`evaluate:local` 不会在当前工作树执行 `git pull`。第一步在仓库外创建临时源码树：

```text
git fetch 指定 remote
  -> 解析目标基线，默认 origin/master
  -> 解析候选提交，默认当前 HEAD
  -> 在临时 clone 中合并两者
  -> 叠加当前 tracked 和 untracked 修改
  -> 记录最终 evaluated tree SHA
```

若目标基线无法获取、分支无法合并、本地补丁无法应用或必要评测文件缺失，流程立即失败，不会退回旧源码继续执行。

运行报告记录目标基线、候选提交、最终 tree SHA、工具链和依赖。本地摘要中的 `checkoutSha` 是调用评测时原工作树的 `HEAD`，用于解释候选来源；最终 `evaluatedTreeSha` 才是本次真正被测试的文件树身份。

## 6. 固定工具链

当前脚本在 `scripts/evaluation/_common.sh` 集中声明版本：

```text
Node       24.12.0
npm        11.6.2
Bun        1.4.2
Playwright package-lock.json 中的精确版本
Browser    由 Playwright 版本绑定的 revision
项目依赖   package-lock.json + npm ci
```

修改任一工具链版本时，要同步更新脚本、`package.json` 和 lockfile，并重新执行完整确定性评测。选择 Firefox 或 WebKit 时，先安装相应浏览器；完整本地入口会按 `LCH_E2E_BROWSER` 自动准备。正式评测拒绝 `LCH_E2E_BROWSER_CHANNEL`，避免系统浏览器绕过 Playwright 锁定的 revision；该变量只用于直接开发调试。

`scheduler-lifecycle.test.ts` 已兼容 Node 24 MockTimers 缺少 `Timeout.close()` 的差异：仅在缺少时转交当前模拟时钟的 `clearTimeout`，结束后恢复。无需为此改用 Node 26、跳过调度断言或修改生产计时器。`web-native-picker.test.ts` 仅在 macOS 且显式设置 `LONGCAT_TEST_NATIVE_PICKER=1` 时运行，会打开真实系统窗口；未开启时必须报告 SKIP，不能称为该交互已验证。

## 7. 单独执行步骤

正常验收优先使用总入口。排障时可以指定仓库外的空目录，并按顺序执行：

```bash
export LCH_EVAL_ROOT=/tmp/lch-local-eval.manual

./scripts/evaluation/01-prepare-source.sh "$LCH_EVAL_ROOT" "$PWD"
./scripts/evaluation/02-prepare-toolchain.sh "$LCH_EVAL_ROOT"
./scripts/evaluation/03-install-dependencies.sh "$LCH_EVAL_ROOT"
./scripts/evaluation/04-typecheck.sh "$LCH_EVAL_ROOT"
./scripts/evaluation/05-run-regression.sh "$LCH_EVAL_ROOT"
./scripts/evaluation/05b-retry-external.sh "$LCH_EVAL_ROOT"
./scripts/evaluation/06-verify-results.sh "$LCH_EVAL_ROOT"
```

`LCH_EVAL_ROOT` 必须是仓库外的绝对路径，第一次执行时必须为空；脚本会解析符号链接和 `..` 后再次核对物理路径。

## 8. 主要变量

### 8.1 运行选择

| 变量 | `evaluate:local` 默认值 | `evaluate:ci` 默认值 | 作用 |
|---|---|---|---|
| `LCH_EVAL_PROFILE` | `deterministic` | `deterministic` | 只接受 `deterministic` 或 `live`；CI 拒绝 `live` |
| `LCH_E2E_BROWSER` | `chromium` | `chromium` | 可选 `chromium`、`firefox` 或 `webkit` |
| `LCH_EVAL_REPEAT_EACH` | 完整入口固定为 `5` | 完整入口固定为 `5` | 直接运行 `test:e2e` 时默认 `1`，可设为正整数做阶段采样；正式入口、补样和第七步从 `sample-requirements.mjs` 读取五个有效样本要求 |
| `LCH_EVAL_ROOT` | 自动创建 | 自动创建 | 指定保留源码、工具链、日志和产物的空目录 |
| `LCH_EVAL_ARTIFACT_DIR` | `$LCH_EVAL_ROOT/artifacts` | `$LCH_EVAL_ROOT/artifacts` | Playwright 产物根；完整七步评测由脚本固定，不应单独覆盖。仅直接运行 `test:e2e` 调试时可显式指定已有或待创建目录，以集中保存 JUnit、trace、截图和 Case 附件；它不包含固定源码、工具链、步骤日志或完整评测元数据，不能替代 `LCH_EVAL_ROOT` |
| `LCH_EVAL_TARGET_REF` | `origin/master` | `unreported` | 本地运行中是 fetch 后的目标基线；CI 中须与 `LCH_EVAL_TARGET_SHA` 成对提供 |
| `LCH_EVAL_TARGET_SHA` | 由目标引用解析 | `unreported` | CI 声明的目标提交；必须是当前对象库中可验证的完整提交标识 |
| `LCH_EVAL_SOURCE_REF` | `HEAD` | `unreported` | 本地运行中是要合入目标基线的候选提交；CI 中须与 `LCH_EVAL_SOURCE_SHA` 成对提供 |
| `LCH_EVAL_SOURCE_SHA` | 由候选引用解析 | `unreported` | CI 声明的候选提交；必须是当前对象库中可验证的完整提交标识 |
| `LCH_EVAL_REMOTE_NAME` | `origin` | `origin`，不存在时记为 `unreported` | 本地运行会 fetch；CI 只记录 remote 名称，不依赖 remote 执行测试 |

### 8.2 真实模型

| 变量 | 作用 |
|---|---|
| `LCH_EVAL_ALLOW_LIVE=1` | 显式允许产生真实模型调用 |
| `LCH_EVAL_LIVE_MODEL` | 评测模型名称；当前基线为 `LongCat-2.0` |
| `LCH_EVAL_LIVE_BASE_URL` | OpenAI Chat Completions 兼容 Provider 根地址 |
| `LCH_EVAL_LIVE_API_KEY` | 只交给父进程和本机凭据代理的评测密钥 |
| `LCH_EVAL_LIVE_MODEL_REVISION` | Provider 部署或模型快照标识；未知时明确写 `provider-unreported` |

非本机 Provider 必须使用 HTTPS。地址不能包含用户名、密码、查询参数或片段，也不能指向日常 Web UI 的 `8088` 端口。缺少必要变量时，`live` 通路应在启动浏览器和发送请求之前失败。

## 9. 开发和排障命令

| 命令 | 用途 |
|---|---|
| `npm run test:e2e` | 构建后运行 `LCH_EVAL_PROFILE` 选择的 Playwright 通路；默认是确定性基础自检且每个 Case 只跑 1 个开发样本 |
| `npm run test:e2e:live` | 设置 `live` 通路并运行 `live` profile 当前选中的真实模型 Case；仍需提供真实模型变量 |
| `npm run test:regression` | 先运行当前 Playwright 通路，再运行主包和 Web UI 自动测试 |
| `npm run evaluate:local` | 在临时源码树中完成七步本地评测 |
| `npm run evaluate:ci` | 对流水线已检出的干净代码执行确定性评测；不下载工具链、依赖或浏览器，但会核对实际版本和可执行文件 |

单 Case 的准备、`--list`、单跑一次、一次跑五个样本及冻结命令，集中见[新增 SOP 第 5～6 节](../../docs/testing/new-playwright-case-sop.md#5-单项验证直接用这些命令)。不用手工启动网页服务；不要用 `test:e2e:live -- --grep` 转发筛选参数，使用 `test:e2e -- --grep`。

直接 `test:e2e` 会构建并执行所选 Case，保存附件和清理；不会固定源码/工具链，也不会自动补样或执行正式最终校验。每次资格实验使用新 `LCH_EVAL_ARTIFACT_DIR`，不能覆盖 JUnit 和旧附件。完整冻结及校验入口是 `evaluate:local` / `evaluate:ci`；周实验使用第 3.1 节的独立入口。

## 10. 产物位置与读取

单路完整评测目录：

```text
$LCH_EVAL_ROOT/
  source/                 实际待测源码和构建结果
  toolchain/              固定工具链
  metadata/               Git 身份、物理目录、工具版本、8088 快照和步骤标记
  logs/                   各步骤日志
  artifacts/
    evaluation-summary.json
    external-invalid.json 原因及原样本/替补映射（发生作废时）
    external-retries/     独立替补产物（发生补样时）
    junit/playwright.xml
    test-results/         audit、timings、日志、截图、trace、失败诊断与轨迹
```

周目录的 `plan.json` / `progress.json` 指明两路节点位置，另有冻结 `runner/`、源码归档、`analysis.json`、`report.html/json` 及 G2 产物。不要把单路目录当作整个周实验，也不要把进度报告当最终结果。

| 要找的东西 | 在哪里看 |
|---|---|
| 哪一步退出、哪些 Case 没跑 | progress、步骤日志、JUnit；准备失败可能尚无 Case 附件 |
| 单个 Case 的真实断言错误 | JUnit、`error-context.md`、截图、trace |
| 清理前发生什么 | `failure-diagnostics.json`：Turn/事件、Policy 状态、代理阶段、清理结果；仅环境已启动时能取得 |
| 成功判定与预算 | 该 Case 的 `sqlite-audit`、`timings` 和 `isolated-service.log`；文件名由 Contract 决定 |
| 服务交换及业务文件 | Driver 在 `attachArtifactsBeforeCleanup` 挂出的专属附件，参照相应 Contract/Driver |
| 完整持久轨迹 | `trajectory.jsonl.gz`，manifest → event/turn/message → complete；不是原始 HTTP |
| 外部补样 | 原始 JUnit、`external-invalid.json`、`external-retries/`，共同核对映射，不能只读替补绿项 |
| 本次归因与代码责任线索 | `analysis.json`，及报告引用的冻结源码/Git 历史 |

`attachArtifactsBeforeCleanup` 在清理前保存外部服务和进程证据；附件失败会记录并阻断准出，但仍继续清理。最终轨迹在停止测试进程后从原 SQLite 只读导出，包含清理事件；取证失败保留原目录。完整协议见[技术方案](../../docs/testing/web-regression.md)，归因和逐附件验收见[归因指南](../../docs/testing/failure-attribution.md)。

临时服务目录使用系统临时目录下的随机 `lch-e2e-*` 短路径，macOS 取证时按 realpath 核对 `/tmp` 与 `/private/tmp`。外部取证器只匹配本任务的精确目录/进程，不能使用历史前缀或模糊杀进程。产物只能在完整性确认后清理；不删除旧实验或日常状态库。

读取传输原文的方法与限制见第 3.1 节 `LCH_EVAL_CAPTURE_MODEL_WIRE`。已知密钥脱敏不等于没有业务资料，临时证据不提交仓库；归因、报告和封存步骤统一见[归因指南第 7～9 节](../../docs/testing/failure-attribution.md#7-追溯代码和建议跟进人)。

## 11. CI 边界

`evaluate:ci` 假设流水线已经检出唯一待测提交，要求工作树干净，并只允许 `LCH_EVAL_PROFILE=deterministic`。流水线运行器要预先提供固定 Node、npm、Bun、通过 `npm ci` 安装的项目依赖和 Playwright 浏览器；脚本会核对项目 Bun、实际 Playwright 版本和所选浏览器可执行文件，不会用 lockfile 中的声明值冒充实际环境。

CI 摘要把三类 Git 身份分开记录：`checkoutSha` 是流水线实际检出的提交，`source/target` 是流水线显式声明的变更来源，`evaluatedTreeSha` 是真正接受测试的文件树。CI 只有在 `LCH_EVAL_SOURCE_REF` 与 `LCH_EVAL_SOURCE_SHA`（或 target 对应变量）成对提供且 SHA 能由当前 Git 对象库验证时才记录来源；缺失时两项均写为 `unreported`，不会拿检出提交冒充分支来源。`ref` 是流水线提供的名称；当前 clone 能解析它时脚本会进一步核对它是否指向声明的 SHA，浅 clone 中无法解析时只能证明 SHA 对象存在，不能独立证明该名称与 SHA 的远端关系。

仓库当前只提供可被流水线调用的脚本，不在本文宣称已经接入具体平台。真实模型的手动或定时运行使用受信任机器，仍需凭据隔离、模型版本、成本与重复采样管理；不能把当前隔离目录当作不可信代码沙箱。

## 12. 新增 Case

按[新增 Playwright Case SOP](../../docs/testing/new-playwright-case-sop.md)执行：分支选择、设计单、live/deterministic 文件顺序、单项命令、冻结取样及台账均在那里维护。本手册不再复制第二版步骤。

## 13. 冻结与取样要求

取样门槛统一见[设计准则](../../docs/testing/case-design.md#5-什么叫稳定什么叫全量通过)。全量计数由 `sample-requirements.mjs` 供入口、补样与最终校验共用，两项 Compaction 第六样本由周入口预登记。临时定向 Playwright 不生成正式 CI/七步通过标记。

Core 失败导致正式步骤无法启动时，可以保留经授权的独立定向观察，但不能补造步骤成功标记、替换退出码或混成整体通过。源码、编译产物、模型配置及断言都要冻结，原失败和补样映射全部保留；代码树或条件变化就新开实验。不得操作 8088。
