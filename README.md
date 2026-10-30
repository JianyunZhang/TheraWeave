# TheraWeave
Discovery of Therapeutic Strategies

TheraWeave 旨在将多组学分析结果与外部生物医学证据结合，形成可追溯的候选治疗靶点、干预方向假设和后续验证实验计划。首版聚焦代谢性疾病、小鼠与人数据及代谢酶/转运体相关机制，同时保留通用扩展接口。

生态定位：OmicsWeave 负责定量与模型质量，TheraWeave 聚焦疾病/实验上下文中的靶点证据和验证决定；结构、结合与分子性质问题可在后续按需要衔接 Schrödinger 等专业平台。双方在靶点评估、数据整合和实验反馈上有重叠，差异化需通过具体研究效用验证。

当前版本为 **`0.1.0.dev0`，本地研究闭环预览**（2026-10-30）：已实现 OmicsWeave `0.1` 草案导入与校验、证据去重归档、三个知识来源的本地子集转换、按规则的候选证据画像、敏感性分析、验证计划、显式审查与结果回流。正式 v1、真实数据库快照及真实课题上的科学验收尚待完成；当前规则未校准为预测模型。

当前工作区的最短体验路径（在仓库根目录，使用已安装的隔离环境；目标目录需不存在）：

```powershell
.\.venv\Scripts\python.exe -m theraweave demo local/my-demo
.\.venv\Scripts\python.exe -m theraweave import local/my-demo/bundle --context local/my-demo/context.json --output local/my-report --allow-draft
```

打开 `local/my-report/import_report.html` 查看证据档案。示例全部为合成数据，不代表实际治疗靶点。新环境要求 Python ≥3.10，安装命令为 `python -m pip install -e ".[dev]"`。

继续运行候选评估和计划草稿：

```powershell
.\.venv\Scripts\python.exe -m theraweave assess local/my-report --snapshot local/my-demo/knowledge/OpenTargets.synthetic.json --snapshot local/my-demo/knowledge/UniProt.synthetic.json --snapshot local/my-demo/knowledge/ChEMBL.synthetic.json --output local/my-assessment
.\.venv\Scripts\python.exe -m theraweave plan local/my-assessment --output local/my-plans
```

完整合成演示（包含模拟审查和模拟结果）可运行 `python tools/run_preview_demo.py local/my-full-demo`。真实研究的审查和结果必须由实际资料填写，不能套用演示内容。

- [OmicsWeave × TheraWeave 总体规划 v1.3](docs/omicsweave_theraweave_development_plan.md)：双仓库职责、结果契约、模块与路线图。
- [TheraWeave 设计评审与首版实施规格](docs/theraweave_design_review.md)：问题优先级、证据去重、因果与方向边界、最小输入契约、候选评估、实验闭环及验收标准。
- [实施记录与验收边界](docs/implementation_status.md)：实际支持的输入、使用方法、上游核对结果、检查命令和未完成事项。
- [本地知识与实验闭环操作说明](docs/local_discovery_workflow.md)：知识转换、规则评估、计划审查和结果回流的数据要求。
- [与 Schrödinger 的生态比较和对接规划](docs/schrodinger_ecosystem_comparison.md)：共同能力、主要差异、直接重叠工具、外部计算接口与质量评价。

核心输出围绕“为什么验证该靶点、证据有何限制、下一项实验如何支持或否证假设”。计算结果用于研究假设与实验决策，需在具体模型和条件下验证。
