from datetime import date

# ── Enum 값 안전 추출 헬퍼 ─────────────────────────────────────────────────────
def _str_val(v: object) -> str:
    """Enum이든 str이든 순수 값 문자열만 반환. 'AnomalyType.LOW_STOCK' 방지."""
    if v is None:
        return ""
    if hasattr(v, "value"):      # Enum
        return str(v.value)
    return str(v)

# ── 매핑 테이블 ──────────────────────────────────────────────────────────────
RISK_COLOR = {
    "LOW":      "#16a34a",
    "MEDIUM":   "#d97706",
    "HIGH":     "#ea580c",
    "CRITICAL": "#dc2626",
}
RISK_BG = {
    "LOW":      "#dcfce7",
    "MEDIUM":   "#fef3c7",
    "HIGH":     "#ffedd5",
    "CRITICAL": "#fee2e2",
}

ANOMALY_TYPE_KOR = {
    "LOW_STOCK":       "재고 부족",
    "OVER_STOCK":      "재고 과잉",
    "LONG_TERM_STOCK": "장기 재고",
    "SALES_SURGE":     "판매 급등",
    "SALES_DROP":      "판매 급락",
}

SEVERITY_KOR = {
    "LOW":      "낮음",
    "MEDIUM":   "보통",
    "HIGH":     "높음",
    "CRITICAL": "긴급",
    "CHECK":    "확인",
}

SEVERITY_BADGE_STYLE = {
    "CRITICAL": "background:#fee2e2;color:#dc2626;font-weight:bold;",
    "HIGH":     "background:#ffedd5;color:#ea580c;font-weight:bold;",
    "MEDIUM":   "background:#fef3c7;color:#d97706;",
    "LOW":      "background:#dcfce7;color:#16a34a;",
    "CHECK":    "background:#e0f2fe;color:#0284c7;",
}


def _severity_badge(raw: object) -> str:
    key = _str_val(raw).upper()
    label = SEVERITY_KOR.get(key, key)
    style = SEVERITY_BADGE_STYLE.get(key, "background:#f3f4f6;color:#374151;")
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:9999px;'
        f'font-size:11px;{style}">{label}</span>'
    )


def _anomaly_type_label(raw: object) -> str:
    key = _str_val(raw).upper()
    return ANOMALY_TYPE_KOR.get(key, key)


def build_daily_report_html(
        report_date: date,
        total_products: int,
        stock_anomalies: list[dict],
        sales_anomalies: list[dict],
        insight: dict,
) -> str:

    risk_key   = _str_val(insight.get("risk_level", "MEDIUM")).upper()
    risk_color = RISK_COLOR.get(risk_key, "#d97706")
    risk_bg    = RISK_BG.get(risk_key, "#fef3c7")
    risk_label = SEVERITY_KOR.get(risk_key, risk_key)

    # ── 핵심 이슈 / 권고사항 ──────────────────────────────────────────────────
    issues_html = "".join(
        f"<li>{i}</li>" for i in insight.get("key_issues", [])
    )
    recs_html = "".join(
        f"<li>{r}</li>" for r in insight.get("recommendations", [])
    )

    # ── 재고 이상 테이블 행 ───────────────────────────────────────────────────
    stock_rows = ""
    for a in stock_anomalies:
        atype    = _anomaly_type_label(a.get("anomaly_type", ""))
        days_raw = a.get("days_until_stockout", "")
        try:
            days_f   = float(days_raw) if days_raw not in ("", None) else None
        except (ValueError, TypeError):
            days_f = None
        days_str = f"{days_f:.1f}일" if days_f is not None and days_f < 999 else "-"

        stock_rows += f"""
        <tr>
          <td style="white-space:nowrap">{a.get('product_code', '')}</td>
          <td>{a.get('product_name', '')}</td>
          <td style="white-space:nowrap">{atype}</td>
          <td style="text-align:right">{a.get('current_stock', '-')}</td>
          <td style="text-align:right;white-space:nowrap">{days_str}</td>
          <td style="text-align:center">{_severity_badge(a.get('severity', ''))}</td>
        </tr>"""

    # ── 판매 이상 테이블 행 ───────────────────────────────────────────────────
    sales_rows = ""
    for a in sales_anomalies:
        atype    = _anomaly_type_label(a.get("anomaly_type", ""))
        rate     = a.get("change_rate", 0)
        try:
            rate_f   = float(rate)
            rate_str = f"+{rate_f:.1f}%" if rate_f > 0 else f"{rate_f:.1f}%"
            rate_color = "#dc2626" if rate_f > 0 else "#2563eb"
        except (ValueError, TypeError):
            rate_str   = str(rate)
            rate_color = "#374151"

        sentiment = ""
        raw_sent  = a.get("sentiment")
        if isinstance(raw_sent, dict):
            sentiment = raw_sent.get("label", "")
        elif isinstance(raw_sent, str):
            sentiment = raw_sent

        sales_rows += f"""
        <tr>
          <td style="white-space:nowrap">{a.get('product_code', '')}</td>
          <td>{a.get('product_name', '')}</td>
          <td style="white-space:nowrap">{atype}</td>
          <td style="text-align:right;color:{rate_color};font-weight:bold">{rate_str}</td>
          <td style="text-align:center">{sentiment}</td>
          <td style="text-align:center">{_severity_badge(a.get('severity', ''))}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"/>
<style>
  @page {{ margin: 18mm 16mm; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Malgun Gothic", "Apple SD Gothic Neo", "NanumGothic", sans-serif;
    font-size: 12px;
    color: #1e293b;
    line-height: 1.6;
  }}

  /* ── 헤더 영역 ── */
  .report-header {{
    border-bottom: 3px solid #1e40af;
    padding-bottom: 12px;
    margin-bottom: 20px;
  }}
  .report-title {{
    font-size: 20px;
    font-weight: bold;
    color: #1e40af;
    margin-bottom: 4px;
  }}
  .report-meta {{
    font-size: 11px;
    color: #64748b;
  }}
  .risk-badge {{
    display: inline-block;
    padding: 2px 12px;
    border-radius: 9999px;
    font-size: 12px;
    font-weight: bold;
    background: {risk_bg};
    color: {risk_color};
    border: 1px solid {risk_color};
  }}

  /* ── KPI 카드 ── */
  .kpi-grid {{
    display: table;
    width: 100%;
    margin-bottom: 20px;
    border-collapse: separate;
    border-spacing: 8px 0;
  }}
  .kpi-card {{
    display: table-cell;
    width: 25%;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 12px;
    text-align: center;
    vertical-align: middle;
  }}
  .kpi-num {{
    font-size: 26px;
    font-weight: bold;
    color: #1e40af;
    line-height: 1.2;
  }}
  .kpi-label {{
    font-size: 10px;
    color: #64748b;
    margin-top: 2px;
  }}

  /* ── 섹션 헤더 ── */
  h2 {{
    font-size: 13px;
    font-weight: bold;
    color: #1e293b;
    border-left: 4px solid #1e40af;
    padding-left: 8px;
    margin: 20px 0 10px 0;
  }}

  /* ── 요약 박스 ── */
  .summary-box {{
    background: #f0f9ff;
    border: 1px solid #bae6fd;
    border-radius: 6px;
    padding: 12px 14px;
    font-size: 12px;
    color: #0c4a6e;
    line-height: 1.7;
  }}

  /* ── 이슈/권고 리스트 ── */
  ul {{
    padding-left: 18px;
    margin: 0;
  }}
  ul li {{
    margin-bottom: 4px;
    font-size: 12px;
  }}

  /* ── 테이블 ── */
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
    margin-bottom: 4px;
  }}
  th {{
    background: #1e40af;
    color: #ffffff;
    padding: 7px 8px;
    text-align: left;
    font-size: 11px;
    white-space: nowrap;
  }}
  td {{
    padding: 6px 8px;
    border-bottom: 1px solid #f1f5f9;
    vertical-align: middle;
    word-break: break-all;
  }}
  tr:nth-child(even) td {{
    background: #f8fafc;
  }}

  /* ── 푸터 ── */
  .footer {{
    margin-top: 30px;
    padding-top: 10px;
    border-top: 1px solid #e2e8f0;
    font-size: 10px;
    color: #94a3b8;
    text-align: right;
  }}
</style>
</head>
<body>

<!-- 헤더 -->
<div class="report-header">
  <div class="report-title">일일 재고 현황 보고서</div>
  <div class="report-meta">
    보고일: {report_date.strftime('%Y년 %m월 %d일')}
    &nbsp;&nbsp;|&nbsp;&nbsp;
    위험도: <span class="risk-badge">{risk_label}</span>
  </div>
</div>

<!-- KPI -->
<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-num">{total_products}</div>
    <div class="kpi-label">전체 상품</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-num" style="color:#dc2626">{len(stock_anomalies)}</div>
    <div class="kpi-label">재고 이상</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-num" style="color:#ea580c">{len(sales_anomalies)}</div>
    <div class="kpi-label">판매 이상</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-num" style="color:#7c3aed">{len(stock_anomalies) + len(sales_anomalies)}</div>
    <div class="kpi-label">총 이상 징후</div>
  </div>
</div>

<!-- AI 요약 -->
<h2>AI 종합 요약</h2>
<div class="summary-box">{insight.get('overall_summary', '')}</div>

<!-- 핵심 이슈 -->
<h2>핵심 이슈</h2>
<ul>{issues_html if issues_html else '<li>이슈 없음</li>'}</ul>

<!-- 재고 이상 -->
<h2>재고 이상 징후 ({len(stock_anomalies)}건)</h2>
<table>
  <tr>
    <th>상품코드</th>
    <th>상품명</th>
    <th>유형</th>
    <th style="text-align:right">현재재고</th>
    <th style="text-align:right">소진예상</th>
    <th style="text-align:center">심각도</th>
  </tr>
  {stock_rows if stock_rows else '<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:16px">이상 징후 없음</td></tr>'}
</table>

<!-- 판매 이상 -->
<h2>판매 이상 징후 ({len(sales_anomalies)}건)</h2>
<table>
  <tr>
    <th>상품코드</th>
    <th>상품명</th>
    <th>유형</th>
    <th style="text-align:right">변화율</th>
    <th style="text-align:center">감성</th>
    <th style="text-align:center">심각도</th>
  </tr>
  {sales_rows if sales_rows else '<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:16px">이상 징후 없음</td></tr>'}
</table>

<!-- 권고사항 -->
<h2>조치 권고사항</h2>
<ul>{recs_html if recs_html else '<li>권고사항 없음</li>'}</ul>

<div class="footer">SCM Agent 자동 생성 &nbsp;|&nbsp; {report_date.strftime('%Y-%m-%d')}</div>
</body>
</html>"""