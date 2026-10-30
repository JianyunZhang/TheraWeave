"""Offline HTML built from the same records written to Parquet."""
from __future__ import annotations

from html import escape


def render_report(context: dict, manifest: dict, evidence: list[dict], entities: list[dict], validation: dict) -> str:
    def cell(value):
        return escape("未知 / 未提供" if value is None else str(value))

    rows = "".join(
        "<tr>" + "".join(f"<td>{cell(row[k])}</td>" for k in (
            "feature_id", "omics", "sample_tissue", "contrast_id", "log2fc", "padj",
            "n_numerator", "n_denominator", "intervention_direction")) + "</tr>"
        for row in evidence
    )
    diagnostics = "".join(f"<li><strong>{cell(d['rule_id'])}</strong> · {cell(d['file'])}: {cell(d['message'])}</li>"
                          for d in validation["diagnostics"])
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>TheraWeave 证据导入档案</title>
<style>body{{font:16px/1.65 system-ui,sans-serif;color:#18332f;background:#f5f7f6;margin:0}}
main{{max-width:1200px;margin:auto;padding:40px 24px}}h1{{font-size:32px}}h2{{margin-top:32px}}
.note{{background:#fff5da;border-left:4px solid #ba8520;padding:16px}}
.stats{{display:flex;gap:28px;flex-wrap:wrap;background:white;padding:20px}}
table{{width:100%;border-collapse:collapse;background:white;font-size:14px}}th,td{{border-bottom:1px solid #ddd;padding:10px;text-align:left}}
.scroll{{overflow:auto}}a{{color:#126953}}code{{overflow-wrap:anywhere}}li{{margin:10px 0}}</style>
</head><body><main><p>THERAWEAVE · IMPORT PREVIEW</p><h1>证据导入档案</h1>
<p class="note">当前为 OmicsWeave 0.1 草案兼容预览。该报告整理统计观察与来源，尚未进行靶点排序、因果判断、治疗方向或安全性评估。</p>
<div class="stats"><span>实体 <strong>{len(entities)}</strong></span><span>去重后观察 <strong>{len(evidence)}</strong></span>
<span>合并重复记录 <strong>{validation['duplicate_rows']}</strong></span><span>独立复现次数 <strong>未知</strong></span></div>
<h2>研究上下文</h2><p>疾病/表型：{cell(context['disease_or_phenotype'])}<br>
主要终点：{cell(context['primary_endpoint'])}<br>物种 taxon：{cell(context['source_taxon_id'])}<br>
实验单位：{cell(context.get('experimental_unit'))}<br>上游运行：<code>{cell(manifest['run_id'])}</code></p>
<p>上下文由使用者声明；身份映射尚未经外部知识校验。同一实验的多组学共享依赖组，不能作为多次独立复现。p 值不直接生成支持/反对或治疗方向。</p>
<h2>统计观察</h2><div class="scroll"><table><thead><tr>
<th>实体 ID</th><th>组学</th><th>取样组织</th><th>比较</th><th>log2FC</th><th>校正 p</th><th>分子组 n</th><th>分母组 n</th><th>干预方向</th>
</tr></thead><tbody>{rows or '<tr><td colspan="9">输入有效，但没有统计观察。</td></tr>'}</tbody></table></div>
<h2>质量、缺口与限制</h2><ul>{diagnostics}</ul>
<h2>可检查产物</h2><p><a href="evidence_inventory.parquet">证据表</a> · <a href="entity_inventory.parquet">实体表</a> ·
<a href="validation_report.json">校验报告</a> · <a href="context.json">研究上下文</a> · <a href="manifest.json">运行清单</a></p>
<p>原始输入副本保存在 source_bundle，原始行值与行号保存在证据表。后续需要补充对比设计、样本重叠、身份映射、外部机制及功能验证资料。</p>
</main></body></html>"""
