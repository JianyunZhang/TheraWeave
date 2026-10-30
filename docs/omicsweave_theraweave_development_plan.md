# OmicsWeave × TheraWeave：多组学分析与治疗发现系统架构规划

> **文档类型**：软件系统架构与研究开发规划（两个系统的总纲）\
> **版本**：v1.3（生态定位修订稿，2026-10-30；修订自 v1.2，修订内容见第 0 节；不代表功能或契约已发布）\
> **适用范围**：Python 多组学分析、代谢流分析、证据整合、候选靶点发现与下游治疗策略研究\
> **项目名称**：`OmicsWeave`（上游） / `TheraWeave`（下游，暂定；初步检索未发现重名，正式采用前需完成商标核查，见第 10 节）\
> **配套文档**：详细评审见 [theraweave_design_review.md](theraweave_design_review.md)，最新实现状态见 [implementation_status.md](implementation_status.md)。上游 `omicsweave_arch_design_v2.md` 未复制到本仓库；后续实施已在本机 OmicsWeave 仓库核对到 v2.1 及草案 0.1 源码。本文规定双仓库边界和契约设计要求，发布格式以 OmicsWeave 权威契约为准；本次新增字段尚未在上游发布。

## 0. 修订说明

### v1.2 → v1.3（2026-10-30）

| 修订内容 | 位置 |
|---|---|
| 纳入 Schrödinger 生命科学生态比较：承认靶点评估、数据整合、生物药、闭环与 AI 编排的重叠，收紧差异化主张 | 6.1、6.7、配套生态比较文档 |
| 明确本项目的重点为上下文限定的组学/MFA 证据与验证决定；专业分子计算采用可选后端并保留预测语义 | 6.5、6.7、T2 |
| 增加更接近的组学解释/靶点工具对照、真实研究效用与成本指标、外部计算交接和回流要求 | 7.4、T3、9、11 |

完整依据和现状/规划边界见 [生态比较文档](schrodinger_ecosystem_comparison.md)。本轮仅修改文档，不新增商业软件适配器或性能验证。

### v1.1 → v1.2（2026-10-30）

| 修订内容 | 位置 |
|---|---|
| 确认代谢性疾病优先、保留通用扩展接口；补充 TheraWeave 仓库的实查状态，并区分上游历史记录 | 1.2、6.1、11 |
| 修正小样本检验条件；将治疗逆转分为反向响应、趋近参照及因果判断 | 2.2、2.3 |
| 补充上下文限定的假设、证据来源依赖、缺失与阴性语义；拆分干预方向与策略 | 3.3–3.5、6.4 |
| 补充 MFA 的 GPR、区室及通量与控制关系的边界；保留多对多同源映射 | 3.1、3.6 |
| 将完整校验细化为封装、JSON/Parquet 结构、跨文件语义和用途校验；增加最小输入 profile | 5.1 |
| 补齐抗体、基因补充、RNA 等模态范围，区分实验工具与药物再利用；修正 CLI 运行时描述 | 5.2、6.3、6.6 |
| 将最小实验反馈、基准与防泄漏前移至 T1；分解 MVP，发表不再以完成模态扩展为前提 | 7.4、8 |
| 增加详细科学规则、评估标准、验收反例与原始研究/官方依据 | 配套评审文档 |

设计评审后，按项目负责人继续实施的要求，已核对上游草案源码，并实现 T1a 草案兼容预览。它必须显式启用 `--allow-draft`，不代表正式 v1 已冻结或完整 T1a 验收完成；具体范围见实施记录。

### v1.0 → v1.1（2026-10-29，历史记录）

| 修订内容 | 位置 |
|---|---|
| 新增当前进度：OmicsWeave 阶段 0 已完成；TheraWeave 名称的初步检索结果 | 1.2、10 |
| 新增“实验设计语义”：比较的角色（疾病效应 / 治疗效应）与“治疗逆转”标记，这是产生治疗假设的关键信息 | 2.3 |
| 实体模型补充“反应（Reaction）”类型、Biolink 类别、小鼠→人同源映射 | 3.1、3.6 |
| 新增受控词表：证据层次、验证状态、干预方向等字段的取值范围 | 3.3 |
| 候选清单字段补充：同源基因、比较角色、逆转、生物学重复数、代谢物鉴定等级、证据等级 | 3.5 |
| 结果包路径与 v2 的项目目录统一；明确 Parquet 为正式格式，TSV/XLSX 只作导出 | 4 |
| 交换契约补充：Schema 的存放位置、版本规则、共享的契约测试样例；TheraWeave 不需要安装 OmicsWeave 即可读取 | 5 |
| TheraWeave 补充：定位与差异化、MVP 范围、`knowledge` 模块、治疗模态初筛规则、更完整的知识来源及许可与保密注意事项、验证计划回流为 OmicsWeave 实验 | 6 |
| OmicsWeave 包结构与 v2 合并（增加 `adapters`、`visualization`、`cli`） | 7.2 |
| 路线图改为两个系统统一编号，并标出阶段之间的前置条件和工期估算 | 8 |
| 风险表补充：范围蔓延、未发表数据外泄、单人开发瓶颈、契约漂移 | 9 |
| 新增决策记录与待决策事项（2026-10-29 已确认物种、运行环境、旧打分模块、课题工作区等）；新增 O5 集群与联网阶段 | 8、11 |

---

## 1. 执行摘要与总体决策

拟构建两个**相互兼容、独立维护**的科研软件系统：

- **OmicsWeave — Biological Evidence Generation Platform**：处理转录组、靶向与非靶向代谢组、代谢流分析（MFA）、蛋白质组及多组学整合数据，输出可复现的定量结果、标准化生物学实体及关联证据、候选通路和靶点假设，以及科研报告。
- **TheraWeave — Evidence-Guided Therapeutic Discovery Platform**：读取上游标准化证据，融合外部生物医学知识，评估候选靶点的机制合理性、可干预性和潜在风险，比较不同治疗模态，并生成供研究人员审核的候选方案和验证研究规划。

**核心架构决策**：

1. **双仓库**：OmicsWeave 与 TheraWeave 分别建仓；不把药物研发功能直接整合进入 OmicsWeave。
2. **结构化数据优先**：Parquet/JSON 等机器可读成果是正式交付接口；HTML/PDF 是同一分析结果的人类阅读视图。
3. **保留组学差异**：各组学保留其专有单位、模型假设、质量指标和不确定性，不能将所有结果硬性压平成通用的差异表达表。
4. **证据和假设分离**：真实测量、统计关联、机制推断、治疗假设分别存储；候选靶点并不等于已验证治疗靶点。
5. **可追溯**：每项候选结果均能回溯至样本、输入数据、分析版本、参数、数据库版本及相关证据。
6. **按阶段落地**：首先完成可靠的分析输出与证据交换规范，再实现靶点优先级，最后扩展各类治疗设计工具。
7. **职责边界**：OmicsWeave 只回答“数据中发生了什么变化、证据有多强”；成药性、已知药物、安全性和治疗模态的判断全部属于 TheraWeave。
8. **只通过文件契约耦合**：两个系统之间不互相导入代码。契约以 JSON Schema、表结构字典、语义规则及标准样例发布；TheraWeave 不需要安装 OmicsWeave 就能读取和校验结果包，也能接收文献、GWAS 等其他来源的候选清单，并标明其能力限制。
9. **排期门控**：正式稳定版本以最小契约 profile 发布为前提。2026-10-30 按项目负责人继续实施的要求，先对现存 0.1 草案建立固定摘要、显式启用的兼容预览；它不构成正式契约承诺。建议上游分步冻结最小 profile，不以全部组学及原始数据适配器完工作为首版前置条件。

### 1.1 端到端总体流程

```text
实验 / 公共数据
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ OmicsWeave                                                    │
│ RNA-seq | Targeted/Untargeted Metabolomics | MFA | Proteomics │
│ Quality Control → Quantification/Statistics → Integration     │
│ → Biological Evidence → Pathways & Target Hypotheses          │
└──────────────────────────────────────────────────────────────┘
    │
    ├─ AnalysisResultBundle：矩阵、表格、证据、假设、来源信息
    └─ Research Report：HTML（默认）/ PDF（可选）
    │
    ▼
版本化 Evidence Exchange Contract（JSON Schema + 表结构 + 语义规则 + 样例）
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ TheraWeave                                                    │
│ Evidence Import → Knowledge Integration → Target Ranking      │
│ → Modality Selection → Therapeutic Candidate Assessment       │
│ → Validation Planning → Decision Report                      │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
人工审查 → 独立数据验证 → 功能实验 → 研究证据反馈
    │
    └─ 验证实验以 OmicsWeave 实验模板（experiment.yaml）的形式回到上游分析，形成闭环
```

> **解释边界**：该系统用于研究假设生成、候选优先级评估与研发决策支持，不应将计算预测直接表述为已经确定的临床有效性、安全性或治疗建议。

### 1.2 项目状态与核验边界（2026-10-30）

TheraWeave 状态来自本次本地实现和验证；OmicsWeave 的历史进度、测试数和提交记录仍为原稿记载。本次追加核对了上游契约源码并运行其写出函数的合成往返检查，没有重跑其完整测试或远端 CI。

| 系统 | 状态 |
|---|---|
| OmicsWeave（历史记录，待核对） | 原稿记载：阶段 O0（工程化打包）已完成，可 `pip install`，统一包内导入与命令行，代码和实验数据目录解耦；185 个测试在 Python 3.10/3.12 下 182 通过、3 跳过；已建立本地课题工作区 `local/`；CI 已编写但当时尚未在 GitHub 运行；阶段 0 提交为 7ef7cf4。O1 的包改名、项目模型、`validate`、`init`、契约草案和示例项目已完成。以上不是本次重新验证的结果 |
| TheraWeave（本次实现） | `0.1.0.dev0` 已具备本地预览闭环：草案导入与校验、证据归档、三个知识源的受限本地转换、规则画像/分桶与敏感性、计划草稿/审查/反馈。59 项测试和合成完整流程通过，已同步本次变化后的上游 0.1 草案并通过真实写出函数的合成往返；正式契约、真实数据库 release、真实课题及独立科学评估仍待验收。详见实施记录 |

---

## 2. OmicsWeave 的职责及输出层次

### 2.1 五层结果模型（Layered Result Model）

| 层级 | 结果类别 | 核心内容 | 推荐载体 |
| --- | --- | --- | --- |
| L1 | Experimental Data | 样本元数据、实验设计、处理后的数据矩阵、MID、质谱定量信息；原始下机文件只登记路径与校验值，不复制 | Parquet、JSON；H5AD/H5MU 为可选导出 |
| L2 | Analysis Results | DEG、差异代谢物、差异蛋白、代谢通量、富集统计和质量指标 | Parquet |
| L3 | Biological Evidence | 基因—转录本—蛋白质—代谢物—反应—通路及组织/细胞类型的标准化关联和证据 | Parquet、JSON |
| L4 | Research Hypotheses | 候选通路、靶点、可能机制、证据分级、知识缺口与验证状态 | JSON、Parquet |
| L5 | Research Reports | 数据质量、主要结果、图表、候选列表、方法学、局限性与溯源链接 | HTML、可选 PDF |

**不变原则**：L1/L2 的原始结果与 L3/L4 的知识解释彼此独立，报告由上述数据生成，不能替代机器可读结果。

### 2.2 各组学模块需要保留的关键字段

| 模块 | 典型结果 | 必备上下文或质量信息 |
| --- | --- | --- |
| Transcriptomics | Gene/Transcript ID、counts、TPM（适用时）、log2FC、p value、FDR | 物种、参考基因组、对比定义、归一化方法、批次/混杂校正 |
| Targeted Metabolomics | 标准品对应代谢物、峰面积/绝对定量浓度、内标结果 | 单位、标准曲线、QC、定量上下限、加合物与峰归属 |
| Untargeted Metabolomics | feature ID、m/z、RT、峰面积、统计差异、候选注释 | feature 与 compound 分离、鉴定等级（MSI 1–4 级）、批次效应及缺失值处理 |
| MFA | Reaction ID、净/交换通量、flux estimate、95% CI 或可行范围、模型拟合 | 通量单位、代谢网络及原子映射、MID 观测/预测、残差、稳态假设、可辨识性、是否碰到拟合边界 |
| Proteomics | UniProt ID、protein group、peptide evidence、abundance、log2FC、FDR | 蛋白推断歧义、定量方式、肽段支持、批次信息 |
| Multi-Omics | 跨组学实体映射、关联网络、通路/模块结果 | 样本配对、跨组学对比条件、模型方法、多个假设检验及证据冲突 |

**所有组学的统计结果都必须带上**：各组实际参与检验的**生物学重复数**、实验单位、配对/重复测量结构、检验方法与单双侧、效应量与不确定性、多重检验方法和检验家族。适用时记录离散检验的 p 值分辨率：对无并列秩、独立两组各 n=3 的**精确** Mann–Whitney U 检验，最小双侧 p=2/C(6,3)=0.10，单侧 p=0.05。这不是所有检验的统一下限；并列秩、渐近法及置换法须按实际方法解释。[SciPy 官方说明](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html)

**特别注意**：

- MFA 的**通量**与代谢组学的**丰度/浓度**是不同物理量；联合解释时需要显式区分。
- MFA 的置信区间、拟合残差和结构/参数可辨识性不能省略。
- MFA 的推断单位是**动物**而不是拟合迭代：约 150 次拟合迭代描述的是同一只动物的参数不确定度，不能当作独立重复（现有代码已遵循这一点，迁移时必须保留）。
- 非靶向代谢组必须区分**未注释 feature**、**推定化合物**和**标准品确认化合物**，不能把不确定的峰直接映射为可靠药物靶点证据。
- 基因、转录本和蛋白同工型之间不保证一一对应。

### 2.3 实验设计语义（新增）

项目、实验、样本、因素与比较的完整定义见 v2 文档第 5 节。这里补充一项对治疗假设至关重要的设计信息：**每个比较的角色（`role`）**。

| `role` 取值 | 含义 | 示例 |
|---|---|---|
| `disease_effect` | 疾病或造模引起的变化 | HFD vs LFD |
| `treatment_effect` | 干预引起的变化 | 在 HFD 小鼠中 GLP1 vs Saline |
| `time_effect` | 时间引起的变化 | 14 周 vs 4 周 |
| `other` | 其他比较 | — |

当同一实体在可比的 `disease_effect` 和 `treatment_effect` 比较中方向相反时，先标记为**反向治疗响应（opposite_direction）**。例如：某分子在 HFD 相对 LFD 时上调，而 GLP1 处理使其下调。
- 这可以提供治疗假设线索，但不能单凭符号判断其证据优于独立功能或遗传证据。
- “方向相反”“趋近健康参照”“恢复正常”“介导疗效”是不同断言。需进一步检查效应量、区间、治疗组对健康组的剩余差异和独立疾病终点；未显著不同不等于等效。
- 两个对比共享对照时存在误差相关，组合效应需共同模型或协方差信息；同一组织内细胞组成、摄食、体重、时间和代偿效应也可能解释响应。
- 用带 `status`、比较引用、方法与限制的 `ReversalAssessment` 取代唯一布尔结论；旧 `reversal=true` 导入时仅保留为方向线索，不能自动升级。

完整状态与判断规则见 [TheraWeave 评审文档](theraweave_design_review.md)第 3.3 节。下例只声明待评估的比较配对，不意味着已经证实逆转。

`experiment.yaml` 中的写法示例：

```yaml
contrasts:
  - {id: HFD_vs_LFD, factor: diet, numerator: HFD, denominator: LFD, role: disease_effect}
  - {id: GLP1_vs_Saline_in_HFD, factor: treatment, numerator: GLP1, denominator: Saline,
     subset: {diet: HFD}, role: treatment_effect}
reversal_pairs:
  - {disease: HFD_vs_LFD, treatment: GLP1_vs_Saline_in_HFD}
```

---

## 3. 跨组学实体标准化与证据图谱

### 3.1 BiologicalEntity 标准模型

建议使用统一的内部实体记录，但为不同类型保留独立命名空间与多对多映射：

| 实体类型 | 主要外部标识符（示例） | Biolink 类别 | 主要用途 |
| --- | --- | --- | --- |
| Gene | Ensembl Gene ID、HGNC/MGI | `biolink:Gene` | 基因定位、差异表达、遗传靶点 |
| Transcript / mRNA | Ensembl Transcript ID、RefSeq | `biolink:Transcript` | 转录本层级和 RNA 相关干预 |
| Protein | UniProt accession | `biolink:Protein` | 蛋白、酶及受体靶点 |
| Metabolite | ChEBI、HMDB、InChIKey | `biolink:SmallMolecule` | 代谢物与化学结构映射 |
| Reaction（新增） | Rhea、KEGG Reaction、MFA 模型内反应 ID | `biolink:MolecularActivity` | MFA 通量与酶/基因的连接 |
| Pathway | Reactome stable ID、GO term | `biolink:Pathway` | 机制与通路富集解释 |
| Tissue / Organ | UBERON | `biolink:AnatomicalEntity` | 解剖组织定位 |
| Cell Type | Cell Ontology（CL） | `biolink:Cell` | 细胞类型定位 |
| Disease | MONDO、EFO、DOID | `biolink:Disease` | 疾病/表型关联 |

所有外部注释应记录 `namespace`、`source_version`、`organism_taxonomy_id`、映射方法及置信度（适用时）。生物学实体的关系可使用 `entity_relationships.parquet` 管理。
- 标注 Biolink 类别是为了让结果能直接接入生物医学知识图谱。类别名称以所用的 Biolink Model 版本为准，记录在 manifest 中。
- MFA 的反应 ID 来自所用的代谢网络模型，必须与模型版本一起记录；它到 Rhea、KEGG 和催化酶基因的映射，由网络模型定义文件提供，不再硬编码在代码里（对应 v2 第 10.3 节）。
- 反应映射需保留方程正方向、区室、GPR 的 AND/OR 关系及汇总/跨器官反应标记；通量估计、FBA 预测与直接测量须分开记录。通量改变本身不证明对应酶是控制步骤，也不决定抑制或激活方向。一个反应映射到多个基因时仍是一份通量来源。[COBRApy GPR 文档](https://cobrapy.readthedocs.io/en/latest/getting_started.html)

### 3.2 区分组织和细胞类型证据的语义

以下字段**不能互相代替**：

- `sample_tissue`：本研究样本实际来自何种组织。
- `expression_context`：特定分子在外部数据/组织中表达的观察证据。
- `proposed_target_tissue`：依据多种信息提出的潜在干预组织，属于假设。
- `cell_type_id`：在存在细胞分辨率证据时附加；Bulk RNA-seq 通常不能直接证明细胞型特异性。若来自反卷积或外部单细胞图谱，必须同时记录 `cell_type_source`。

### 3.3 Evidence 与 TargetHypothesis 分开存储

推荐数据对象：

- `BiologicalEntity`：标准实体及其标识。
- `Association`：两个实体或实体与通路/疾病之间的关联。
- `Evidence`：单条证据（实验/算法/文献/数据库、效应量、统计数据、方向、限制）。
- `PathwayCandidate`：候选通路及命中实体、富集方法、背景集、校正后的统计结果。
- `TargetHypothesis`：可接受进一步研究的干预假设，其证据通过 `evidence_refs` 关联。
- `AnalysisRun`：分析操作的标识、运行参数、软件和数据版本信息。
- `ResearchContext`：疾病/表型、主要终点、实验模型、物种、组织/细胞、时间与营养状态等；下游治疗假设以“靶点 × 疾病/表型 × 方向 × 上下文”为单位。
- `EvidenceDependency`：原始研究/样本集、数据库转载及派生结果的关系，用于避免重复计入独立支持；同一批样本的多组学是互补测量，不等同于独立复现。

证据建议至少分为三个层次：

1. **Observed Findings**：直接测量或模型估计支持的结果；记录其统计和模型条件。
2. **Inferred Mechanisms**：跨组学或数据库推断出的机制，明确标记推断方法和不确定性。
3. **Therapeutic Hypotheses**：关于干预靶点与治疗策略的候选假说，必须标记尚缺少的功能、因果及安全证据。

**受控词表（新增）**：以下字段只能取表中的值，便于下游程序可靠地解析。

| 字段 | 取值 |
|---|---|
| `evidence_level` | `observed` / `inferred` / `hypothesis` |
| `measurement_basis` | `measured` / `estimated` / `predicted` / `curated`；与 `evidence_level` 分开记录 |
| `stance` | `supports` / `contradicts` / `neutral` / `unclear`；针对具体假设与上下文 |
| `validation_status` | `not_tested` / `planned` / `in_progress` / `supported` / `not_supported` / `inconclusive` |
| `effect_direction` | `up` / `down` / `mixed` / `none` / `not_applicable` |
| `intervention_direction` | 建议为 `inhibit` / `activate` / `restore` / `unknown`（由 TheraWeave 填写；OmicsWeave 输出 `unknown`）；`edit` 移至 `intervention_strategy`，旧 `replace` 需显式解释后迁移 |
| `evidence_grade` | `high` / `medium` / `low` / `exploratory`（OmicsWeave 按证据画像规则给出，规则及其版本写入 manifest） |
| `availability_status` | `available` / `not_provided` / `not_applicable`；数值缺失保持 `null`，不用状态字符串填入数值列 |
| `analysis_status` | `completed` / `not_analyzed` / `failed` |
| `result_interpretation` | `detected` / `not_detected` / `inconclusive` / `not_applicable`；需结合方法与检测精度 |

以上是契约冻结前的修订建议。旧 `evidence_status` 混合了来源和结论，不再作为唯一判断；迁移保留原值与转换记录。`effect_direction=none`、`not_supported` 或 `contradicts` 均不能简单由 p > 0.05 自动产生。外部知识查询另外区分“未查询”“失败”“该快照内无记录”。

### 3.4 TargetHypothesis 示例（字段为示意）

```json
{
  "schema_version": "1.0.0",
  "study_id": "study_example",
  "analysis_id": "run_001",
  "species": { "taxonomy_id": 10090 },
  "target_hypotheses": [
    {
      "hypothesis_id": "TH-001",
      "target": {
        "entity_type": "gene",
        "entity_id": "GENE_ID_PLACEHOLDER",
        "id_namespace": "Ensembl",
        "biolink_category": "biolink:Gene"
      },
      "human_orthologs": [
        {
          "entity_id": "HUMAN_GENE_ID_PLACEHOLDER",
          "id_namespace": "Ensembl",
          "orthology_type": "one2one",
          "source": "SOURCE_AND_VERSION_PLACEHOLDER"
        }
      ],
      "context_id": "CONTEXT_ID_PLACEHOLDER",
      "associated_pathways": ["PATHWAY_ID_PLACEHOLDER"],
      "tissue_context": {
        "sample_tissue": "UBERON_ID_PLACEHOLDER",
        "expression_context": null,
        "proposed_target_tissue": null,
        "cell_type_id": null,
        "cell_type_source": null
      },
      "contrasts": [
        { "contrast_id": "HFD_vs_LFD", "role": "disease_effect", "effect_direction": "up" },
        { "contrast_id": "GLP1_vs_Saline_in_HFD", "role": "treatment_effect", "effect_direction": "down" }
      ],
      "reversal_assessment": {
        "status": "opposite_direction",
        "disease_contrast_id": "HFD_vs_LFD",
        "treatment_contrast_id": "GLP1_vs_Saline_in_HFD",
        "limitations": ["phenotype_response_and_residual_contrast_not_assessed"]
      },
      "evidence_refs": ["EVIDENCE-001", "EVIDENCE-002"],
      "evidence_level": "hypothesis",
      "evidence_grade": "exploratory",
      "validation_status": "not_tested",
      "intervention_direction": "unknown",
      "missing_validation": [
        "causal_validation",
        "protein_level_confirmation",
        "tissue_specificity"
      ]
    }
  ],
  "provenance": {
    "software": "OmicsWeave",
    "software_version": "0.1.0",
    "run_manifest": "manifest.json"
  }
}
```

`evidence_refs` 必须实际指向数据包中的独立证据记录，`context_id` 指向研究上下文。上面的版本号与字段是拟议契约形状示意，不是已发布 v1.0；示例含占位 ID，未提供对应引用表，不是可导入测试包。记录独立存储不等于统计上独立。

### 3.5 候选通路与靶点表建议字段

**`pathway_candidates.parquet`**：`pathway_id`、`pathway_name`、`organism`、`method`、`background_set`、`contrast_id`、`contrast_role`、`effect_direction`（若方法支持）、`p_value`、`fdr`、`hit_entity_ids`、`supporting_omics`、`n_tissues_concordant`、`evidence_grade`、`evidence_refs`。

**`target_candidates.parquet`**：

| 字段组 | 字段 |
|---|---|
| 标识 | `target_id`、`target_type`、`entity_id`、`id_namespace`、`biolink_category`、`organism` |
| 人类映射 | `human_ortholog_ids` 或 `ortholog_mapping_refs`、`orthology_type`（如 one2one / one2many）、`ortholog_source`；保留关系表，不用单值丢失多对多映射 |
| 上下文 | `context_id`、`pathway_ids`、`sample_tissue`、`cell_type_id`、`cell_type_source`、疾病/表型与主要终点引用 |
| 证据 | `contrast_id`、`contrast_role`、`effect_direction`、`reversal_assessment_ref`、`supporting_omics`、各组学效应量/区间/校正后 p 值、`n_bio_by_group`、`n_pairs`、实验单位、`dependency_group_ids`、`n_omics_concordant`、`n_tissues_concordant`、`identification_level`（代谢物） |
| 结论 | `evidence_grade`、`causal_evidence_status`、`validation_status`、`evidence_refs`、`limitations`、`flags`（如 `low_n`、`at_bound`、`annotation_uncertain`） |

> 不建议单凭差异表达的 FDR、组学变化方向或通路富集结果生成无条件的“治疗靶点排名”。统计相关性、机制因果性、可成药性和安全性是不同概念。OmicsWeave 只输出**证据等级与各维度指标**，不输出“治疗优先级分数”。

### 3.6 小鼠→人同源映射（新增）

以人类转化为目标时，由小鼠数据得到的候选需附带人类同源映射或明确的缺失状态；映射不证明功能、药理和疾病机制守恒：
- 映射来源（如 Ensembl Compara、HGNC HCOP、MGI）及其版本写入 manifest。
- 一对多、多对多的情况必须保留，不能只取第一个。
- 没有人类同源基因的候选不删除，而是标记为 `no_human_ortholog`，交由下游判断。

---

## 4. 推荐的分析结果包（AnalysisResultBundle）

每次完整分析应有**不可混淆的运行 ID**，并生成自描述结果目录。路径与 v2 的项目目录约定统一：

```text
<项目目录>/analysis_results/<experiment_id>/<run_id>/
├── manifest.json
├── metadata/
│   ├── subjects.parquet              # 由 subjects.tsv 解析校验后写出
│   ├── samples.parquet
│   └── experiment.resolved.json      # 展开后的实际配置（含比较及其角色）
├── omics/
│   ├── transcriptomics/
│   │   ├── data/                     # L1：matrix / features / dataset.json
│   │   ├── qc/
│   │   ├── tables/                   # L2：differential / enrichment
│   │   └── figures/
│   ├── metabolomics/
│   ├── mfa/
│   └── proteomics/
├── integration/                      # 跨组学分析（flux_anchored / pathway_convergence / sample_level）
├── evidence/
│   ├── biological_entities.parquet
│   ├── evidence.parquet
│   ├── entity_relationships.parquet
│   ├── orthologs.parquet
│   └── pathways.parquet
├── hypotheses/
│   ├── pathway_candidates.parquet
│   ├── target_candidates.parquet
│   └── target_hypotheses.json
├── reports/
│   ├── analysis_report.html
│   └── figures/
├── qc/
│   └── quality_metrics.json
└── provenance/
    ├── software_versions.json
    ├── parameters.json
    └── ro-crate-metadata.json
```

单组学运行时可只生成对应的 `omics/<组学>/` 子目录和 `manifest.json`；`integration/`、`evidence/`、`hypotheses/` 按能力声明生成。若未包含正式证据表，下游需通过适配器提取，不能假定它已满足 `evidence_bundle` profile；单组学本身不是拒绝导入的理由。

### 4.1 文件格式选择

- **Parquet（正式格式）**：用于结构化定量表、分析结果和证据清单；列类型可靠、支持列表型字段（如 `hit_entity_ids`），适合批处理与下游程序读取。`pyarrow` 列为基础依赖。
- **TSV / XLSX（导出格式）**：供人工查看，通过 `omicsweave export --format tsv|xlsx` 生成，不作为交换契约的一部分。原因是 Excel 会自动改写基因名、日期等，且列类型不可靠。
- **H5AD/H5MU**：适用于 AnnData/MuData 数据模型能准确表示的矩阵和多模态数据；作为可选导出，不要求所有 MFA/质谱数据转换为这些格式。
- **JSON**：用于 Schema、关联对象、假设、实验设计、参数与 manifest。
- **HTML**：默认报告形式，可实现可交互图表、结果筛选、证据点击跳转。
- **PDF**：论文补充材料、归档、会议汇报等场景按需生成。

> v2 文档已于 v2.1 同步本节决定（第 6.2、7、8 节）。

### 4.2 可复现性与来源追踪

`manifest.json` 建议包含：

- `bundle_schema_version`、`study_id`、`analysis_id`、`created_at`。
- 模块列表、输入文件摘要（checksum）、输出文件清单及其内容类型。
- 物种、实验条件、样本与比较组定义（含比较角色和逆转配对）。
- 代码提交版本（Git SHA）、Python/依赖版本、算法参数与随机种子（如适用）。
- 数据库/注释版本、参考基因组/代谢网络版本、同源映射来源版本、Biolink Model 版本。
- 外部知识库的检索日期（如使用在线接口）。
- QC 状态、重要告警、不可解析实体映射及数据缺失信息。
- `profile`、`required_capabilities`、逐模块完成/失败状态；输出文件大小和 SHA-256、正式运行完成标志。保留各组学的被测/通过 QC/检验/候选集合或其引用及筛选规则，避免只有显著候选而失去背景。

可借鉴 **RO-Crate** 描述结果包结构，借鉴 **W3C PROV-O** 记录数据、分析活动与来源的关系。第一版可以使用简单 manifest，逐步增加兼容性。

### 4.3 报告章节建议

1. 研究概览与实验设计。
2. 数据质量、批次效应与处理流程。
3. 各组学主要结果（附关键统计指标）。
4. 跨组学整合：一致性、互补证据和冲突证据。
5. 候选代谢/信号通路及机制假说。
6. 候选基因、转录本、蛋白受体/酶及组织细胞上下文（含人类同源基因、是否被治疗逆转）。
7. 证据可靠度、模型假设、局限性与待验证问题。
8. 可复现信息、参数、软件/数据库版本及结果文件索引。
9. 自动生成的方法学段落（软件版本、参数、统计方法），可直接改写进论文。

**报告与数据包必须使用同一数据源生成**，避免图表与导出表格出现版本不一致。报告只陈述统计事实与方法参数，候选清单单独成节并明确标注“假设，需实验验证”，不写入课题专用的生物学结论。

---

## 5. OmicsWeave 与 TheraWeave 的交互接口

### 5.1 Evidence Exchange Contract

建议采用**版本化文件交换契约**，起步时不要求部署服务器或数据库：

- 以 `AnalysisResultBundle` 为交换单位。
- JSON Schema 校验 JSON；Arrow/Parquet schema 校验表结构；另有跨表关系和科学语义规则。上游模型可由 Pydantic 定义，下游不依赖其运行时代码。
- 严格检查文件存在、checksum、路径边界、字段类型、显式物种/同源关系、标识符命名空间、单位、对比方向、证据引用完整性及派生关系。跨物种证据允许通过明确映射进入，不要求全部记录物种相同。
- 对不可解析的数据给出明确告警；禁止静默丢弃关键字段。
- 分别记录信息是否提供、分析是否完成、结果解释和对具体假设的支持立场（取值见 3.3 节）；不将缺失、失败和未检出互相转换。
- 按 Schema Version 管理兼容范围和破坏性变更。

**契约的存放与版本规则（新增）**：

| 项目 | 约定 |
|---|---|
| 唯一来源 | OmicsWeave 中的 Pydantic 模型（`omicsweave.contract`） |
| 发布形式 | 由模型生成 JSON Schema，连同表结构字典、语义规则、样例和内容摘要发布到 `schemas/evidence-exchange/v<主版本>/`；TheraWeave 固定引用发布物，不自动跟随上游主分支 |
| 版本号 | 语义化版本：兼容的可选字段可加次版本；删改字段/含义需主版本。新增枚举、默认解释或必需能力须单独判断兼容性，不能假定全部向后兼容 |
| 下游声明 | 声明支持版本范围及能力；未知可选扩展保留并告警，未知必需能力或不可解释枚举拒绝进入评估 |
| 契约测试 | 正常与失败样例随发布物共享，明确预期规则 ID；包含引用错误、单位冲突、去重、多对多映射、缺失、空候选与版本不兼容等场景 |
| 单位 | 尽量使用 UCUM 单位代码，便于程序比较和换算 |

**最小能力等级**：`candidate_list` 只支持候选知识补充与缺口整理；`evidence_bundle` 包含证据、上下文、比较及来源，可作正式评估；`analysis_bundle` 增加可选 L1/L2 数据以增强追溯。仅有汇总表时不能声称进行了样本级整合或重采样。具体字段、四层校验和错误报告见 [TheraWeave 评审文档](theraweave_design_review.md)第 4 节。

**建议的数据流**：

```text
OmicsWeave Result Bundle
   ├─ omics measurements & statistical estimates
   ├─ biological evidence
   ├─ hypotheses
   └─ provenance / QC
               │
               ▼
        Schema Validation
               │
               ▼
     TheraWeave Evidence Import
               │
               ▼
     External Knowledge Integration
               │
               ▼
        Target & Modality Review
```

### 5.2 未来 Python API 示例（完整评估接口的设计目标）

下面的面向对象 `assess_targets()` 仍是未来 API 形状。当前可用 `DiscoveryProject.from_bundle(..., context=..., allow_draft=True)` 生成导入档案，再用公开函数 `assess_archive`、`create_plans`、`review_plan`、`record_outcome` 或相应 CLI 完成预览闭环，见实施记录；实际 API 与下方示意不可混同。

```python
# 上游：在 OmicsWeave 中读取自己的结果包
from omicsweave import load_result_bundle
bundle = load_result_bundle("analysis_results/20250613_dio_glp1/run_2026_001/")

# 下游：TheraWeave 使用已发布契约及自己的校验器，不需要安装 OmicsWeave
from theraweave import DiscoveryProject
project = DiscoveryProject.from_bundle(
    "analysis_results/20250613_dio_glp1/run_2026_001/",
    validate_schema=True,
)
assessment = project.assess_targets()          # 分维度评估，不是单一分数
assessment.to_parquet("target_assessment.parquet")
```

对外同时设计文件式 CLI（`theraweave import <结果包目录>`），便于自动化。CLI 仍需安装 TheraWeave 及 Python，或未来提供的独立运行时；纯文件契约意味着无须安装 OmicsWeave，不意味着命令行可脱离运行时执行。

### 5.3 反向反馈而非篡改上游结论

TheraWeave 生成的人工审查、功能验证、靶点否证、药物筛选结果等应作为**新的证据记录**，通过来源引用关联原始假设，而不是覆盖已有的 OmicsWeave 结果。

**验证闭环**：TheraWeave 输出包含 `plan_id`、`hypothesis_id` 和预设比较的 OmicsWeave 实验草稿（`experiment.yaml` + 样本表模板）。缺少实际样本信息时保持 draft；补齐并经上游校验后才能作为完整配置。实验完成并分析后，结果包回流为新的 `ValidationOutcome` 与证据，保留计划版本、执行偏差、效应/区间、扰动成功与否及审查记录。`validation_status` 针对具体假设和条件更新；不显著或扰动失败不能自动否证整个靶点。最小反馈链路属于 T1。

---

## 6. TheraWeave：靶点证据评估与验证研究系统

### 6.1 目标与范围

**目标**：将组学证据与外部知识结合，按明确疾病/表型和实验上下文形成候选靶点证据档案、验证优先级、干预策略比较及可否证的实验计划。治疗策略扩展以这一研究闭环为基础。

**不应作为初期目标**：独立重建所有化学、蛋白结构、CRISPR、RNA 药物设计或临床决策算法；对研究计算结果作出未经验证的有效性/安全性承诺。

**定位与差异化（新增）**：
- 每种治疗模态本身都是一个成熟领域，各有专业工具；只在这些工具外面包一层，附加价值很低。
- TheraWeave 的价值在于**“组学证据 → 干预方案 → 验证实验”这一转化环节**。
- 具体聚焦：保留统计/模型不确定性、证据依赖及冲突，回答限定疾病、组织和实验条件下“为什么验证该靶点、方向依据是什么、哪个实验能区分替代解释”。这是待验证的价值主张，不能仅凭闭环、可解释、多模态或 AI 等类别宣称独有能力。
- 首个聚焦领域：**代谢性疾病**，以及由 MFA 通量锚定的代谢酶、转运体靶点。这与上游数据（DIO、GLP-1、袖状胃切除等研究）直接相关，其中 GLP-1 本身就是多肽药物。
- 2026-10-30 已由项目负责人确认：沿用代谢性疾病优先，保留通用扩展接口；MFA 是优势输入，不是所有研究的强制前提。
- 与 Schrödinger 等专业平台采用可互补、可双向回流的分工；其已有靶点结构研究、分子/生物药设计和协作闭环。近期对照还应包含 Open Targets、IPA/Pathfinder 类组学解释与靶点工具，详见 6.7 节。

**MVP 范围（新增）**：
- **包含**：最小结果包导入与多层校验、证据去重和冲突、受控本地知识整合、分维度评估与规则分桶、模态及实验工具初筛、验证计划与最小结果反馈、决策报告和基准评估。
- **不包含**：分子生成、结构设计、任何治疗模态的设计工具对接（放到阶段 T2）。

### 6.2 功能模块

| 模块 | 工作内容 | 典型输出 |
| --- | --- | --- |
| `contract` | 基于版本化契约完成 JSON/Parquet 及语义校验，按输入 profile 接收结果包或候选清单 | 校验报告、能力限制、内部证据对象 |
| `knowledge`（新增） | 外部知识源注册表：每个来源的版本、下载/检索日期、许可；本地快照与缓存 | 可复现的知识快照 |
| `evidence` | 合并上游与外部证据，维护原始来源、样本重叠、派生关系、去重和冲突 | 表结构表示的 Evidence Graph |
| `targets` | 上下文限定的假设画像、规则分桶、方向/风险缺口及敏感性分析 | Target Assessment 与选择/暂缓理由 |
| `modalities` | 比较不同治疗模态的机制适配与限制 | Modality Comparison |
| `repurposing`（T2） | 匹配直接靶点、机制、方向和适应证，区分通路线索 | Repurposing Candidates；T1 只输出实验工具线索 |
| `evaluation` | 采用适当基准集和指标验证模型 | Model Evaluation |
| `experiment_planning` | 可否证假设、对照/正交扰动/救援、主要终点、实验单位、精度/样本量依据、预设判定；导出草稿并接收验证反馈 | Validation Plan / Outcome 与审查历史 |
| `reporting` | 导出可审查的研究决策报告 | HTML/PDF/JSON |

### 6.3 预留的治疗模态

| 模态 | 适合的研究功能 | 不可忽略的条件 |
| --- | --- | --- |
| Small molecule | 药物再利用、虚拟筛选、性质预测、候选分子评价 | 靶点结合与选择性、ADMET、实验确认 |
| Antibody | 胞外/膜靶点的阻断、激动或其他机制比较 | 表位可及性、跨物种识别、组织分布与功能验证 |
| DNA / Gene editing | 目标基因和编辑策略适配性、现有工具对接 | 编辑后的功能方向、脱靶、递送、组织特异性、持久性效应 |
| Gene supplementation / delivery | 功能恢复或补充的研究方案 | 与 DNA 编辑分开；表达定位、剂量、持续性和递送 |
| mRNA | 表达补充与功能恢复的研究方案 | 干预方向、RNA 稳定性、过量表达、递送及免疫反应 |
| siRNA / ASO | RNA 降低、剪接调节等机制分别评估 | 靶转录本、亚细胞定位、序列特异性及目标细胞递送 |
| Peptide therapeutics | 多肽候选方案的结构与性质评价 | 稳定性、特异性、亲和力和递送 |

**重要区分**：RNA 表达补充与 RNA 降解抑制属于不同的干预机制；同样，基因差异表达方向不能直接决定应该激活、抑制、替代或编辑某个靶点。

**模态初筛规则（新增，仅作初筛，必须由专家审核）**：

| 靶点特征 | 优先考虑的模态 | 主要依据 |
|---|---|---|
| 膜受体或胞外蛋白 | 抗体、多肽 | 亚细胞定位（UniProt）、已有配体 |
| 具有可结合口袋的酶 | 小分子 | 已知配体与可成药性评估（ChEMBL、Open Targets） |
| 在明确的目标细胞中需要降低相关转录本 | siRNA / ASO 的适用机制 | 靶转录本、细胞摄取和递送证据；仅有肝脏表达不足以判定递送可行 |
| 功能缺失、需要恢复表达 | mRNA、基因治疗 | 干预方向、递送可行性 |
| 已有药物有直接靶点和匹配作用方向的证据 | 实验工具线索；T2 再评估药物再利用 | assay、机制、物种、暴露、选择性与适应证；仅同通路只记通路线索 |

### 6.4 靶点优先级应采用多维证据，而非不透明单一得分

建议至少评价：

1. **统计证据**：效应量、显著性、研究质量与重复性。
2. **多组学一致性**：跨组学是否互相支持，是否存在合理冲突。
3. **机制与因果性**：独立干预实验、遗传学证据等支持程度；是否被治疗逆转。
4. **组织/细胞上下文**：靶部位可及性、细胞类型和表达范围。
5. **可干预性**：分子类型、结构或功能特征、可用治疗模态。
6. **安全性**：潜在组织外效应、基本生物学功能与已有风险信息（如小鼠敲除表型）。
7. **转化相关性**：物种差异、人体疾病相关性和外部重复证据。

早期优先展示**分维度评分、来源、缺失值与证据冲突**；没有充分验证前，不应对外宣称“模型分数=成药成功概率”。

首版采用证据画像与规则分桶（可进入功能验证 / 优先补证据 / 优先解决冲突 / 暂缓审查），同时展示覆盖率、独立研究来源和选择理由。缺失值不填 0，不通过重新归一化抬高缺信息候选；风险与方向冲突不能由其他维度高分抵消。验证价值与治疗开发成熟度分开，允许高价值但未充分表征的候选进入小规模验证。规则及敏感性分析、候选检测背景和防泄漏基准详见配套评审第 4、5、9 节。

### 6.5 可集成的现有工具与知识来源（选型示例）

| 用途 | 来源 |
|---|---|
| 靶点—疾病证据、按模态的可成药性评估 | **Open Targets** |
| 已知配体、生物活性、作用机制 | **ChEMBL** |
| 已获批药物及其靶点 | **DrugBank**（使用条款按用途区分，商业用途需授权） |
| 蛋白功能、亚细胞定位、蛋白类别 | **UniProt** |
| 组织与细胞表达（安全性评估） | **Human Protein Atlas**、**GTEx** |
| 小鼠敲除表型 | **IMPC**、**MGI** |
| 小鼠→人同源映射 | **Ensembl Compara**、**HGNC HCOP** |
| 通路与生物学实体映射 | **Reactome** |
| 化学信息学基础能力 | **RDKit** |
| 分子机器学习基础组件 | **DeepChem** |
| 药物发现数据任务与基准评价 | **Therapeutics Data Commons** |
| 基因编辑相关靶位点分析 | **CHOPCHOP** |
| 结构与分子计算（T2 可选，属于预测后端） | **Schrödinger** 等专业平台；不作为默认运行依赖，其预测与公共知识/实验观察分层管理 |

这些均应当通过适配器与版本记录接入；**不默认提供外部平台授权、数据许可或网络访问权限**。

**许可与保密（新增）**：
- 各数据源的许可条款不同，部分限制商业用途或再分发。`knowledge` 模块须为每个来源记录许可，并在报告中注明。
- **用在线接口查询候选清单，等于把未发表的研究假设发送给第三方。** 默认应使用下载到本地的数据快照；需要在线查询时，须由用户显式开启，且只发送标识符，不发送任何组学数据。
- 使用本地快照也有利于结果复现。
- 快照须记录母版本、子集提取条件、checksum、适配器版本和覆盖范围；未命中不等于没有生物学关联。第三方数据许可独立于代码许可，首版不把全量数据库捆绑进安装包。

### 6.6 建议的仓库结构

```text
TheraWeave/
├── pyproject.toml
├── README.md
├── src/
│   └── theraweave/
│       ├── core/
│       ├── contract/          # 结果包导入与 JSON Schema 校验
│       ├── knowledge/         # 知识源注册表、本地快照、各来源适配器
│       ├── evidence/
│       ├── targets/
│       │   ├── prioritization/
│       │   └── tractability/
│       ├── modalities/
│       │   ├── small_molecule/
│       │   ├── antibody/
│       │   ├── gene_editing/
│       │   ├── gene_delivery/
│       │   ├── rna_therapeutics/
│       │   └── peptide/
│       ├── repurposing/
│       ├── experiment_planning/
│       ├── evaluation/
│       ├── reporting/
│       └── cli.py
├── tests/
│   └── contract/              # 使用 OmicsWeave 发布的标准样例结果包
├── examples/
└── docs/
```

依赖策略：基础安装只包含导入、知识整合和报告所需的轻量依赖；RDKit、深度学习框架等按模态放入可选依赖（extras），与 OmicsWeave 的做法一致。

以上为长期目录规划；T1 先实现规则和证据接口，不必一次建立所有模态子包。无需图数据库、LLM 或 GPU 即可完成首版闭环。TheraWeave 自己的评估结果包、运行清单、决策日志与实验反馈结构见配套评审第 8 节。

### 6.7 与 Schrödinger 等生态的定位及对接

Schrödinger 的 [SiteMap](https://www.schrodinger.com/platform/products/sitemap/)覆盖结合位点与可干预性，[LiveDesign](https://www.schrodinger.com/platform/products/livedesign/)整合计算/实验与团队决策，相关产品还覆盖自由能、生物药及 AI 工作流。因此，两套生态不是互不重叠的前后两段，也不能以“只有本项目形成研究闭环”作为差异化。

本项目优先建立“组学/MFA 定量语义 → 上下文与证据依赖 → 可检验靶点假设 → 功能实验反馈”的可靠性。结构研究可在不同阶段提供口袋、工具或分子优化线索；分子结合、功能扰动、组织作用和表型效应分别建证据，不能互相替代。

T2 先定义经审查的文件交接及结果回流，再按实际授权/部署验证命令或 API。外部请求关联假设版本、上下文、物种/构建体和结构/分子身份；结果保存任务、方法、参数、单位、优劣方向、不确定性、来源和内容摘要，保持 predicted/inferred 层级与派生依赖。具体最小字段和阶段门槛见[生态比较与对接规划](schrodinger_ecosystem_comparison.md)第 8 节。

此规划不引入新的强制依赖，不表示已有 Schrödinger 接口或授权。近期优先完成真实课题与独立科学验收；性能评价应区分靶点验证效用和后端专用预测质量。

---

## 7. 仓库边界、依赖策略与治理

### 7.1 为什么分成两个独立仓库

| 维度 | OmicsWeave | TheraWeave |
| --- | --- | --- |
| 目标 | 组学定量分析与生物学证据 | 治疗靶点及干预策略决策支持 |
| 核心输入 | 实验数据与组学矩阵 | 组学证据包、知识库与研究证据 |
| 关键输出 | 可复现的分析结果和研究假设 | 候选靶点、模态比较、验证计划 |
| 计算生态 | 统计分析、MFA、质谱和组学专用包 | 化学信息学、结构/分子模型、治疗模态工具 |
| 验证重点 | 算法正确性、统计与模型假设 | 基准评价、独立验证、转化风险 |
| 适用人群 | 组学分析与系统生物学研究者 | 靶点研究和治疗发现研究者 |

独立仓库可以降低复杂依赖的相互干扰、允许不同发布周期，也可以让 TheraWeave 将来接收**非 OmicsWeave** 来源的数据。

### 7.2 OmicsWeave 内部仓库策略

延续此前决策：**OmicsWeave 初期采用 Monorepo + 单 Python 分发包**，各组学使用独立模块和可选依赖（extras）；成熟后按需演化为同仓库多包，不因功能种类多就立即拆分仓库。

目标包结构（合并 v2 第 4.2 节）：

```text
OmicsWeave/
├── pyproject.toml
├── schemas/evidence-exchange/v1/   # 发布的 JSON Schema 与标准样例结果包
├── src/omicsweave/
│   ├── core/                       # 项目模型、配置校验、统计、ID 映射、溯源
│   ├── contract/                   # 结果包与交换契约的 Pydantic 模型、读写与校验
│   ├── adapters/                   # 外部工具适配器：原始数据 → 分析层
│   ├── transcriptomics/
│   ├── metabolomics/
│   ├── mfa/
│   ├── proteomics/
│   ├── integration/                # 跨组学统计整合（由现 multiomics/ 改名）
│   ├── evidence/                   # 实体标准化、证据记录、候选假设生成
│   ├── reporting/
│   ├── visualization/
│   └── cli.py
├── tests/
├── examples/
└── docs/
```

**依赖方向**：`core` 不依赖具体组学模块；各组学模块尽量仅依赖 `core`；`integration/evidence/reporting` 通过稳定接口组合模块结果。`integration` 负责跨组学的统计分析，`evidence` 负责把统计结果转成标准化的证据和假设记录，两者不合并。

### 7.3 是否建立独立公共 Schema 仓库

**初期不建议**再建第三个仓库。先为交换格式制定版本化的文件规范（存放位置见 5.1 节），并在两个项目中进行兼容性测试。当交换契约稳定、已有外部用户或第三方项目需要直接依赖 Schema 时，再考虑单独抽取 `omics-evidence-schema` 轻量包。

### 7.4 测试与质量门禁

- 单元测试：统计计算、实体映射、序列化/反序列化和单位转换。
- Schema 契约测试：版本兼容、必填字段、引用完整性及异常输入；两个仓库的 CI 都运行标准样例结果包。
- 数据集回归测试：固定公开/合成测试集上的结果稳定性；迁移现有课题时，新旧结果逐项比对。
- MFA 专项测试：通量单位、可辨识性、MID 拟合、约束与网络版本。
- 报告一致性测试：报告内数值与机器可读结果一致。
- 人工科学审查：候选解释的适用范围和因果性是否被夸大。
- TheraWeave 行为验收：来源去重幂等、同批样本不伪增独立支持、缺失不变阴性、反向响应不变因果、GPR/同源歧义保留、空候选可解释、反馈有历史。
- 科学评估从 T1 开始：简单排序与单源基线、MFA/知识消融、按原始研究拆分及时间泄漏检查；未知靶点不作真阴性，公开结果不能同时作为特征与验证标签。详见配套评审第 9 节。
- 生态对照按相同问题选择：组学解释/靶点评估比较公开基线、人工审查和具备授权的可比工具；结构后端单独评价其专属任务。记录独立功能验证、关键假设解决率及实验/时间成本，不以软件数量或 docking 分数充当整个系统的科学效用。

---

## 8. 分阶段开发路线（Roadmap）

两个系统统一编号：`O` 为 OmicsWeave，`T` 为 TheraWeave。原工期按 1 名主要开发者估算，未经实现验证；TheraWeave 按下述分阶段产物验收，在首个真实结果包接通后重估。OmicsWeave 各阶段详细任务原引用 v2 第 11 节，待取得对应文档核对；O0/O1 勾选状态保留自上游历史记录。

### 8.1 总览与前置条件

```text
O0 打包 ✅ ─▶ O1 核心契约与项目模型 ─▶ O2 各组学接入 + 证据/假设 + 契约 v1 ─┬─▶ O3 原始数据适配器 ─▶ O4 OmicsWeave 发表
                    │                                                  │
                    └─ T0 TheraWeave 设计与契约评审（不写功能代码）      └─▶ T1a 导入 ─▶ T1b 评估 ─▶ T1c 验证闭环
                                                                                                     ├─▶ T2 按需模态扩展
                                                                                                     └─▶ T3 发布与发表
```

| 阶段 | 前置条件 | 工期 | 版本 |
|---|---|---|---|
| O0 工程化打包 | — | 已完成 | — |
| O1 核心契约与项目模型 | O0 | 6–8 周 | OmicsWeave v0.2 |
| T0 TheraWeave 设计 | 可与 O1 并行（只写文档） | 1–2 周 | 设计文档 |
| O2 各组学接入 + 证据层 + 契约 v1 | O1 | 6–8 周 | OmicsWeave v0.3、契约 v1.0 |
| T1a / T1b / T1c TheraWeave MVP | 所消费的最小契约 profile 发布；依次完成导入、评估和实验闭环 | 原估 8–10 周仅作历史参考；首个真实导入后重估 | TheraWeave v0.1 |
| O3 原始数据适配器 | O2 | 8–12 周 | OmicsWeave v0.4 |
| T2 模态扩展 | T1 | 每种模态 4–8 周 | TheraWeave v0.2+ |
| O4 / T3 发表 | O2（O3 可选）/ 稳定 T1 与独立评估；T2 不作为硬性前置 | 原估各 4–6 周，待按证据与投稿要求重估 | 按成熟度发布 |
| O5 集群部署与多客户端联网 | O4；按实际需求启动 | 视规模而定 | v1.x |

> **单人开发约束**：同一时间只推进一个“写代码”的阶段。O2 之后先做 T1 还是 O3，取决于实验室的近期目标（见第 11 节）。

### Phase O0 — OmicsWeave：工程化打包 ✅

- [x] 初始化统一仓库及模块化 Python 包（`pyproject.toml`、可选依赖、`src/` 布局）。
- [x] 统一包内导入，删除 `sys.path` 修改；代码与实验数据目录解耦。
- [x] 统一命令行入口；测试迁至 `tests/`；编写 CI 配置。
- [x] 提交改动（7ef7cf4）。
- [ ] 在 GitHub 上跑通 CI。

### Phase O1 — OmicsWeave：核心契约与项目模型

- [x] 包改名：`common`→`core`、`multiomics`→`integration`；删除兼容转发模块。
- [x] 项目模型：`project.yaml` / `experiment.yaml` / `subjects.tsv` / `samples.tsv`，含比较角色与逆转配对。
- [ ] 定义 `AnalysisRun` 和 `AnalysisResultBundle` 的最小字段（`omicsweave.contract`）：数据集、差异结果表与运行清单（草案 0.1）已完成，富集与 MFA 结果表待补。
- [x] MFA 求解结果标准格式（Excel 模板 / Parquet 目录）与旧版自研软件格式转换器（`omicsweave mfa template / check / convert`，v2 第 6.2 节）。
- [ ] 标准化单位、对比组、物种、软件版本与 QC 记录。
- [ ] `omicsweave init / validate / migrate`；用 `migrate` 转换现有课题的旧配置：`init`、`validate` 已完成，`migrate` 等课题数据本地副本就位。
- [ ] 删除废弃脚本（v2 第 10.5 节，已失效的已删除，其余按替代进度删除）；课题数据本地副本就位后，把课题专用脚本移到 `local/projects/<课题>/analysis/`（v2 第 10.4 节）。
- [ ] 运行函数改为接受显式的项目上下文，逐步去除进程级全局状态（为 O5 预留）。
- [x] 合成示例项目（`examples/demo_project`，CI 中运行 validate）；补 CITATION.cff；修复 SSL 校验。

**验收标准**：示例项目能通过 `validate`；迁移后的现有课题 MFA 结果与迁移前逐项一致。

### Phase O2 — OmicsWeave：各组学接入、证据整合与报告

- [ ] RNA-seq、代谢组、MFA、蛋白组改为读取分析层数据、输出统一结果表（Parquet）。
- [ ] 单组学独立运行与三种整合模式（v2 第 9 节）。
- [ ] 引入 `BiologicalEntity` / `Association` / `Evidence` / `PathwayCandidate` / `TargetHypothesis`。
- [ ] 接入通路数据库和标准实体 ID 映射；ID 映射改为数据文件 + 解析器；加入小鼠→人同源映射。
- [ ] 实现候选通路与靶点清单，保留证据冲突、逆转标记与未验证标记。
- [ ] 生成 HTML 研究报告（含自动方法学段落）；根据需求增加 PDF。
- [ ] 定义 Evidence Exchange Contract v1，发布 JSON Schema 与标准样例结果包，编写 Schema 校验器。

**验收标准**：结果可被独立程序读取、复现其来源信息，并且没有丢失特有的科学语义；任一候选通路/靶点可回溯到具体统计结果、输入样本和来源数据库。

### Phase O3 — OmicsWeave：原始数据适配器

- [ ] 转录组 `fastq.gz` → cutadapt → kallisto/salmon。
- [ ] 蛋白组 Thermo `.raw` → DIA-NN；`.raw` → mzML。
- [ ] 代谢组 `.wiff`/`.raw` → msconvert → MS-DIAL/MZmine/Skyline 结果导入；同位素示踪 MID 的天然丰度校正。

**验收标准**：每种原始格式都有公开小样例，能从原始文件跑到分析层数据。

### Phase T0 — TheraWeave：设计与契约评审

- [x] 编写 TheraWeave 设计评审及首版实施规格（2026-10-30）；当前部分已进入可运行预览，详细状态见实施记录。
- [x] 从下游需求提出最小 profile、科学语义与样例验收需求。
- [x] 取得并核对上游配套文档和现有 0.1 草案实现，记录与拟议最小 profile 的差距及来源文件摘要。
- [ ] 将新增科学语义与 profile 需求落实到 O1/O2 的权威契约并发布。
- [ ] 正式核查名称与商标。

### Phase T1 — TheraWeave：靶点发现 MVP

- [x] 建立独立 `TheraWeave` 仓库（仅仓库和文档就绪）。
- [x] **T1a 预览**：基础打包与 CLI、显式 0.1 草案导入、JSON/Parquet/已知语义校验、来源去重、可定位错误与证据档案；不依赖 OmicsWeave 安装，已通过合成往返检查。
- [ ] **T1a 正式验收**：发布的最小 profile、完整引用/样本语义、真实研究结果包及科学审查；不将预览完成等同于本项完成。
- [x] **T1b 预览**：三个知识来源受限本地格式转换、统一快照、来源链/摘要/引用、跨来源原记录去重；自动记录默认未审查。
- [ ] **T1b 数据验收**：真实 release 的许可与字段覆盖核对、映射歧义处理、真实课题快照及跨 ID/物种关联。
- [x] **T1b 预览**：上下文限定的八维画像、四桶规则、方向冲突/风险门槛、来源与原始研究移除敏感性、工具线索和描述性基线。
- [ ] **T1b 科学验收**：独立标签、时间/研究拆分、MFA 与知识增益消融、模态适配校准和真实表现；当前无准确率声明。
- [x] **T1c 预览**：计划草稿、主要终点/设计/预设规则的显式审查、关联 ID、空样本 OmicsWeave 草稿模板；未知样本量/方差不自动填数。
- [x] **T1c 预览**：精确计划版本的支持/不支持/不确定结果回流，保留历史及上下文，阻断风险未解决不能推进审查。
- [ ] **T1c 科学验收**：真实终点与实验能力、样本量依据、完整上游配置校验及真实验证结果。
- [x] 输出与正式评估数据同源的预览决策报告，列出缺口及暂缓理由。

**验收标准**：按配套评审第 9 节的正常/反例样例检查规则行为；固定输入、快照与规则得到一致结果，离线模式不发网络请求；至少一个真实结果包完成证据审查，合成反馈完成假设版本更新。实验模板缺信息时显示 draft，补齐后需实际通过对应版本 `omicsweave validate`；这项跨仓库验收不得由下游单独声称完成。科学有效性与工程跑通分别报告。

### Phase T2 — 治疗模态扩展与验证闭环

- [ ] 优先加入已有药物检索、再利用和小分子性质评估。
- [ ] 定义外部计算请求/结果的文件交接与回流契约，保留靶点构建体、分子身份、方法适用域、单位、来源和依赖；先以固定样例验收。
- [ ] 按实际科学缺口逐项验证 Schrödinger 等可选专业后端；先人工审查文件交接，再考虑命令/API；不以接入后端数量为目标，不默认提交云任务。
- [ ] 逐步增加 RNA、基因编辑和多肽模态的独立适配器；顺序按实验室湿实验验证能力决定。
- [ ] 扩展 T1 已有的验证结果模型与反馈链路，适配新增模态的特有读数。
- [ ] 根据用户、协作及版本需求决定是否拆分子包或公共 Schema。

### Phase O4 / T3 — 独立评估、发布与发表

- [ ] 利用独立基准数据/实验结果评估靶点筛选质量。
- [ ] 汇总 T1 起积累的基线、消融与前瞻验证记录；明确研究范围、数据泄漏限制、未标记候选和不确定结果，不以完成全部模态为发表前置。
- [ ] 对外定位和比较使用具体科学问题：在可比条件下评估组学解释与靶点工具；若有结构后端，另报专属任务表现。没有授权或实测时不宣称优于商业平台。
- [ ] 英文文档、教程、API 文档；PyPI 发布与 Zenodo 存档。
- [ ] OmicsWeave 与 TheraWeave 分别投稿（JOSS / Bioinformatics Application Note 等）。

**验收标准**：经过独立研究数据检查后，系统能稳定支持可审查的研究决策，而非仅给出不可验证的生成式结论。

### Phase O5 — 集群部署与多客户端联网（v1.0 之后，按需）

- [ ] 多节点集群：原始数据处理与大批量分析交给作业调度器（如 Slurm）或 Snakemake/Nextflow，项目目录放在共享存储上。
- [ ] 多客户端联网：服务端提供任务提交、排队与状态查询接口，加入用户认证与项目级权限；客户端只提交配置、查看结果包。
- [ ] TheraWeave 视需要以同样方式提供服务接口。

前提：O1–O2 已去除进程级全局状态，所有步骤都能以“配置 + 输入文件 → 结果包”的方式独立运行（v2 第 4.1 节）。

---

## 9. 关键风险与架构护栏

| 风险 | 可能后果 | 设计护栏 |
| --- | --- | --- |
| 把统计关联当作因果关系 | 靶点筛选方向偏差 | 证据等级分层，明确“仅相关”状态 |
| 重复转载或派生分析被当作独立证据 | 虚增置信度 | 保留原始研究、样本重叠及派生关系，按证据家族汇总 |
| 缺失、失败和不显著都变成阴性 | 错误排除靶点或误判低风险 | 正交状态字段，保留检测能力与结果区间 |
| 逆转/通量变化直接决定抑制方向 | 将代偿或标志物当作治疗机制 | 明确参照、GPR、控制关系与方向依据，允许未知和竞争假设 |
| 知识源同时提供特征和基准标签 | 产生虚高性能 | 研究/时间切分、标签来源隔离、原始来源泄漏审计 |
| 非靶向代谢物错误注释 | 通路/靶点错误映射 | 保留鉴定等级与未注释 feature |
| 混淆 MFA 通量与浓度 | 错误解释生理机制 | 保留单位、模型前提与通量置信区间 |
| 伪重复（把拟合迭代当作生物学重复） | 显著性被严重高估 | 统计只在生物学重复间进行；结果表记录实际重复数 |
| 跨物种直接映射 | 转化研究偏差 | 记录物种和 ortholog 映射关系，保留一对多映射 |
| 混淆取样组织与治疗靶器官 | 错误定位干预部位 | 使用独立组织/细胞语义字段 |
| 大型不可解释靶点评分 | 结论无法审查 | 提供逐维度证据和规则 |
| 上下游紧耦合 | 系统升级困难 | 独立仓库、稳定的交换契约和契约测试 |
| 契约在两个仓库间漂移 | 下游静默读错数据 | 单一来源生成 Schema；语义化版本；双方 CI 运行同一组标准样例 |
| 报告脱离正式结果数据 | 图表与数据版本不一致 | 报告由同一结果包自动生成 |
| 外部知识库变更 | 不可复现与结果漂移 | 来源、版本、检索时间及许可记录；默认使用本地快照 |
| 未发表数据或假设外泄 | 竞争与合规风险 | 在线查询默认关闭，只发送标识符；示例只用合成或公开数据 |
| 药物设计预测被过度解读 | 误判安全性/有效性 | 仅定位科研决策支持，保留人工审核与验证环节 |
| 范围蔓延（同时铺开四种治疗模态） | 每种都做不深，维护负担过重 | MVP 不含设计工具；模态按湿实验能力逐个加入 |
| 以通用功能类别充当差异化 | 重复已有平台，科学增量不清楚 | 承认 LiveDesign、IPA/Pathfinder 等重叠，以具体代谢病证据问题和独立效用验证定位 |
| 将分子预测越级解释为疾病因果或疗效 | 错误推进靶点与实验 | 结构/结合、功能、组织和表型证据分层，外部结果保留适用域与依赖 |
| 单人开发瓶颈 | 两个仓库同时停滞 | 同一时间只推进一个写代码阶段；先冻结最小消费 profile，再分步完成 T1a/b/c |

---

## 10. 项目名称与最终定位

| 系统 | 推荐名称 | 英文定位 | 仓库建议 |
| --- | --- | --- | --- |
| 多组学分析 | **OmicsWeave** | *Biological Evidence Generation Platform* | `OmicsWeave`：单仓库内模块化开发 |
| 下游治疗发现 | **TheraWeave**（暂定） | *Evidence-Guided Therapeutic Discovery Platform* | `TheraWeave`：独立 Git 仓库 |
| 公共数据契约 | （未来按需抽取） | *Evidence Exchange Schema* | 初期只保留版本化规范，不单独建仓 |

**名称检索结果（2026-10-29，初步）**：

| 名称 | PyPI | GitHub 仓库搜索 | 网页检索 |
|---|---|---|---|
| OmicsWeave | 无同名包 | 无同名仓库（不含本项目） | — |
| TheraWeave | 无同名包 | 无同名仓库 | 未发现同名产品；有名称相近的儿科康复平台 TheraWe / TheraWee，领域不同 |
| TheraFoundry（备选） | 无同名包 | 无同名仓库 | 未发现同名产品 |

**推荐 TheraWeave 而非 TheraFoundry**：
- 与 OmicsWeave 构成同一系列，“Weave”也贴合“编织证据与治疗策略”的定位。
- “Foundry”已被大量软件产品使用；“biofoundry”在合成生物学中专指自动化湿实验平台，容易引起误解。

以上只是初步检索，不等于商标核查。`TheraWeave`、`OmicsWeave` 的域名与商标可用性尚需正式核实；本文不表示这些名称已获得注册或独占使用资格。“Thera-” 前缀在生物技术公司名中较常见，商标核查时需特别留意。

### 一句话总结

> **OmicsWeave 负责把组学数据转化为可信、可追溯的生物学证据；TheraWeave 负责把这些证据与外部知识结合，提出可审查、可验证的治疗干预研究方向。**

---

## 11. 决策记录与待决策事项

2026-10-29 已确认的决定（OmicsWeave 侧的完整说明见 v2 文档第 13 节）：

| 事项 | 决定 | 影响阶段 |
|---|---|---|
| 契约模型与校验库 | Pydantic v2 作为唯一来源，导出 JSON Schema | O1 |
| 正式结果格式 | Parquet（本文 4.1 节；v2.1 已同步） | O1 |
| 首批支持的物种 | 小鼠（taxon 10090）+ 人（taxon 9606） | O2 |
| 运行环境 | 当前 Windows/Linux 单机；以后扩展多节点集群与多客户端联网（O5）。从 O1 起去除进程级全局状态，为此预留 | O1–O5 |
| 旧打分模块 `flux_omics_scorer` | 尚未发表且策略过于粗糙：删除加和总分与 `legacy_*` 输出，不保留 `--legacy`；多维证据画像作为唯一整合结果，按维度给出证据等级；证据提取部分保留并重构 | O2 |
| 课题专用脚本与数据 | 暂不移动外部项目的原始数据；本仓库已建立不提交的本地工作区 `local/projects/<课题>/`（脚本放 `analysis/`），通过 `--project-dir` / `OMICSWEAVE_PROJECT_DIR` / `pytest --project-dir` 指定 | O1 |
| 开源许可证 | BSD-3-Clause，OmicsWeave 与 TheraWeave 相同。OmicsWeave 版权方为 “The OmicsWeave Developers”，`LICENSE` 已加入；TheraWeave 建仓时按同样方式署名 “The TheraWeave Developers” | O0 / T1 |

仍待决定：

| 事项 | 建议 | 影响阶段 |
|---|---|---|
| O2 之后先做 T1 还是 O3 | 若近期目标是尽快形成治疗假设并开展验证，先做 T1；若近期要处理新的原始下机数据，先做 O3。现有课题数据已处理成表格，因此倾向于先做 T1 | O3 / T1 |
| 外部知识源及其许可 | 先用 Open Targets、ChEMBL、UniProt；DrugBank 等按用途核实条款后再接入 | T1 |
| TheraWeave 首批治疗模态 | 药物再利用 + 小分子性质评估；其余按湿实验验证能力排序 | T2 |

2026-10-30 补充：

| 状态 | 事项 | 内容 |
|---|---|---|
| 项目负责人已确认 | 首版范围 | 代谢性疾病优先，保留通用扩展接口 |
| 本次设计建议 | 科学语义和首版拆分 | 按配套评审补齐上下文、证据依赖、方向、缺失、实验反馈和 T1a/b/c 验收 |
| 待上下游落实 | 最小契约发布 | 已核对实际 0.1 草案并捕获只读消费快照；新增字段仍需在上游落实发布，不在本仓库维护第二套权威契约 |
| 首个真实案例前落实 | 实验条件 | 确定具体研究、主要终点、可用数据与湿实验能力，才能校准门槛和排期 |
| 本轮纳入规划 | 生态分工与价值验证 | 与 Schrödinger 等专业平台按问题互补；T1 证明具体组学/MFA 与验证效用，T2 才按需求接入后端；不把多模态、闭环或 AI 当作独有能力 |

---

## 12. 可供实施时参考的规范与工具

以下链接用于查阅正式文档、决定后续技术选型；并非声明各项技术现已在项目中实现。

- [AnnData](https://anndata.readthedocs.io/) / [MuData](https://mudata.readthedocs.io/)：组学矩阵与多模态数据模型。
- [Apache Parquet](https://parquet.apache.org/)：列式结构化数据存储。
- [JSON Schema](https://json-schema.org/) / [Pydantic](https://docs.pydantic.dev/)：交换数据的校验规则。
- [RO-Crate](https://www.researchobject.org/ro-crate/) / [W3C PROV-O](https://www.w3.org/TR/prov-o/)：研究对象打包与来源追踪。
- [Biolink Model](https://biolink.github.io/biolink-model/)：生物医学实体与关系的类别体系。
- [UCUM](https://ucum.org/)：机器可读的计量单位代码。
- [Metabolomics Standards Initiative 报告标准（Sumner et al., 2007）](https://doi.org/10.1007/s11306-007-0082-2)：代谢物鉴定等级。
- [Reactome](https://reactome.org/) / [Open Targets Platform](https://platform.opentargets.org/)：通路与靶点关联证据。
- [ChEMBL](https://www.ebi.ac.uk/chembl/) / [DrugBank](https://go.drugbank.com/)：生物活性分子与已获批药物。
- [UniProt](https://www.uniprot.org/) / [Human Protein Atlas](https://www.proteinatlas.org/) / [GTEx](https://gtexportal.org/)：蛋白注释与组织表达。
- [IMPC](https://www.mousephenotype.org/) / [MGI](https://www.informatics.jax.org/)：小鼠表型。
- [Ensembl Compara](https://www.ensembl.org/info/genome/compara/index.html) / [HGNC HCOP](https://www.genenames.org/tools/hcop/)：同源基因映射。
- [RDKit](https://www.rdkit.org/) / [DeepChem](https://deepchem.io/) / [Therapeutics Data Commons](https://tdcommons.ai/)：化学信息学、机器学习与药物发现基准。
- [CHOPCHOP](https://chopchop.cbu.uib.no/)：基因编辑相关分析工具。
- [TheraWeave 设计评审与首版实施规格](theraweave_design_review.md)：本次核对的官方文档与原始研究见第 12 节，涵盖遗传方向、共定位、通量调节、assay 语义、实验设计与格式校验。
- [Schrödinger 与本项目的生态比较](schrodinger_ecosystem_comparison.md)：截至 2026-10-30 的公开定位、实际重叠、差异化要求、相关工具对照与拟议的 T2 对接方式。
