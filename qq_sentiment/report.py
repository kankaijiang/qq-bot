"""Report generator — produces plain-text and HTML sentiment reports."""

import os
import logging
from datetime import datetime, timezone, timedelta

from .sentiment import GroupReport, Sentiment

logger = logging.getLogger(__name__)

# Beijing time
_CST = timezone(timedelta(hours=8))


def _ts_to_str(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=_CST).strftime("%Y-%m-%d %H:%M:%S")


def _sentiment_bar(pos: int, neu: int, neg: int, width: int = 40) -> str:
    """ASCII bar chart showing sentiment distribution."""
    total = pos + neu + neg
    if total == 0:
        return "[" + " " * width + "]"
    p = round(pos / total * width)
    ne = round(neg / total * width)
    nu = width - p - ne
    return "[" + "+" * p + "=" * nu + "-" * ne + "]"


# ──────────────────────────────────────────────────────────────────
# Plain-text report
# ──────────────────────────────────────────────────────────────────

def generate_text_report(report: GroupReport) -> str:
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append(f"  QQ 群舆情分析报告  —  群号: {report.group_id}")
    lines.append("=" * 60)
    lines.append(f"时间范围: {_ts_to_str(report.start_ts)} ~ {_ts_to_str(report.end_ts)}")
    lines.append(f"消息总数: {report.total_messages}")
    lines.append("")

    # Sentiment distribution
    lines.append("【情感分布】")
    lines.append(f"  正面: {report.positive_count}  "
                 f"中性: {report.neutral_count}  "
                 f"负面: {report.negative_count}")
    lines.append(f"  平均情感分: {report.avg_score:.4f}  (0=极负面, 1=极正面)")
    lines.append(f"  {_sentiment_bar(report.positive_count, report.neutral_count, report.negative_count)}")
    lines.append("")

    # Alert
    if report.alert:
        lines.append("⚠ 舆情预警: 负面消息占比过高或触发关键词告警")
        lines.append("")

    # Keyword hits
    if report.keyword_hits:
        lines.append("【关键词命中】")
        for kw, cnt in sorted(report.keyword_hits.items(), key=lambda x: -x[1]):
            lines.append(f"  「{kw}」 × {cnt}")
        lines.append("")

    # Top negative
    if report.top_negative:
        lines.append("【负面消息 TOP 5】")
        for i, r in enumerate(report.top_negative, 1):
            lines.append(f"  {i}. [{r.score:.2f}] {r.message.nickname}: "
                         f"{r.message.text[:80]}")
        lines.append("")

    # Top positive
    if report.top_positive:
        lines.append("【正面消息 TOP 5】")
        for i, r in enumerate(report.top_positive, 1):
            lines.append(f"  {i}. [{r.score:.2f}] {r.message.nickname}: "
                         f"{r.message.text[:80]}")
        lines.append("")

    lines.append(f"报告生成时间: {datetime.now(tz=_CST).strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 60)
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────
# HTML report
# ──────────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>QQ 群舆情报告 - {group_id}</title>
<style>
  body {{ font-family: "PingFang SC","Microsoft YaHei",sans-serif; margin: 2em; background: #f5f5f5; }}
  .card {{ background: #fff; border-radius: 8px; padding: 1.5em; margin-bottom: 1.5em; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
  h1 {{ color: #333; }}
  .alert {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 1em; margin-bottom: 1em; }}
  .bar {{ display: flex; height: 24px; border-radius: 4px; overflow: hidden; margin: .5em 0; }}
  .bar-pos {{ background: #4caf50; }}
  .bar-neu {{ background: #9e9e9e; }}
  .bar-neg {{ background: #f44336; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  th {{ background: #f0f0f0; }}
  .score {{ font-weight: bold; }}
  .neg {{ color: #d32f2f; }}
  .pos {{ color: #388e3c; }}
</style>
</head>
<body>
<h1>QQ 群舆情分析报告</h1>

<div class="card">
  <p><strong>群号:</strong> {group_id}</p>
  <p><strong>时间范围:</strong> {start} &mdash; {end}</p>
  <p><strong>消息总数:</strong> {total}</p>
  <p><strong>平均情感分:</strong> {avg_score}</p>
</div>

{alert_html}

<div class="card">
  <h2>情感分布</h2>
  <div class="bar">
    <div class="bar-pos" style="width:{pos_pct}%" title="正面 {pos_count}"></div>
    <div class="bar-neu" style="width:{neu_pct}%" title="中性 {neu_count}"></div>
    <div class="bar-neg" style="width:{neg_pct}%" title="负面 {neg_count}"></div>
  </div>
  <p>正面: {pos_count} &nbsp; 中性: {neu_count} &nbsp; 负面: {neg_count}</p>
</div>

{keywords_html}

{neg_table}

{pos_table}

<p style="color:#999;text-align:center;">报告生成于 {generated}</p>
</body>
</html>
"""


def _pct(part: int, total: int) -> str:
    return f"{part / total * 100:.1f}" if total else "0"


def _msg_table(title: str, results, css_class: str) -> str:
    if not results:
        return ""
    rows = ""
    for i, r in enumerate(results, 1):
        text = r.message.text[:120].replace("<", "&lt;").replace(">", "&gt;")
        nick = r.message.nickname.replace("<", "&lt;").replace(">", "&gt;")
        rows += (
            f"<tr><td>{i}</td>"
            f"<td class='score {css_class}'>{r.score:.2f}</td>"
            f"<td>{nick}</td>"
            f"<td>{text}</td></tr>\n"
        )
    return (
        f'<div class="card"><h2>{title}</h2>'
        f"<table><tr><th>#</th><th>分数</th><th>昵称</th><th>内容</th></tr>"
        f"{rows}</table></div>"
    )


def generate_html_report(report: GroupReport) -> str:
    total = report.total_messages or 1

    alert_html = ""
    if report.alert:
        alert_html = '<div class="alert"><strong>⚠ 舆情预警</strong>：负面消息占比过高或触发关键词告警</div>'

    keywords_html = ""
    if report.keyword_hits:
        kw_rows = "".join(
            f"<tr><td>{kw}</td><td>{cnt}</td></tr>"
            for kw, cnt in sorted(report.keyword_hits.items(), key=lambda x: -x[1])
        )
        keywords_html = (
            '<div class="card"><h2>关键词命中</h2>'
            "<table><tr><th>关键词</th><th>次数</th></tr>"
            f"{kw_rows}</table></div>"
        )

    return _HTML_TEMPLATE.format(
        group_id=report.group_id,
        start=_ts_to_str(report.start_ts),
        end=_ts_to_str(report.end_ts),
        total=report.total_messages,
        avg_score=f"{report.avg_score:.4f}",
        alert_html=alert_html,
        pos_pct=_pct(report.positive_count, total),
        neu_pct=_pct(report.neutral_count, total),
        neg_pct=_pct(report.negative_count, total),
        pos_count=report.positive_count,
        neu_count=report.neutral_count,
        neg_count=report.negative_count,
        keywords_html=keywords_html,
        neg_table=_msg_table("负面消息 TOP 5", report.top_negative, "neg"),
        pos_table=_msg_table("正面消息 TOP 5", report.top_positive, "pos"),
        generated=datetime.now(tz=_CST).strftime("%Y-%m-%d %H:%M:%S"),
    )


def save_report(report: GroupReport, output_dir: str) -> tuple[str, str]:
    """Save both text and HTML reports. Returns (text_path, html_path)."""
    os.makedirs(output_dir, exist_ok=True)
    now = datetime.now(tz=_CST).strftime("%Y%m%d_%H%M%S")
    base = f"sentiment_{report.group_id}_{now}"

    txt_path = os.path.join(output_dir, f"{base}.txt")
    html_path = os.path.join(output_dir, f"{base}.html")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(generate_text_report(report))

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(generate_html_report(report))

    logger.info("Reports saved: %s, %s", txt_path, html_path)
    return txt_path, html_path
