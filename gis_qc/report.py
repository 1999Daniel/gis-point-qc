"""生成无需外部资源的 HTML 报告及安全的 CSV 问题清单。"""
import csv
import html
import io

ISSUE_COLUMNS = ("row", "id", "field", "code", "severity", "value", "message", "suggestion")
ISSUE_LABELS = ("原始行号", "编号", "字段", "规则代码", "严重程度", "原始值", "问题说明", "修改建议")


def _e(value):
    return html.escape(str(value), quote=True)


def _safe_csv(value):
    text = str(value)
    # 兼顾首部空白、制表符与其他控制字符，防止表格软件解释公式。
    start = 0
    while start < len(text) and (text[start].isspace() or ord(text[start]) < 32 or text[start] == "\ufeff"):
        start += 1
    probe = text[start:]
    if probe.startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def export_csv(result) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(ISSUE_LABELS)
    for issue in result["issues"]:
        writer.writerow([_safe_csv(issue.get(key, "")) for key in ISSUE_COLUMNS])
    return buffer.getvalue().encode("utf-8-sig")


def build_report(result) -> str:
    summary = result["summary"]
    cards = "".join(f'<div class="card"><strong>{_e(summary[key])}</strong><span>{label}</span></div>' for key, label in (
        ("total_rows", "数据记录数"), ("affected_rows", "涉及记录"), ("error_count", "错误"), ("warning_count", "提示")))
    body = "".join("<tr>" + "".join(f"<td>{_e(issue.get(key, ''))}</td>" for key in ISSUE_COLUMNS) + "</tr>" for issue in result["issues"])
    if not body:
        body = '<tr><td colspan="8">本次配置的规则未发现问题。请结合下方检查边界理解结果。</td></tr>'
    rules = "".join(f"<li><code>{_e(rule['code'])}</code> · {_e(rule['title'])}：{_e(summary['by_rule'].get(rule['code'], 0))} 项</li>" for rule in result["rules"])
    notes = "".join(f"<li>{_e(note)}</li>" for note in result["notes"])
    headings = "".join(f"<th>{label}</th>" for label in ISSUE_LABELS)
    demo = "模拟样例 · 不代表真实业务数据" if result.get("is_demo") else "用户文件 · 原始文件未被改写"
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GIS 点位质检报告</title>
<style>body{{margin:0;background:#f3f6f8;color:#182b38;font:15px/1.7 system-ui,"Microsoft YaHei",sans-serif}}main{{max-width:1200px;margin:auto;padding:36px 24px}}h1{{font-size:30px;margin:8px 0}}h2{{font-size:20px;margin-top:32px}}.kicker{{color:#177e83;font-weight:700}}.muted{{color:#62727b}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:24px 0}}.card{{background:white;border:1px solid #d9e4e8;border-radius:12px;padding:18px}}.card strong{{display:block;font-size:30px}}.card span{{color:#62727b}}.status{{display:inline-block;padding:4px 14px;border-radius:20px;background:#dceef0;font-weight:700}}.panel{{background:white;border-radius:12px;padding:20px;border:1px solid #d9e4e8}}.table-wrap{{overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:13px}}td,th{{padding:11px;text-align:left;vertical-align:top;border-bottom:1px solid #e3ebef;overflow-wrap:anywhere;min-width:65px}}th{{background:#eaf1f4}}td{{white-space:pre-wrap}}dl{{display:grid;grid-template-columns:110px 1fr;gap:8px}}dt{{color:#62727b}}dd{{margin:0;overflow-wrap:anywhere}}code{{font-family:Consolas,monospace}}@media(max-width:650px){{.cards{{grid-template-columns:repeat(2,1fr)}}main{{padding:20px 12px}}dl{{grid-template-columns:1fr}}}}@media print{{body{{background:white}}main{{max-width:none;padding:0}}.table-wrap{{overflow:visible}}table{{font-size:10px}}td,th{{min-width:0;padding:5px}}}}</style></head>
<body><main><div class="kicker">GIS · 点位数据质量检查</div><h1>点位质检报告</h1><p class="muted">{_e(demo)}</p><span class="status">{_e(summary['status'])}</span>
<div class="cards">{cards}</div><section class="panel"><dl><dt>源文件</dt><dd>{_e(result['filename'])}</dd><dt>生成时间</dt><dd>{_e(result['generated_at'])}</dd><dt>声明坐标系</dt><dd>{_e(result['crs'])} · 十进制度</dd><dt>类别白名单</dt><dd>{_e('、'.join(result.get('allowed_categories', [])))}</dd><dt>空白记录</dt><dd>忽略 {_e(summary['ignored_blank_rows'])} 条</dd><dt>问题总数</dt><dd>{_e(summary['issue_count'])}</dd><dt>原文件 SHA-256</dt><dd><code>{_e(result['sha256'])}</code></dd></dl></section>
<h2>完整问题清单</h2><div class="panel table-wrap"><table><thead><tr>{headings}</tr></thead><tbody>{body}</tbody></table></div>
<h2>检查规则与计数</h2><div class="panel"><ul>{rules}</ul></div><h2>检查边界与处理说明</h2><div class="panel"><ul>{notes}</ul><p>本报告仅反映配置规则的检查结果。真实位置及空间精度未核验；坐标参考系未鉴定；未自动修正任何原始数据。</p></div><p class="muted">报告版本 {_e(result['schema_version'])} · CSV 导出对可能触发公式的文本增加前置单引号，保留其可见内容。</p></main></body></html>'''
