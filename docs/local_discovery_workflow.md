# 本地知识与实验闭环操作说明

> 软件版本：0.1.0.dev0；日期：2026-10-31。以下功能为可运行的研究预览；尚未在真实课题上完成独立科学验证。正式数据接口状态见[实施记录](implementation_status.md)。

## 1. 已实现的工作流

```text
OmicsWeave 0.1 草案结果 + 使用者上下文
  → validate / import：校验、去重与来源归档
  → knowledge-convert：本地数据库文件转换，所有新记录默认未审查
  → knowledge-validate：来源、版本、引用、上下文与记录校验
  → assess：八维证据画像、四种决策桶、来源/研究移除敏感性、描述性对照；可选同源/反应映射、遗传记录与模态条件
  → record-override：只记录更保守或同级的人工决定，不能清除阻断风险
  → plan：明确缺口与对照的计划草稿
  → review-plan：使用者填写设计与预设规则，生成独立审查版本
  → record-outcome：精确匹配计划版本的定量反馈，历史记录保留
```

整个运行流程只访问本地文件，不查询外部平台。数据库下载、许可适用性核实、原始来源科学审查仍由项目维护者或使用者完成。

## 2. 三个来源的本地转换

`knowledge-convert` 支持以下受限格式，不能把任意版本的大型数据库直接当作已经适配：

| 来源 | 接收的本地文件 | 行为与限制 |
|---|---|---|
| OpenTargets | `targetId`、`diseaseId` 等字段的 evidence 子集，Parquet、JSON 列表/`evidence` 容器或 JSONL | 明确指定 taxon；保留 score、文献、studyId 和原记录；不把 score 转成因果或方向 |
| UniProt | 单条 entry JSON 或 `results` 列表，含 primaryAccession 与 organism.taxonId | 保留蛋白身份和原记录；不按基因符号自动合并，也不自行建立基因—蛋白对应 |
| ChEMBL | `mechanisms` JSON 加 `targets` 本地响应映射 | 仅处理 SINGLE PROTEIN 且单一 component accession；缺少物种或有复合体/同源歧义时报错，需另行审查；不混排 IC50/Kd 等活性 |

转换后使用统一的 `theraweave.knowledge-snapshot` 0.1 格式。来源摘要、输入文件 SHA-256、辅助 target map 摘要和原始 payload 一并保存。自动转换的记录全部 `reviewed=false`，作用方向保持 unknown；科学审查必须明确记录 reviewer、假设上下文、引用与断言后，规则才使用相应支持。

来源格式依据：[Open Targets 数据集官方说明](https://platform-docs.opentargets.org/data-access/datasets)、[ChEMBL 官方数据服务](https://chembl.gitbook.io/chembl-interface-documentation/web-services/chembl-data-web-services)。UniProt 读取器目前按 entry/search JSON 的显式 accession/taxon 字段实现，尚未做真实 release 的往返验收。

元数据 JSON 必须包含 `release`、`retrieved_at`（日期）、`origin_url`、`license`、`synthetic`；可选 `coverage_notes`。这些是来源登记，不代表软件已替使用者完成法律许可判断。示例仅用合成数据；真实本地快照不自动进入仓库或安装包。

```powershell
python -m theraweave knowledge-convert UniProt local/uniprot-subset.json --metadata local/uniprot-metadata.json --output local/knowledge/uniprot-normalized.json
python -m theraweave knowledge-validate local/knowledge/uniprot-normalized.json
```

同一 primary_record_id 与相同断言在多个来源中出现时合并来源引用；不同解释或相反方向保留冲突。primary_study_id 用于保守的来源家族和移除敏感性，不自动宣称样本互相独立。

## 3. 候选评估规则

当前 `preview-rules-1` 是透明的工程政策：默认本研究疾病效应需有校正 p≤0.05、|log2FC|≥0.5 且各组生物学 n≥3，才满足这一条测量门槛。它不重新执行统计检验，也不声称这些阈值适合所有实验。替代政策必须显式提供完整阈值并写入产物；不能按希望得到的候选反复调参。

八维包括本研究统计、独立复现、机制、方向、细胞/组织适配、人类转化、身份/工具与风险。单一 bulk/组织标签只支持 limited 上下文，缺少样本重叠信息时独立复现保持 unknown；未知风险不变成安全。

四个决策桶为：

- `functional_validation_ready`：当前测量门槛、审查过的身份与工具线索足以设计功能实验；仍需人工审查和补齐具体实验设计。
- `evidence_gap_first`：先解决身份、测量或工具缺口。
- `conflict_resolution_first`：先处理同上下文的方向/功能冲突。
- `hold_for_review`：有该上下文内已审查的阻断风险，其他维度不能抵消。

未注释 feature、protein group、代谢物或反应不能因为统计强就直接成为已明确的基因/蛋白干预靶点。跨物种、跨命名空间或不同 context 不模糊匹配，必须提供可追溯的映射和科学审查。

报告包括逐项依据、引用、缺口、规则版本与覆盖，且有按来源及原始研究移除的敏感性记录。`baseline.json` 只是校正 p 的描述性顺序，没有标签时不计算准确率。性能基准和前瞻实验仍待真实研究数据。

## 4. 草稿、审查与反馈

`plan` 为每个候选生成草稿。计划保留未知样本量、方差、终点量纲和判定界限；列出正交扰动、可行的救援、非靶向/vehicle 和存活/应激对照。它不会自动批准动物实验或生成实际药物剂量。

`review-plan` 要求 reviewer、时间、理由、主要终点、设计说明和预先规定的判断规则。当前终点需要 name、unit、desired_direction、minimum_meaningful_effect、confidence_level；设计需要实验单位、样本量依据、随机化、盲法、比较、检验家族/多重性、排除和对照说明。阻断风险未解决时拒绝推进。

当前唯一自动反馈规则是 `benefit_ci_excludes_zero_and_point_meets_minimum`：在成功扰动与 QC 通过的前提下，所预定方向的置信区间完全位于获益侧，且点估计达到预定最小效应，才记为 supported。置信水平、终点、单位和计划版本必须完全匹配；不做隐式换算。区间不支持预定方向可记 not_supported；精度不足、扰动失败或 QC 失败均记 inconclusive。这些状态限定于该计划和模型，不能全局否证整个靶点。该规则不是临床有效性标准，也不替代科学审查。

反馈 JSON 的必要字段为 plan_id、plan_version、endpoint_name、unit、effect、ci_lower、ci_upper、confidence_level、target_engagement_confirmed、qc_passed、observed_by、source_analysis 和 execution_deviations。当前接收的是外部汇总统计，不在反馈模块内重算原始实验结果。

审查后可生成 OmicsWeave 草稿目录，包含 project.yaml、experiment.yaml 和空 subject/sample 表。它仅保存计划/假设关联；没有实际样本、组学输入与比较配置，保持 DRAFT。Schema 形状正确也不能声称通过了完整 `omicsweave validate`。

## 5. 运行完整合成演示

```powershell
python tools/run_preview_demo.py local/new-full-preview
```

它使用虚构基因、知识、审查人与结果完成完整流程，输出 import、assessment、plans、reviewed、feedback 和 demo-summary.json；目标目录须不存在。合成知识只允许用于显式标为 synthetic 的输入包，不能被带入实际课题给出支持。

## 6. 同源映射、反应映射、模态条件与人工覆盖

这些输入都是本地文件，默认不访问网络。合成映射只能用于明确标为 synthetic 的结果包。

同源映射使用 `theraweave.ortholog-map` 0.1。它必须已经审查，来源物种固定为小鼠 10090，同源条目固定为人 9606。`one2one` 恰好一条，`one2many` 或 `many2many` 至少两条并全部保留，`none` 表示审查后确认无人类同源；实体不会因此被删除。未提供映射时，人类转化保持未知。映射只改变“已有审查过的对应关系”这一状态，功能、药理和疾病机制是否守恒仍是缺口。人类同源上的另一条方向记录不会写回小鼠实体。

反应映射使用 `theraweave.reaction-map` 0.1，并且 `flux_control` 只能是 `mapping_only`。`OR` 至少两个组分，表示同工酶或替代酶，不表示每个酶都应抑制。`AND` 表示记录到的组分共同参与。跨器官反应会保留标记，不指定某一个组织内的酶。通量观察只挂在反应上，不复制到每个组分，也不把通量增减解释成干预方向。

模态筛查读取已审查的身份定位、蛋白类别，以及工具记录上的模态和机制。类别会写入依据，但本身不分配模态。胞内定位会使抗体和多肽的可及性条件失败；没有审查过的定位则保持未知，器官表达不能代替递送。siRNA 的敲低记录不会满足 ASO 的剪接调节。方向为抑制时，mRNA 和基因补充不会被当成匹配方案。DNA 编辑始终只是方法条件，不会因为表达符号而成为开放工具。本版只有小分子可以在方向与已审查机制对齐时留下 `open_research_probe`，选择性和暴露仍列入未决问题。抗体、多肽、siRNA、ASO、mRNA、基因补充和 DNA 编辑即使已有工具记录，也会因递送、持久性或机制细节未决而保持 `pending_conditions`，不会被记成开放工具。

`record-override` 生成新的评估归档和 `decision_log.json`。请求的分桶不能比算法分桶或当前分桶更宽松。`hold_for_review` 之后的计划审查仍会拒绝，直到新的评估解除阻断风险。

```powershell
python -m theraweave assess local/my-report --ortholog-map local/orthologs.json --reaction-map local/reactions.json --output local/my-assessment
python -m theraweave record-override local/my-assessment --override local/override.json --output local/my-decision
```

覆盖文件只含 `hypothesis_id`、`operator`、`overridden_at`、`rationale`、`requested_bucket` 和 `evidence_ids`。`evidence_ids` 必须来自该假设已有的观察或知识记录。

## 7. 符号线索、遗传记录和描述性对照

同一实体在疾病效应和治疗效应中符号相反时，评估记为 `opposite_direction`。符号相同、缺失或互相冲突会分别记为 `same_direction`、`not_assessed` 或 `discordant`。这只保留线索：不设置 `intervention_direction`，也不表示恢复正常或因果逆转。

遗传记录使用 `theraweave.genetic-evidence` 0.1，通过 `assess --genetic-evidence` 读入。文件和每条被采用的记录都要经过审查，并且必须对应已经导入的实体。使用规则是：

| 方法 | 采用方式 |
|---|---|
| 映射依据为最近基因，或方法是 GWAS 关联 | 只保留记录。最近基因不是因果靶点，也不提供方向 |
| 共定位 | 只表示共享信号，不证明表达介导疾病，不提供方向 |
| 精细定位且依据是 credible set | 可以标记身份线索，不提供方向，也不代替蛋白身份审查 |
| MR | 只有等位基因方向明确，并且局限说明同时包含工具强度、水平多效性、样本重叠和方向性时才参与方向；这仍不是功能证明 |
| 功能变异 | 编码变异、功能测定或审查后的人工依据可以参与方向；与已有方向冲突时进入冲突分桶。它不代替本研究模型里的扰动 |

`comparisons.json` 给出校正 p 顺序、绝对效应顺序、完整规则、每个知识来源单独使用、去掉全部外部知识，以及在存在 MFA 观察时去掉 MFA 的结果。`accuracy`、`labels` 和 `ranked_winner` 保持为空。分桶变化只说明输入变了，不说明哪种方案更接近真实靶点。没有 MFA 观察时，去掉 MFA 的状态是 `not_applicable`。

```powershell
python -m theraweave assess local/my-report --genetic-evidence local/genetic.json --output local/my-assessment
```

## 8. 候选清单、实验成本和外部计算交接

`screen-candidates` 接收 `theraweave.candidate-list` 0.1。清单需要研究目标、筛选规则、物种和候选标识，不能附带 p 值或效应量。输出分桶固定为 `knowledge_gap_review`。已审查且上下文相符的方向可以显示，但不会变成统计评估或完整排序。

计划审查新增 `effort`：`decision_to_change`、`cost_level`、`duration_level`、`laboratory_capability` 和 `basis`。成本只用 `not_recorded`、`low`、`moderate`、`high`，周期只用 `not_recorded`、`days`、`weeks`、`months`。`execution_ready`、`computed_sample_size` 和 `information_gain` 保持空或 false，`claims_reduced_experiment_count` 为 false。

`prepare-external-request` 把已经审查的请求写成新归档，状态是 `prepared_not_executed`。任务类型只接受 docking、fep_absolute、fep_relative、md、structure_preparation、antibody_model。允许的结论只到结合假设、结构相容、构象假设或工具线索。`network_authorized` 和 `executes_backend` 必须为 false。构建体必须仍是原假设实体；改用同源时，目标必须已经出现在该评估的人类同源列表中。

`record-external-result` 要求请求编号和假设版本完全一致。对接分数、绝对自由能和相对自由能不能互换。完成的分子动力学需要采样说明，其时间序列不是生物学重复。失败或不确定的运行不能带可用数值。结果层级固定为 `predicted`，`independent_support_added` 为 0，也不填补功能缺口。

```powershell
python -m theraweave screen-candidates local/candidates.json --output local/candidate-screen
python -m theraweave prepare-external-request local/my-assessment --request local/request.json --output local/external-request
python -m theraweave record-external-result local/external-request --result local/result.json --output local/external-result
```

## 9. 当前真实课题准备情况

项目负责人已指定首发的代谢病研究课题；课题标识和具体研究信息保存在 git 忽略的本地工作区，没有作为公开数据库样例。当前尚无结果包，因此完成的是研究问题、比较目标、已确认给药记录和缺失项整理；不能据此产生真实靶点排名或验证结论。
