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
RISK_BORDER = {
    "LOW":      "#16a34a",
    "MEDIUM":   "#d97706",
    "HIGH":     "#ea580c",
    "CRITICAL": "#dc2626",
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
    "CRITICAL": "background:#fef2f2;color:#b91c1c;border:1px solid #fca5a5;font-weight:600;",
    "HIGH": "background:#fff7ed;color:#c2410c;border:1px solid #fdba74;font-weight:600;",
    "MEDIUM": "background:#fefce8;color:#a16207;border:1px solid #fde047;",
    "LOW": "background:#f0fdf4;color:#15803d;border:1px solid #86efac;",
    "CHECK": "background:#eff6ff;color:#1d4ed8;border:1px solid #93c5fd;",
}


def _severity_badge(raw: object) -> str:
    key   = _str_val(raw).upper()
    label = SEVERITY_KOR.get(key, key)
    style = SEVERITY_BADGE_STYLE.get(key, "background:#f1f5f9;color:#475569;border:1px solid #cbd5e1;")
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:99px;'
        f'font-size:10px;letter-spacing:0.2px;{style}">{label}</span>'
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

    risk_key    = _str_val(insight.get("risk_level", "MEDIUM")).upper()
    risk_color  = RISK_COLOR.get(risk_key, "#d97706")
    risk_bg     = RISK_BG.get(risk_key, "#fef3c7")
    risk_border = RISK_BORDER.get(risk_key, "#d97706")
    risk_label  = SEVERITY_KOR.get(risk_key, risk_key)

    font_face   = ""
    font_family = "NanumGothic, sans-serif"
    if font_path:
        font_face = f"""
  @font-face {{
    font-family: NanumGothic;
    src: url("{font_path}");
  }}"""

    issues_html = "".join(f"<li>{i}</li>" for i in insight.get("key_issues", []))
    recs_html   = "".join(f"<li>{r}</li>" for r in insight.get("recommendations", []))

    # ── 재고 이상 행 ──
    stock_rows = ""
    for a in stock_anomalies:
        atype    = _anomaly_type_label(a.get("anomaly_type", ""))
        days_raw = a.get("days_until_stockout", "")
        try:
            days_f = float(days_raw) if days_raw not in ("", None) else None
        except (ValueError, TypeError):
            days_f = None
        days_str = f"{days_f:.1f}일" if (days_f is not None and days_f < 999) else "-"
        sev_key  = _str_val(a.get("severity", "")).upper()
        row_bg   = "#fff5f5" if sev_key == "CRITICAL" else "#fff7ed" if sev_key == "HIGH" else "transparent"

        stock_rows += f"""
        <tr style="background:{row_bg}">
          <td style="white-space:nowrap;font-family:monospace">{a.get('product_code', '')}</td>
          <td>{a.get('product_name', '')}</td>
          <td style="white-space:nowrap">{atype}</td>
          <td style="text-align:right">{a.get('current_stock', '-'):,}개</td>
          <td style="text-align:right;white-space:nowrap">{days_str}</td>
          <td style="text-align:center">{_severity_badge(a.get('severity', ''))}</td>
        </tr>"""

    # ── 판매 이상 행 ──
    sales_rows = ""
    for a in sales_anomalies:
        atype = _anomaly_type_label(a.get("anomaly_type", ""))
        rate  = a.get("change_rate", 0)
        try:
            rate_f     = float(rate)
            rate_str   = f"+{rate_f:.1f}%" if rate_f > 0 else f"{rate_f:.1f}%"
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
        row_bg  = "#fff5f5" if sev_key == "CRITICAL" else "#fff7ed" if sev_key == "HIGH" else "transparent"

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
    generated_at    = report_date.strftime("%Y년 %m월 %d일")

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
    background: #1e3a5f;
    color: #ffffff;
    padding: 18px 22px 14px 22px;
    margin-bottom: 16px;
    border-radius: 6px;
  }}
  .report-title {{
    font-size: 17px;
    font-weight: bold;
    letter-spacing: -0.3px;
    margin-bottom: 10px;
    color: #ffffff;
  }}
  .report-meta {{
    font-size: 11px;
    color: #cbd5e1;
  }}

  /* ── 위험도 강조 블록 ── */
    .risk-block {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: 10px;
    padding: 5px 14px;
    border-radius: 99px;
    border: 1.5px solid {risk_border};
    background: {risk_bg};
  }}
  .risk-label-sm {{
    font-size: 10px;
    color: #64748b;
    display: block;
    margin-bottom: 2px;
  }}
  .risk-value {{
    font-size: 20px;
    font-weight: bold;
    color: {risk_color};
    letter-spacing: 1px;
  }}

  /* ── KPI 테이블 (xhtml2pdf 호환) ── */
  .kpi-table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 6px 0;
    margin-bottom: 16px;
  }}
  .kpi-table td {{
    width: 25%;
    border: 1px solid #e2e8f0;
    border-top: 3px solid #3b82f6;
    border-radius: 0 0 6px 6px;
    padding: 12px 6px 10px 6px;
    text-align: center;
    vertical-align: middle;
    background: #ffffff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }}
  .kpi-num {{
    font-size: 22px;
    font-weight: bold;
    line-height: 1.2;
    display: block;
  }}
  .kpi-label {{
    font-size: 10px;
    color: #64748b;
    margin-top: 3px;
    display: block;
  }}
  .c-blue   {{ color: #1e40af; }}
  .c-orange {{ color: #ea580c; }}
  .c-red    {{ color: #dc2626; }}
  .c-purple {{ color: #7c3aed; }}

  /* ── 섹션 헤더 ── */
  .section-title {{
    font-size: 11px;
    font-weight: 700;
    color: #334155;
    border-left: 3px solid #3b82f6;
    padding: 4px 0 4px 10px;
    margin: 18px 0 8px 0;
    background: transparent;
    letter-spacing: 0.3px;
    text-transform: uppercase;
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

  /* ── 2컬럼 (table 방식) ── */
  .two-col {{ width: 100%; border-collapse: separate; border-spacing: 8px 0; margin-bottom: 10px; }}
  .col-cell {{
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
  ul {{ padding-left: 14px; margin: 0; }}
  ul li {{ margin-bottom: 4px; font-size: 11px; color: #374151; }}

  /* ── 데이터 테이블 ── */
  table.data-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 10px;
    margin-bottom: 4px;
  }}
  table.data-table th {{
    background: #f8fafc;
    color: #475569;
    border-bottom: 2px solid #e2e8f0;
    border-top: 1px solid #e2e8f0;
    padding: 6px 7px;
    text-align: left;
    font-size: 10px;
    white-space: nowrap;
    border-bottom: 2px solid #1e293b;
  }}
  table.data-table td {{
    padding: 5px 7px;
    border-bottom: 1px solid #f1f5f9;
    vertical-align: middle;
  }}
  table.data-table tr:nth-child(even) td {{ background: #f8fafc; }}

  /* ── 푸터 ── */
  .footer-table {{ width: 100%; margin-top: 20px; padding-top: 8px; border-top: 1px solid #e2e8f0; }}
  .footer-table td {{ font-size: 9px; color: #94a3b8; vertical-align: middle; }}
</style>
</head>
<body>

<!-- 헤더 -->
<div class="report-header">
  <div class="report-title">SCM Agent &nbsp;|&nbsp; 일일 재고 현황 보고서</div>
  <div class="report-meta">보고일: {generated_at}</div>
  <div class="risk-block">
    <span class="risk-label-sm">위험도</span>
    <span class="risk-value">{risk_label}</span>
  </div>
</div>

<!-- KPI -->
<table class="kpi-table">
  <tr>
    <td>
      <span class="kpi-num c-blue">{total_products:,}</span>
      <span class="kpi-label">전체 상품</span>
    </td>
    <td style="border-top:3px solid #f97316;">
      <span class="kpi-num c-orange">{len(stock_anomalies)}</span>
      <span class="kpi-label">재고 이상</span>
    </td>
    <td style="border-top:3px solid #ef4444;">
      <span class="kpi-num c-red">{len(sales_anomalies)}</span>
      <span class="kpi-label">판매 이상</span>
    </td>
    <td style="border-top:3px solid #8b5cf6;">
      <span class="kpi-num c-purple">{total_anomalies}</span>
      <span class="kpi-label">총 이상 징후</span>
    </td>
  </tr>
</table>

<!-- AI 종합 요약 -->
<div class="section-title">AI 종합 요약</div>
<div class="summary-box">{insight.get('overall_summary', '요약 없음')}</div>

<!-- 핵심 이슈 + 권고사항 -->
<table class="two-col">
  <tr>
    <td class="col-cell">
      <div class="col-title">⚠ 핵심 이슈</div>
      <ul>{issues_html if issues_html else '<li>이슈 없음</li>'}</ul>
    </td>
    <td class="col-cell">
      <div class="col-title">✔ 조치 권고사항</div>
      <ul>{recs_html if recs_html else '<li>권고사항 없음</li>'}</ul>
    </td>
  </tr>
</table>

<!-- 재고 이상 -->
<div class="section-title">재고 이상 징후 ({len(stock_anomalies)}건)</div>
<table class="data-table">
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
<table class="data-table">
  <tr>
    <th>상품코드</th><th>상품명</th><th>유형</th>
    <th style="text-align:right">변화율</th>
    <th style="text-align:center">감성</th>
    <th style="text-align:center">심각도</th>
  </tr>
  {sales_rows if sales_rows else '<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:14px">이상 징후 없음</td></tr>'}
</table>

<!-- 푸터 -->
<table class="footer-table">
  <tr>
    <td style="text-align:left">SCM Agent 자동 생성 보고서</td>
    <td style="text-align:right">{report_date.strftime('%Y-%m-%d')} &nbsp;|&nbsp; Confidential</td>
  </tr>
</table>

</body>
</html>"""