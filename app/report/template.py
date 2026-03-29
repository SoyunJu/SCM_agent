from datetime import date


# ── Enum 값 안전 추출 ─────────────────────────────────────────────────────────
def _str_val(v: object) -> str:
    if v is None:
        return ""
    if hasattr(v, "value"):
        return str(v.value)
    return str(v)


# ── 매핑 ─────────────────────────────────────────────────────────────────────
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
        f'font-size:10px;{style}">{label}</span>'
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
        font_path: str | None = None,
) -> str:

    risk_key   = _str_val(insight.get("risk_level", "MEDIUM")).upper()
    risk_color = RISK_COLOR.get(risk_key, "#d97706")
    risk_bg    = RISK_BG.get(risk_key, "#fef3c7")
    risk_label = SEVERITY_KOR.get(risk_key, risk_key)

    # @font-face 블록 (폰트 있을 때만)
    font_face = ""
    font_family = "NanumGothic, sans-serif"
    if font_path:
        font_face = f"""
  @font-face {{
    font-family: NanumGothic;
    src: url("{font_path}");
  }}"""

    # 핵심 이슈 / 권고사항
    issues_html = "".join(f"<li>{i}</li>" for i in insight.get("key_issues", []))
    recs_html = "".join(f"<li>{r}</li>" for r in insight.get("recommendations", []))

    # 재고 이상 테이블 행
    stock_rows = ""
    for a in stock_anomalies:
        atype    = _anomaly_type_label(a.get("anomaly_type", ""))
        days_raw = a.get("days_until_stockout", "")
        try:
            days_f   = float(days_raw) if days_raw not in ("", None) else None
        except (ValueError, TypeError):
            days_f = None
        days_str = f"{days_f:.1f}일" if (days_f is not None and days_f < 999) else "-"
        sev_key = _str_val(a.get("severity", "")).upper()
        row_bg = "#fff5f5" if sev_key == "CRITICAL" else "#fff7ed" if sev_key == "HIGH" else "transparent"

        stock_rows += f"""
        <tr style="background:{row_bg}">
          <td style="white-space:nowrap;font-family:monospace">{a.get('product_code', '')}</td>
          <td>{a.get('product_name', '')}</td>
          <td style="white-space:nowrap">{atype}</td>
          <td style="text-align:right">{a.get('current_stock', '-'):,}개</td>
          <td style="text-align:right;white-space:nowrap">{days_str}</td>
          <td style="text-align:center">{_severity_badge(a.get('severity', ''))}</td>
        </tr>"""

    # 판매 이상 테이블 행
    sales_rows = ""
    for a in sales_anomalies:
        atype = _anomaly_type_label(a.get("anomaly_type", ""))
        rate = a.get("change_rate", 0)
        try:
            rate_f = float(rate)
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

        sev_key = _str_val(a.get("severity", "")).upper()
        row_bg = "#fff5f5" if sev_key == "CRITICAL" else "#fff7ed" if sev_key == "HIGH" else "transparent"

        sales_rows += f"""
        <tr style="background:{row_bg}">
          <td style="white-space:nowrap;font-family:monospace">{a.get('product_code', '')}</td>
          <td>{a.get('product_name', '')}</td>
          <td style="white-space:nowrap">{atype}</td>
          <td style="text-align:right;color:{rate_color};font-weight:bold">{rate_str}</td>
          <td style="text-align:center">{sentiment}</td>
          <td style="text-align:center">{_severity_badge(a.get('severity', ''))}</td>
        </tr>"""

    total_anomalies = len(stock_anomalies) + len(sales_anomalies)
    generated_at = f"{report_date.strftime('%Y년 %m월 %d일')}"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"/>
<style>
  {font_face}

  @page {{ margin: 16mm 14mm 16mm 14mm; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: {font_family};
    font-size: 11px;
    color: #1e293b;
    line-height: 1.6;
  }}

  /* ── 헤더 ── */
  .report-header {{
    background: #1e40af;
    color: #ffffff;
    padding: 16px 20px;
    margin-bottom: 20px;
    border-radius: 6px;
  }}
  .report-title {{
    font-size: 18px;
    font-weight: bold;
    letter-spacing: -0.3px;
    margin-bottom: 4px;
  }}
  .report-meta {{
    font-size: 11px;
    color: #bfdbfe;
  }}
  .risk-badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 9999px;
    font-size: 11px;
    font-weight: bold;
    background: {risk_bg};
    color: {risk_color};
  }}

  /* ── KPI 카드 ── */
  .kpi-grid {{
    display: table;
    width: 100%;
    margin-bottom: 18px;
    border-collapse: separate;
    border-spacing: 6px 0;
  }}
  .kpi-card {{
    display: table-cell;
    width: 25%;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-top: 3px solid #1e40af;
    border-radius: 4px;
    padding: 10px 8px;
    text-align: center;
    vertical-align: middle;
  }}
  .kpi-card.warn {{ border-top-color: #ea580c; }}
  .kpi-card.danger {{ border-top-color: #dc2626; }}
  .kpi-card.purple {{ border-top-color: #7c3aed; }}
  .kpi-num {{
    font-size: 22px;
    font-weight: bold;
    color: #1e40af;
    line-height: 1.2;
  }}
  .kpi-num.warn   {{ color: #ea580c; }}
  .kpi-num.danger {{ color: #dc2626; }}
  .kpi-num.purple {{ color: #7c3aed; }}
  .kpi-label {{
    font-size: 10px;
    color: #64748b;
    margin-top: 3px;
  }}

  /* ── 섹션 헤더 ── */
  .section-title {{
    font-size: 12px;
    font-weight: bold;
    color: #ffffff;
    background: #334155;
    padding: 6px 10px;
    margin: 18px 0 8px 0;
    border-radius: 4px;
  }}

  /* ── 요약 박스 ── */
  .summary-box {{
    background: #f0f9ff;
    border-left: 4px solid #0284c7;
    border-radius: 0 4px 4px 0;
    padding: 10px 14px;
    font-size: 11px;
    color: #0c4a6e;
    line-height: 1.8;
    margin-bottom: 10px;
  }}

  /* ── 두 컬럼 레이아웃 ── */
  .two-col {{
    display: table;
    width: 100%;
    border-collapse: separate;
    border-spacing: 10px 0;
    margin-bottom: 10px;
  }}
  .col {{
    display: table-cell;
    width: 50%;
    vertical-align: top;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 10px 12px;
  }}
  .col-title {{
    font-size: 10px;
    font-weight: bold;
    color: #475569;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  ul {{
    padding-left: 14px;
    margin: 0;
  }}
  ul li {{
    margin-bottom: 4px;
    font-size: 11px;
    color: #374151;
  }}

  /* ── 테이블 ── */
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 10px;
    margin-bottom: 4px;
  }}
  th {{
    background: #334155;
    color: #f1f5f9;
    padding: 6px 7px;
    text-align: left;
    font-size: 10px;
    white-space: nowrap;
    border-bottom: 2px solid #1e293b;
  }}
  td {{
    padding: 5px 7px;
    border-bottom: 1px solid #f1f5f9;
    vertical-align: middle;
  }}
  tr:nth-child(even) td {{ background: #f8fafc; }}

  /* ── 푸터 ── */
  .footer {{
    margin-top: 24px;
    padding-top: 8px;
    border-top: 1px solid #e2e8f0;
    font-size: 9px;
    color: #94a3b8;
    display: table;
    width: 100%;
  }}
  .footer-left  {{ display: table-cell; text-align: left; }}
  .footer-right {{ display: table-cell; text-align: right; }}
</style>
</head>
<body>

<!-- 헤더 -->
<div class="report-header">
  <div class="report-title">SCM Agent &nbsp;|&nbsp; 일일 재고 현황 보고서</div>
  <div class="report-meta">
    보고일: {generated_at}
    &nbsp;&nbsp;&nbsp;
    위험도: <span class="risk-badge">{risk_label}</span>
  </div>
</div>

<!-- KPI -->
<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-num">{total_products:,}</div>
    <div class="kpi-label">전체 상품</div>
  </div>
  <div class="kpi-card warn">
    <div class="kpi-num warn">{len(stock_anomalies)}</div>
    <div class="kpi-label">재고 이상</div>
  </div>
  <div class="kpi-card danger">
    <div class="kpi-num danger">{len(sales_anomalies)}</div>
    <div class="kpi-label">판매 이상</div>
  </div>
  <div class="kpi-card purple">
    <div class="kpi-num purple">{total_anomalies}</div>
    <div class="kpi-label">총 이상 징후</div>
  </div>
</div>

<!-- AI 종합 요약 -->
<div class="section-title">AI 종합 요약</div>
<div class="summary-box">{insight.get('overall_summary', '요약 없음')}</div>

<!-- 핵심 이슈 + 권고사항 (2컬럼) -->
<div class="two-col">
  <div class="col">
    <div class="col-title">⚠ 핵심 이슈</div>
    <ul>{issues_html if issues_html else '<li>이슈 없음</li>'}</ul>
  </div>
  <div class="col">
    <div class="col-title">✔ 조치 권고사항</div>
    <ul>{recs_html if recs_html else '<li>권고사항 없음</li>'}</ul>
  </div>
</div>

<!-- 재고 이상 -->
<div class="section-title">재고 이상 징후 ({len(stock_anomalies)}건)</div>
<table>
  <tr>
    <th>상품코드</th><th>상품명</th><th>유형</th>
    <th style="text-align:right">현재재고</th>
    <th style="text-align:right">소진예상</th>
    <th style="text-align:center">심각도</th>
  </tr>
  {stock_rows if stock_rows else '<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:14px">이상 징후 없음</td></tr>'}
</table>

<!-- 판매 이상 -->
<div class="section-title">판매 이상 징후 ({len(sales_anomalies)}건)</div>
<table>
  <tr>
    <th>상품코드</th><th>상품명</th><th>유형</th>
    <th style="text-align:right">변화율</th>
    <th style="text-align:center">감성</th>
    <th style="text-align:center">심각도</th>
  </tr>
  {sales_rows if sales_rows else '<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:14px">이상 징후 없음</td></tr>'}
</table>

<!-- 푸터 -->
<div class="footer">
  <div class="footer-left">SCM Agent 자동 생성 보고서</div>
  <div class="footer-right">{report_date.strftime('%Y-%m-%d')} &nbsp;|&nbsp; Confidential</div>
</div>

</body>
</html>"""