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
    "LOW":      "#15803d",
    "MEDIUM":   "#b45309",
    "HIGH":     "#c2410c",
    "CRITICAL": "#b91c1c",
}
RISK_BG = {
    "LOW":      "#f0fdf4",
    "MEDIUM":   "#fffbeb",
    "HIGH":     "#fff7ed",
    "CRITICAL": "#fef2f2",
}
RISK_BORDER = {
    "LOW":      "#86efac",
    "MEDIUM":   "#fde68a",
    "HIGH":     "#fed7aa",
    "CRITICAL": "#fecaca",
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
    "CRITICAL": "background:#fef2f2;color:#b91c1c;border:1px solid #fca5a5;font-weight:bold;",
    "HIGH":     "background:#fff7ed;color:#c2410c;border:1px solid #fdba74;font-weight:bold;",
    "MEDIUM":   "background:#fffbeb;color:#b45309;border:1px solid #fde68a;",
    "LOW":      "background:#f0fdf4;color:#15803d;border:1px solid #86efac;",
    "CHECK":    "background:#eff6ff;color:#1d4ed8;border:1px solid #93c5fd;",
}


def _severity_badge(raw: object) -> str:
    key   = _str_val(raw).upper()
    label = SEVERITY_KOR.get(key, key)
    style = SEVERITY_BADGE_STYLE.get(key, "background:#f8fafc;color:#475569;border:1px solid #cbd5e1;")
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:4px;'
        f'font-size:10px;letter-spacing:0.3px;{style}">{label}</span>'
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
    risk_color  = RISK_COLOR.get(risk_key, "#b45309")
    risk_bg     = RISK_BG.get(risk_key, "#fffbeb")
    risk_border = RISK_BORDER.get(risk_key, "#fde68a")
    risk_label  = SEVERITY_KOR.get(risk_key, risk_key)

    font_face   = ""
    font_family = "NanumGothic, sans-serif"
    if font_path:
        font_face = f"""
  @font-face {{
    font-family: NanumGothic;
    src: url("{font_path}");
  }}"""

    issues_html = "".join(f"<li style='margin-bottom:6px;'>{i}</li>" for i in insight.get("key_issues", []))
    recs_html   = "".join(f"<li style='margin-bottom:6px;'>{r}</li>" for r in insight.get("recommendations", []))

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

        # 행 배경색을 조금 더 부드럽게 조정
        row_bg   = "#fef2f2" if sev_key == "CRITICAL" else "#fff7ed" if sev_key == "HIGH" else "transparent"

        stock_rows += f"""
        <tr style="background:{row_bg}">
          <td style="white-space:nowrap;font-family:monospace;color:#475569;">{a.get('product_code', '')}</td>
          <td style="font-weight:bold;color:#1e293b;">{a.get('product_name', '')}</td>
          <td style="white-space:nowrap;color:#64748b;">{atype}</td>
          <td style="text-align:right;font-weight:bold;">{a.get('current_stock', '-'):,}개</td>
          <td style="text-align:right;white-space:nowrap;color:#ef4444;">{days_str}</td>
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
            rate_color = "#475569"

        sentiment = ""
        raw_sent  = a.get("sentiment")
        if isinstance(raw_sent, dict):
            sentiment = raw_sent.get("label", "")
        elif isinstance(raw_sent, str):
            sentiment = raw_sent

        sev_key = _str_val(a.get("severity", "")).upper()
        row_bg  = "#fef2f2" if sev_key == "CRITICAL" else "#fff7ed" if sev_key == "HIGH" else "transparent"

        sales_rows += f"""
        <tr style="background:{row_bg}">
          <td style="white-space:nowrap;font-family:monospace;color:#475569;">{a.get('product_code', '')}</td>
          <td style="font-weight:bold;color:#1e293b;">{a.get('product_name', '')}</td>
          <td style="white-space:nowrap;color:#64748b;">{atype}</td>
          <td style="text-align:right;color:{rate_color};font-weight:bold;">{rate_str}</td>
          <td style="text-align:center;color:#64748b;">{sentiment}</td>
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

  @page {{ margin: 15mm; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: {font_family};
    font-size: 11px;
    color: #334155;
    line-height: 1.6;
    background-color: #ffffff;
  }}

  /* ── 헤더 (PDF 안정성을 위해 단색 처리) ── */
  .report-header {{
    background-color: #0f172a;
    color: #ffffff;
    padding: 20px 24px;
    margin-bottom: 24px;
    border-radius: 6px;
  }}
  .report-title {{
    font-size: 18px;
    font-weight: bold;
    letter-spacing: -0.5px;
    color: #ffffff;
  }}
  .report-meta {{
    font-size: 11px;
    color: #94a3b8;
    margin-top: 6px;
  }}

  /* ── KPI 테이블 (xhtml2pdf 호환) ── */
  .kpi-table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 24px;
  }}
  .kpi-table td {{
    width: 25%;
    border: 1px solid #e2e8f0;
    padding: 16px 10px;
    text-align: center;
    vertical-align: middle;
    background: #f8fafc;
  }}
  .kpi-table td.b-blue   {{ border-top: 4px solid #3b82f6; }}
  .kpi-table td.b-orange {{ border-top: 4px solid #f97316; }}
  .kpi-table td.b-red    {{ border-top: 4px solid #ef4444; }}
  .kpi-table td.b-purple {{ border-top: 4px solid #8b5cf6; }}
  
  .kpi-num {{
    font-size: 24px;
    font-weight: bold;
    line-height: 1.2;
    display: block;
    margin-bottom: 4px;
  }}
  .kpi-label {{
    font-size: 11px;
    color: #64748b;
    font-weight: bold;
    display: block;
  }}
  .c-blue   {{ color: #2563eb; }}
  .c-orange {{ color: #ea580c; }}
  .c-red    {{ color: #dc2626; }}
  .c-purple {{ color: #7c3aed; }}

  /* ── 섹션 헤더 ── */
  .section-title {{
    font-size: 13px;
    font-weight: bold;
    color: #0f172a;
    border-left: 4px solid #3b82f6;
    padding: 4px 0 4px 12px;
    margin: 24px 0 12px 0;
    background: transparent;
    letter-spacing: -0.3px;
  }}

  /* ── 요약 박스 ── */
  .summary-box {{
    background: #f0f9ff;
    border: 1px solid #bae6fd;
    border-radius: 4px;
    padding: 14px 18px;
    font-size: 12px;
    color: #0369a1;
    line-height: 1.7;
    margin-bottom: 16px;
  }}

  /* ── 2컬럼 (table 방식) ── */
  .two-col {{ 
    width: 100%; 
    border-collapse: separate; 
    border-spacing: 12px 0; 
    margin-bottom: 16px; 
    margin-left: -6px; /* border-spacing 보정 */
  }}
  .col-cell {{
    width: 50%;
    vertical-align: top;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 16px;
  }}
  .col-title {{
    font-size: 12px;
    font-weight: bold;
    color: #334155;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid #f1f5f9;
  }}
  ul {{ padding-left: 18px; margin: 0; }}
  ul li {{ font-size: 11px; color: #475569; line-height: 1.5; }}

  /* ── 데이터 테이블 ── */
  table.data-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
    margin-bottom: 8px;
  }}
  table.data-table th {{
    background: #f1f5f9;
    color: #334155;
    border-top: 2px solid #cbd5e1;
    border-bottom: 2px solid #cbd5e1;
    padding: 10px 8px;
    text-align: left;
    font-weight: bold;
    white-space: nowrap;
  }}
  table.data-table td {{
    padding: 8px 8px;
    border-bottom: 1px solid #e2e8f0;
    vertical-align: middle;
  }}
  table.data-table tr:nth-child(even) td {{ background: #fafafa; }}

  /* ── 푸터 ── */
  .footer-table {{ 
    width: 100%; 
    margin-top: 32px; 
    padding-top: 12px; 
    border-top: 1px solid #cbd5e1; 
  }}
  .footer-table td {{ 
    font-size: 10px; 
    color: #64748b; 
    vertical-align: middle; 
  }}
</style>
</head>
<body>

<div class="report-header">
  <table style="width:100%;border-collapse:collapse;">
    <tr>
      <td style="vertical-align:middle;">
        <div class="report-title">SCM Agent 일일 재고 현황 보고서</div>
        <div class="report-meta">보고일자: {generated_at}</div>
      </td>
      <td style="text-align:right;vertical-align:middle;white-space:nowrap;">
        <span style="font-size:10px;color:#cbd5e1;display:block;margin-bottom:4px;">종합 위험도</span>
        <span style="
          display:inline-block;
          padding:6px 16px;
          border-radius:4px;
          font-size:14px;
          font-weight:bold;
          letter-spacing:1px;
          color:{risk_color};
          background:{risk_bg};
          border:1px solid {risk_border};
        ">{risk_label}</span>
      </td>
    </tr>
  </table>
</div>

<table class="kpi-table">
  <tr>
    <td class="b-blue">
      <span class="kpi-num c-blue">{total_products:,}</span>
      <span class="kpi-label">전체 상품</span>
    </td>
    <td class="b-orange">
      <span class="kpi-num c-orange">{len(stock_anomalies)}</span>
      <span class="kpi-label">재고 이상</span>
    </td>
    <td class="b-red">
      <span class="kpi-num c-red">{len(sales_anomalies)}</span>
      <span class="kpi-label">판매 이상</span>
    </td>
    <td class="b-purple">
      <span class="kpi-num c-purple">{total_anomalies}</span>
      <span class="kpi-label">총 이상 징후</span>
    </td>
  </tr>
</table>

<div class="section-title">AI 종합 요약</div>
<div class="summary-box">{insight.get('overall_summary', '요약 데이터가 없습니다.')}</div>

<table class="two-col">
  <tr>
    <td class="col-cell">
      <div class="col-title">⚠ 핵심 이슈</div>
      <ul>{issues_html if issues_html else '<li>보고된 이슈가 없습니다.</li>'}</ul>
    </td>
    <td class="col-cell">
      <div class="col-title">✔ 조치 권고사항</div>
      <ul>{recs_html if recs_html else '<li>권고사항이 없습니다.</li>'}</ul>
    </td>
  </tr>
</table>

<div class="section-title">재고 이상 징후 ({len(stock_anomalies)}건)</div>
<table class="data-table">
  <tr>
    <th>상품코드</th>
    <th>상품명</th>
    <th>유형</th>
    <th style="text-align:right">현재재고</th>
    <th style="text-align:right">소진예상</th>
    <th style="text-align:center">심각도</th>
  </tr>
  {stock_rows if stock_rows else '<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:20px">이상 징후가 없습니다.</td></tr>'}
</table>

<div class="section-title">판매 이상 징후 ({len(sales_anomalies)}건)</div>
<table class="data-table">
  <tr>
    <th>상품코드</th>
    <th>상품명</th>
    <th>유형</th>
    <th style="text-align:right">변화율</th>
    <th style="text-align:center">감성</th>
    <th style="text-align:center">심각도</th>
  </tr>
  {sales_rows if sales_rows else '<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:20px">이상 징후가 없습니다.</td></tr>'}
</table>

<table class="footer-table">
  <tr>
    <td style="text-align:left; font-weight:bold;">SCM Agent Automated Report</td>
    <td style="text-align:right">{report_date.strftime('%Y-%m-%d')} &nbsp;|&nbsp; Internal Use Only</td>
  </tr>
</table>

</body>
</html>"""