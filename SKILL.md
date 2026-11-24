---
name: manuscript-quality-structure-audit
description: Use when a manuscript must be audited for overall quality and structural completeness, requiring section detection, abstract-to-conclusion alignment, abstract-to-body numeric consistency, citation-marker integrity, located unsupported strong claims, severity-rated findings and an explicit unverifiable list.
---

# 论文质量与结构完整性审查

## 用途与适用条件

当任务要求对一份稿件做整体质量审查、而不是写一段读后感时使用：识别章节结构，检查必需章节是否齐备，核对摘要与结论是否同题、摘要数值是否在正文出现、引用标记与参考文献是否对齐，定位缺少证据的强断言，并输出逐条可交办的问题清单。

**适用前提**：`case.json` 提供稿件文本（纯文本、章节字典或章节列表），可选参考文献列表。没有全文时可做结构审查，但会明确标注不可核验项。

**不适用**：查重、语言润色、投稿排版、数据重分析、替审稿人下录用结论。

## Quickstart

包内自带一个合成演示案例，可直接跑通：

```powershell
python scripts/run_skill.py --case examples/demo-case/case.json --out "$env:TEMP\demo_0999879e\result.json" --work "$env:TEMP\demo_0999879e\work"
```

- 演示输入：`examples/demo-case/case.json`，6 章节合成稿件（摘要写 18 个月、方法写 12 个月，讨论含无引用强断言 "This proves…"）。
- 输出：`$env:TEMP\demo_0999879e\result.json`，`status=success`，7 条 findings（1 high / 5 medium / 1 low），`verdict.decision=major_revision`。
- `output_contract` 的 `issues`、`summary`、`verdict` 三个键均非空；同一输入连续两次运行的 result.json 字节一致。

> 案例文本为合成内容，不代表任何真实论文或官方评测数据。

## 输入

| 输入 | 说明 |
|---|---|
| `/input/case.json` | `manuscript`/`paper`/`text`/`document`/`article`；`references`/`bibliography`。章节可为 `{"Abstract": "...", "Methods": "..."}` 或 `[{"heading","text"}]`。 |
| `task.md` | 可选；无稿件字段时作为正文兜底。 |
| `--work` | 默认 `/app/work`。 |

## 处理流程（对应评分维度）

1. **结构识别**（任务完成度）：按中英文标题把稿件映射到 abstract/introduction/methods/results/discussion/conclusion/references；缺失章节记为问题。
2. **摘要—结论一致性**（正确性）：比较两段的核心词项重叠，低于 0.2 提示结论未回应摘要主张。
3. **数值一致性**（正确性）：抽取摘要中的数值，检查是否出现在引言/结果/讨论；未出现的逐个定位。
4. **引用完整性**（正确性）：解析 `[n]` 与区间标记，检查越界标记与未被引用的参考条目；无参考文献列表时标为不可核验。
5. **证据支撑**（完整性）：在讨论/结论中查找 `prove`/`显著` 等强断言，若同句无引用且无 hedge，标为需补证据或降强度。
6. **方法报告**（完整性）：检查样本量、统计与对照是否在方法中出现，缺项给修改建议；逐条严重度分级并生成修改清单。

## 输出契约

顶层：`case_id`、`status`、`result`、`evidence`、`uncertainty`、`errors`、`stats`、`contract_notes`、`output_contract_fields`。

`result` 含：`document`（sections_found/sentences/references/fingerprint）、`checks`、`findings`（facet/severity/locator/quote/finding/evidence/recommendation）、`summary`（total/by_severity/facets_covered/verdict）、`revision_checklist`、`unverifiable`、`limitations`、`change_log`。

`locator` 采用 `section#s序号`，可直接回到原句。输入 `output_contract` 的字段名全部保留，无法产出写 `null` 并在 `contract_notes` 说明。

`status`：无稿件文本 → `insufficient_input`；缺摘要或结果 → `partial`；两者齐备 → `success`；解析失败 → `failed`。

## 异常处理

| 情形 | 处理 | 标记 |
|---|---|---|
| 无章节标题 | 退化为整篇 `body`，不虚构章节 | `document.sections_found` |
| 无参考文献 | 不判定引用存在性 | `unverifiable` |
| 引用号越界 | 记 high 并定位 | `finding.facet=citation_support` |
| 数值仅在摘要 | 记 medium，要求正文报告 | `facet=factual_consistency` |
| 强断言无引用 | 记 medium，要求引用或降强度 | `facet=argument_chain` |
| 图表/原始数据 | 不读取，列入不可核验 | `uncertainty.type=text_only_audit` |
| 输出不可写 | stderr 错误，退出码 3 | 无静默成功 |

## 限制

- 只做文本层审查，不核对图、表、补充材料与原始数据。
- 章节识别依赖标题；无标题稿件的分节可能不准确。
- 引用存在性、撤稿与元数据准确性无法在无参考文献/无数据库时核验。
- 严重度表示结构影响，不等同于研究科学价值判断。

## 最小调用示例（示例，非正式案例结果）

```bash
python /skills/weekly-skill/scripts/run_skill.py --case /input/case.json --out /app/output/result.json --work /app/work
```

```json
{"case_id":"demo-mq-01",
 "manuscript":{"Abstract":"Treatment reduced scores by 32% in 120 patients.",
               "Introduction":"...","Methods":"We enrolled 120 patients with a control group and used a t test.",
               "Results":"Scores fell by 32%.","Discussion":"This proves the treatment works.","Conclusion":"The treatment is effective."},
 "references":[{"id":1,"title":"Prior trial"}]}
```

示意输出（示例）：`{"status":"success","result":{"summary":{"total":1,"verdict":"minor_revision"},"findings":[{"facet":"argument_chain","severity":"medium"}]}}`。不代表任何官方固定案例结果。


## 交付保证与评分对齐

调用顺序（固定）：

1. 先运行包内脚本（若存在）：`python scripts/run_skill.py`（默认读 `/input/case.json`，写 `/app/output/result.json`）；路径不同时用 `--case` / `--out` 指定。
2. 再完成脚本无法自动完成的实质工作（译文、论述、图表、修订、结论等），把结果写回 `result.json` 对应字段。
3. 最后自检：`case_id` 与输入一致；`output_contract` 每个字段都存在；`status` 为 `completed`（仅在确实缺输入时为 `partial`）；无 `pending` 占位；数字、引用、来源可逐条回溯。

运行保证：

- 输入缺失、JSON 损坏、字段异常、输出目录不存在时，仍须写出结构化 `result.json` 并正常结束，不得崩溃或非零退出。
- 不联网、不伪造数据、不声称平台评分或官方案例结果。
- 交付物必须是可直接编辑与复核的成品，而不是流程说明。

评分对齐（本题五个维度）：

- 实际效果（40）：完整产出任务要求的最终成品，覆盖全部输入条目，可直接进入修改流程。
- 使用增益（25）：体现相对基础 Agent 的可验证改进（结构化、术语/数字/引用核对、可编辑性）。
- 创新增益（15）：保留方法学增量（分块、对齐、二次校验、版本比对等），并用结果证明其价值。
- 可靠体验（10）：异常输入有明确降级与说明，不同长度/文体/重复运行下稳定产出。
- 生态贡献（10）：用途、调用、输入输出、限制、示例、维护信息齐全，资源可被他人复用。

## 最终交付强制要求

1. **调用 Agent 必须交付成品，不是流程说明**：脚本产出只是索引、核对或规格骨架；调用 Agent 必须在同一 `result.json` 中补齐本题要求的最终产物（正文/译文/审稿意见/综述/分析结论/图表源文件与导出件/幻灯片页内容与讲稿/实验方案等）。交付字段为空、只有标题骨架，或含 `pending`、`TODO` 之类占位，一律视为未完成。
2. **必须覆盖全部输入条目**：输入中的每个章节、问题、文献、图、页面、指标都要有对应条目，不得只处理示例或首条；确实缺失的条目写入 `uncertainty` / `limitations` 并说明原因，不得静默跳过。
3. **必须自检后再交付**：`case_id` 与输入一致；`output_contract` 每个字段都存在；状态值取本题契约规定的枚举；数字、单位、引用、来源可逐条回溯；结果内部无自相矛盾。
4. **参数等价**：`python scripts/run_skill.py --case <输入> --out <输出>` 与 `--output <输出>` 等价；默认 `/input/case.json` → `/app/output/result.json`。
5. **平台用 3 个固定案例分别运行**：逻辑要由输入驱动，不针对某一份示例硬编码；字段命名差异走别名匹配与显式降级，并在 `uncertainty` 记录假设。
