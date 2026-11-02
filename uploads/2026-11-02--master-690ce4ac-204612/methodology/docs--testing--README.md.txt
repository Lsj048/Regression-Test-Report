# 回归测试文档入口

第一次接手从这里开始。仓库行为以 [spec/README.md](../../spec/README.md) 为准；本目录解释怎么设计、运行和分析测试，不另立产品规范。

## 我要做什么，先读哪份

| 事情 | 主文档 | 这份文档负责什么 |
|---|---|---|
| 了解 G1/G2/G3 规划和当前建设状态 | [总体方案](harness-evaluation.md) | 阶段目标、已实现能力、尚未完成的工作和覆盖边界 |
| 查某个 Case 测什么、是否稳定 | [Case 台账](../../test/e2e/cases/README.md) | 逐 Case 设计入口、冻结版本、样本成绩、失败处理及证据位置 |
| 决定该写单元、集成还是网页测试 | [测试分层选择](test-selection.md) | 按风险选测试层，判断 live/deterministic 是否合适 |
| 设计题面、夹具、断言和稳定性标准 | [Case 设计准则](case-design.md) | 用户合同、必经机制、允许变化、正反控制、取样门槛 |
| 从零增加一个 Playwright Case | [新增 Case SOP](new-playwright-case-sop.md) | 按文件顺序接入 live / deterministic、单项验证、冻结取样、登记与交付 |
| 判断为什么失败、找谁跟进 | [失败归因指南](failure-attribution.md) | 逐样本第一处分歧、分类、常见误判、Git 溯源、报告及封存 |
| 看测试代码如何工作 | [Web 回归技术方案](web-regression.md) | Contract/Driver/audit、隔离环境、证据协议及领域审计边界 |
| 执行实验、配置模型、查看产物 | [流水线运行手册](../../scripts/evaluation/README.md) | 工具链、命令、冻结、全量入口、补样和报告生成 |
| 分析模型请求的消息结构 | [G2 手册](../../scripts/evaluation/g2/README.md) | G2 运行、源码映射和裁判；规则正文只在 [rules.md](../../scripts/evaluation/g2/rules.md) |
| 查已发现的产品缺陷 | [缺陷说明目录](../bugfix/) | 每个问题的用户影响、原因、修复行为、证据边界；待确认项见 [开放风险](../bugfix/open-evaluation-findings.md) |

## 分支先选对

回归套件在 `devops/luoshijie02` 维护。维护者从该分支切工作分支，Case PR 合回该分支；LCH 产品缺陷从最新 master 单独修复并向 master 提交 PR，带必要产品测试，不带整套 Case。详细约定及兼容边界见[总体方案](harness-evaluation.md#4-分支与交付方式)。

## 一条信息只维护一个正文

- **通用方法**写在设计或归因指南；其他文档给链接，不再复制另一版规则。
- **具体 Case 的成绩和处理状态**写台账。源码里的 Contract、Driver、audit 是可执行定义；台账链接这些定义，不复制完整实现。
- **产品 Bug**独立写 `docs/bugfix/`，台账只关联问题。Case 改错、模型质量问题不计为产品修复。
- **一次实验的全部细节**留在仓库外的实验目录：计划、日志、JSON/HTML、trace、SQLite 派生轨迹、源码与哈希。仓库文档只保留结论和必要定位。
- **桌面报告和旧指南包**是对应时间的快照，不是另一份最新规范；迁移方法优先带走当前仓库文档。运行不依赖本机桌面路径。
- **`lch-web-regression` skill**是执行入口和提醒。已安装时一并阅读；在另一台机器没有安装时，本目录仍应足够完成工作。与仓库最新指令不一致时，以用户要求及仓库规范为准。

更新时只改受影响的职责。例如新增 Case 通常改 Case 源码、测试和台账；没有改变架构或命令，就不需要给总体方案和运行手册各追加一份总结。文档整理集中为一个提交，不追加复审流水账。
