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

## 处理流程

1. **结构识别**（任务完成度）：按中英文标题把稿件映射到 abstract/introduction/methods/results/discussion/conclusion/references；缺失章节记为问题。
2. **摘要—结论一致性**（正确性）：比较两段的核心词项重叠，低于 0.2 提示结论未回应摘要主张。
3. **数值一致性**（正确性）：抽取摘要中的数值，检查是否出现在引言/结果/讨论；未出现的逐个定位。
4. **引用完整性**（正确性）：解析 `[n]` 与区间标记，检查越界标记与未被引用的参考条目；无参考文献列表时标为不可核验。
5. **证据支撑**（完整性）：在讨论/结论中查找 `prove`/`显著` 等强断言，若同句无引用且无 hedge，标为需补证据或降强度。
6. **方法报告**（完整性）：检查样本量、统计与对照是否在方法中出现，缺项给修改建议；逐条严重度分级并生成修改清单。

## 输出契约

顶层：`case_id`、`status`、`result`、`checks`、`review_report`、`evidence`、`uncertainty`、`errors`、`stats`、`contract_notes`、`output_contract_fields`。同时写出 `review-report.md`（可直接交付的质量与结构审查报告）。

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


## 交付要求

- 运行：`python scripts/run_skill.py --case /input/case.json --out /app/output/result.json`（`--output` 等价）。
- 单次运行产出完整成品：`result.json`（契约字段齐全）与 `review-report.md`（可直接复核的质量与结构审查报告）。
- 每个问题附定位、原文、判定、依据与修改建议；覆盖输入中的全部章节与条目，不静默跳过。
- 输入缺失、JSON 损坏或输出不可写时，仍写出结构化 `result.json` 并正常退出；未检查项写入 `uncertainty` / `limitations`，不伪造内容。
- 结果由输入驱动，保持确定性（同一输入双跑字节一致）；不联网、不声称平台评分。
