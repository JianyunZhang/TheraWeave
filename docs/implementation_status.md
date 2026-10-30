# TheraWeave 实施记录与验收边界

> 日期：2026-10-30；软件版本：`0.1.0.dev0`；阶段：**T1a/T1b/T1c 本地研究闭环预览**。\
> 路线图见[总纲](omicsweave_theraweave_development_plan.md)，科学语义与后续要求见[设计评审](theraweave_design_review.md)。

## 1. 上游核对结果

完成评审后，按项目负责人“继续完成未完成事项”的要求，检查了本机同级 `OmicsWeave` 仓库的实际实现及 `docs/omicsweave_arch_design_v2.md`。该配套文档可在上游本地仓库找到，但未复制进 TheraWeave，避免维护两个副本。

实查结果：`RunManifest` 中 `BUNDLE_SCHEMA_VERSION = "0.1"`；存在 `DatasetMeta`、`DIFFERENTIAL_COLUMNS`、读写函数和 Schema 导出函数。上游尚无 `schemas/evidence-exchange/v1/` 发布目录，也没有本次新设计的完整 Evidence/Context/Dependency 契约。物种、完整比较设计、样本依赖和运行完成状态没有全部编码到现有 manifest。

因此先建立**显式启用的草案兼容适配器**，而不是宣布 v1 冻结。上游源文件未被修改；本地捕获的只读 Schema/列定义位于 `src/theraweave/schemas/omicsweave_0_1/`，`snapshot.json` 记录每个来源文件和捕获产物的 SHA-256，并保留原许可。软件运行时不导入 OmicsWeave；维护者重新捕获时才运行上游代码。固定源文件摘要而非推测 Git SHA，避免把当前检出的文件误认为已发布契约。

## 2. 已实现

- 独立 Python 包、CLI、BSD-3-Clause 许可、引用文件与第三方说明；核心依赖为 PyArrow 和 JSON Schema。
- `contract-info`：查询固定的草案版本、来源摘要和状态。
- `demo`：生成小型合成结果包及用户上下文，包含反向变化和缺失统计量示例。
- `validate`：JSON Schema、显式版本门控、输出路径/大小/SHA-256、Parquet 列类型、概率范围、样本数、比较角色、组学声明、重复记录与冲突校验。
- `import` / `DiscoveryProject.from_bundle`：使用显式上下文导入，保留原表、原始行值/行号和完整来源引用，生成实体与证据档案。
- 同一实验的观察共用保守依赖组；跨文件同一键同一记录只计一次，不同值报错。独立复现数保持未知，不把多组学数当作独立重复数。
- 保留未解析实体类别及缺失统计量；不根据 p 值或反向变化生成治疗方向、因果或阴性结论。
- 本地 HTML 与正式 Parquet 同源，文本转义、无外部资源；输出在完整写出后发布，拒绝已有目标目录，校验后输入被修改时中止。
- 开发者工具：文档检查、上游真实写出函数往返检查、wheel 安装检查；CI 配置覆盖 Windows/Linux 与 Python 3.10/3.12，远端结果尚未取得。
- 三个知识来源的本地子集转换、统一快照校验、未审查状态、引用和来源去重；支持 Open Targets evidence、UniProt entry/search JSON、ChEMBL mechanism + 单蛋白 target map 的受限格式。
- 候选八维证据画像、四种规则桶、风险/方向门槛、来源和研究移除敏感性、描述性基线；规则未在真实研究上校准。
- 验证计划草稿、显式设计审查、预定终点规则、精确版本反馈和 OmicsWeave 空样本草稿模板；支持/不支持/不确定结果限定于计划上下文。
- 全流程合成演示，以及保护真实输入不被合成知识支持的门控。详细格式和命令见[本地闭环说明](local_discovery_workflow.md)。

### 当前支持与限制

| 内容 | 状态 |
|---|---|
| OmicsWeave `0.1` manifest 与 differential 表 | 显式 `--allow-draft` 支持；未来版本拒绝，不猜测兼容 |
| `dataset.json` | 校验结构及 counts/units 条件；不声称已验证完整矩阵/样本关系 |
| 文件选择 | 只读取 manifest 中列出的 output；input 路径作为来源信息保存，不读取外部原始数据 |
| 差异表识别 | basename 为 `differential.parquet`，或记录 `kind=differential` |
| 范围与资源 | 每表最多 1,000,000 行；这是当前预览的内存边界，不是性能保证 |
| 数值严格性 | 生物学重复数要求整数列，不接受小数或负数；缺失 p 值/效应保留未知并告警 |
| MFA | 同步最新 0.1 草案的均值、单位、推断单位、统计证据等级与 bool 列；允许带明确不足/未定义标记的空效应；不读取原始 flux/MID/拟合模型，不据此进行 GPR 或控制推断 |
| 富集结果 | 新上游已增加富集写出；当前下游对其校验文件完整性并归档，尚不解释为独立靶点证据 |
| 上下文 | 物种、标识命名空间、疾病和终点由使用者提供；尚无外部身份解析 |
| 缺失与结论 | 输出为观察清单，`result_interpretation=not_assessed`、方向 unknown；这属于本软件预览产物，不冒充正式 v1 枚举 |
| 知识接入 | 本地受限格式转换和归一化快照已实现；真实 release 的许可、全量字段与覆盖验收尚未完成 |
| 靶点分桶 | 规则引擎、证据画像、来源敏感性已实现；没有独立研究性能结论或成功概率 |
| 验证计划/反馈 | 草稿、显式审查、规则反馈和历史版本已实现；实际实验设计与结果需使用者提供 |
| 正式 v1 与真实课题 | 待上游发布和真实结果包科学审查；当前预览不替代这些验收 |

## 3. 使用方法

要求 Python ≥3.10。当前工作区已创建 `.venv` 并安装开发版，可在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe -m theraweave demo local/my-demo
.\.venv\Scripts\python.exe -m theraweave validate local/my-demo/bundle --context local/my-demo/context.json --allow-draft
.\.venv\Scripts\python.exe -m theraweave import local/my-demo/bundle --context local/my-demo/context.json --output local/my-report --allow-draft
```

然后打开 `local/my-report/import_report.html`。这两个目标目录必须尚不存在；重跑时使用新的目录名，以免覆盖既有证据记录。

新环境可先使用 Python ≥3.10 创建虚拟环境，再执行 `python -m pip install -e ".[dev]"`。本机系统默认 `python` 是旧环境，建议使用上面的明确路径。

导入真实数据前，必须按实际物种、feature ID 类型、疾病/表型和主要终点填写上下文；不要复用合成上下文的生物学含义。当前源文件是否完整并不等于统计设计或实体注释已经正确。

```python
from theraweave import DiscoveryProject

project = DiscoveryProject.from_bundle(
    "local/my-demo/bundle",
    context="local/my-demo/context.json",
    allow_draft=True,
)
project.write_evidence_report("local/my-python-report")
```

CLI 返回码：成功为 0，文件/运行错误为 1，输入校验失败为 2；校验错误包含规则 ID、文件、字段/行号和建议动作。

## 4. 可复现检查命令

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tools/check_docs.py
.\.venv\Scripts\python.exe -m build --no-isolation
.\.venv\Scripts\python.exe tools/check_upstream_compatibility.py --upstream ../OmicsWeave --output local/validation/new-roundtrip
```

最后一项使用实际上游 `write_differential`、`RunManifest`、`file_record`、`write_manifest` 写出合成数据，然后由独立 TheraWeave 读取。执行前会比较上游源文件摘要；若源文件已变，要求重新评审，不静默沿用旧兼容结论。

实际验证结果、环境和产物记录在本次本地验收文件中；结果对应本次运行，不是远端 CI 或真实生物学验证。测试与构建通过不意味着研究排序有效。

截至本次实现，自动测试为 **59 项通过**，包含导入、三个本地转换器、去重、上下文/方向/风险、来源敏感性、精确计划版本、反馈规则、最新 MFA 草案语义和 Windows 发布冲突的有上限重试。曾有一次最终复测在目录改名时收到 WinError 5；修复后完整测试通过，持续性错误仍会抛出。合成数据完整流程已实际执行，产物在 `local/validation/full-preview/`。最新上游真实写出函数检查得到 2 个实体、2 条证据；用的仍是合成数据。最新 wheel 的构建与独立安装检查另记录在 `local/validation/`。

运行清单记录实际包内源码/Schema 的内容指纹，开发版即使版本号相同，代码变化也会改变运行身份，避免只凭 `dev0` 或未提交的 Git HEAD 判断来源。

最终核对曾检测到上游在本次工作期间新增富集和 MFA 差异字段，版本号仍为 0.1。已人工核对后重新捕获固定快照、增加条件必填/统计等级规则并重跑往返检查。上游差异表的 `evidence_level` 是 statistical_test/effect_size_only/insufficient，和未来证据图的层级语义不同；下游存为 `source_statistical_level`，不会直接覆盖证据图分层。该命名冲突应在正式契约冻结时解决。

## 5. 仍未完成的阶段验收

- **T0 / 正式契约**：将新增字段和规则落实到上游权威契约，并发布 profile 与正反例。本次只完成读取核对与差距记录。
- **T1a 完整验收**：正式 profile、完整证据引用/样本关系及一个真实课题结果包的科学审查；目前只有草案接口的合成往返证据。
- **T1b 正式验收**：本地转换、快照、画像、分桶、敏感性和基线代码已就绪；仍需真实数据库版本/许可与字段覆盖核验、跨物种/跨 ID 证据映射、真实课题和独立性能评估。
- **T1c 科学验收**：计划/审查/反馈代码与草稿模板已就绪；仍需具体终点、效应/方差、实验能力及实际结果，不能从模板反推实验已执行。
- **远端与发布**：尚未 push、运行 GitHub Actions 或发布到 PyPI；Linux/Python 3.10 尚未本地运行验证。

首个真实课题已由项目负责人指定，疾病为肥胖症，关注中心性肥胖与脂肪肝；课题标识、已确认的干预方案及 6 类比较目标保存在被 Git 忽略的本地工作区。当前尚无结果包，部分给药记录、具体主要读数和时间匹配对照仍待确认。上述科学验收保持未完成，不因演示、规则代码或 CI 文件存在而勾选。

## 6. 生态比较后的规划修订

2026-10-30 新增[与 Schrödinger 的生态比较](schrodinger_ecosystem_comparison.md)，总纲更新为 v1.3，设计评审更新为 v0.2：承认靶点评估、数据整合、模态、闭环与 AI 的实际重叠，聚焦本研究上下文中的证据与验证效用；T2 规划可选专业后端的文件交接和预测回流，并加入更接近的组学解释/靶点工具对照。

本轮仅修改文档与导航，没有新增 Schrödinger 适配器、执行商业计算、重跑科学基准或重建安装包。上文 59 项测试及既有 wheel 对应此前的代码验收；软件版本和运行行为保持不变，新增接口要求仍待实施。
