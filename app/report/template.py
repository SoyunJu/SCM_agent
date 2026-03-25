
from datetime import date


RISK_COLOR = {
    "low":      "#27ae60",
    "medium":   "#f39c12",
    "high":     "#e67e22",
    "critical": "#e74c3c",
}

ANOMALY_TYPE_KOR = {
    "low_stock":       "재고 부족",
    "over_stock":      "재고 과잉",
    "long_term_stock": "장기 재고",
    "sales_surge":     "판매 급등",
    "sales_drop":      "판매 급락",
}

SEVERITY_KOR = {
    "low":      "낮음",
    "medium":   "보통",
    "high":     "높음",
    "critical": "긴급",
}


def build_daily_report_html(
        report_date: date,
        total_products: int,
        stock_anomalies: list[dict],
        sales_anomalies: list[dict],
        insight: dict,
) -> str:

    risk_color = RISK_COLOR.get(insight.get("risk_level", "medium"), "#f39c12")

    # 재고 이상 테이블 행 생성
    stock_rows = ""
    for a in stock_anomalies:
        atype = ANOMALY_TYPE_KOR.get(str(a.get("anomaly_type", "")).lower(), a.get("anomaly_type", ""))
        sev = SEVERITY_KOR.get(str(a.get("severity", "")).lower(), a.get("severity", ""))
        days = a.get("days_until_stockout", "")
        days_str = f"{days}일" if days and days != 999.0 else "-"
        stock_rows += f"""
        <tr>
            <td>{a.get('product_code', '')}</td>
            <td>{a.get('product_name', '')}</td>
            <td>{atype}</td>
            <td>{a.get('current_stock', '-')}</td>
            <td>{days_str}</td>
            <td><span class="severity-{str(a.get('severity','')).lower()}">{sev}</span></td>
        </tr>"""

    # 판매 이상 테이블 행 생성
    sales_rows = ""
    for a in sales_anomalies:
        atype = ANOMALY_TYPE_KOR.get(str(a.get("anomaly_type", "")).lower(), a.get("anomaly_type", ""))
        sev = SEVERITY_KOR.get(str(a.get("severity", "")).lower(), a.get("severity", ""))
        rate = a.get("change_rate", 0)
        rate_str = f"+{rate:.1f}%" if rate > 0 else f"{rate:.1f}%"
        sentiment = a.get("sentiment", {}).get("label", "-")
        sales_rows += f"""
        <tr>
            <td>{a.get('product_code', '')}</td>
            <td>{a.get('product_name', '')}</td>
            <td>{atype}</td>
            <td>{rate_str}</td>
            <td>{sentiment}</td>
            <td><span class="severity-{str(a.get('severity','')).lower()}">{sev}</span></td>
        </tr>"""

    # 핵심 이슈
    issues_html = "".join(f"<li>{i}</li>" for i in insight.get("key_issues", []))

    # 조치 권고
    recs_html = "".join(f"<li>{r}</li>" for r in insight.get("recommendations", []))

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap');
  body      {{ font-family: 'Noto Sans KR', sans-serif; font-size: 13px; color: #2c3e50; margin: 40px; }}
  h1        {{ font-size: 20px; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px; }}
  h2        {{ font-size: 15px; color: #34495e; margin-top: 28px; }}
  .badge    {{ display: inline-block; padding: 4px 12px; border-radius: 12px;
               background: {risk_color}; color: white; font-weight: bold; font-size: 12px; }}
  .summary-box {{ background: #f8f9fa; border-left: 4px solid #3498db;
                  padding: 12px 16px; margin: 12px 0; border-radius: 4px; }}
  .stat-grid   {{ display: flex; gap: 16px; margin: 12px 0; }}
  .stat-card   {{ flex: 1; background: #fff; border: 1px solid #dde; border-radius: 8px;
                  padding: 12px; text-align: center; }}
  .stat-card .num  {{ font-size: 28px; font-weight: bold; color: #3498db; }}
  .stat-card .label {{ font-size: 11px; color: #7f8c8d; }}
  table     {{ width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 12px; }}
  th        {{ background: #3498db; color: white; padding: 8px; text-align: left; }}
  td        {{ padding: 7px 8px; border-bottom: 1px solid #eee; }}
  tr:hover  {{ background: #f5f9ff; }}
  ul        {{ padding-left: 20px; line-height: 2; }}
  .severity-critical {{ color: #e74c3c; font-weight: bold; }}
  .severity-high     {{ color: #e67e22; font-weight: bold; }}
  .severity-medium   {{ color: #f39c12; }}
  .severity-low      {{ color: #27ae60; }}
  .footer   {{ margin-top: 40px; font-size: 11px; color: #aaa; text-align: right; }}
</style>
</head>
<body>

<h1> 일일 재고 현황 보고서</h1>
<p>
  <strong>보고일:</strong> {report_date.strftime('%Y년 %m월 %d일')} &nbsp;|&nbsp;
  <strong>위험도:</strong> <span class="badge">{insight.get('risk_level', '-').upper()}</span>
</p>

<h2> 전체 현황</h2>
<div class="stat-grid">
  <div class="stat-card"><div class="num">{total_products}</div><div class="label">전체 상품</div></div>
  <div class="stat-card"><div class="num">{len(stock_anomalies)}</div><div class="label">재고 이상</div></div>
  <div class="stat-card"><div class="num">{len(sales_anomalies)}</div><div class="label">판매 이상</div></div>
  <div class="stat-card"><div class="num">{len(stock_anomalies) + len(sales_anomalies)}</div><div class="label">총 이상 징후</div></div>
</div>

<h2> AI 종합 요약</h2>
<div class="summary-box">{insight.get('overall_summary', '')}</div>

<h2> ⚠ 핵심 이슈 </h2>
<ul>{issues_html}</ul>

<h2> 재고 이상 징후</h2>
<table>
  <tr><th>상품코드</th><th>상품명</th><th>유형</th><th>현재재고</th><th>소진예상</th><th>심각도</th></tr>
  {stock_rows if stock_rows else '<tr><td colspan="6" style="text-align:center">이상 징후 없음</td></tr>'}
</table>

<h2> 판매 이상 징후</h2>
<table>
  <tr><th>상품코드</th><th>상품명</th><th>유형</th><th>변화율</th><th>감성</th><th>심각도</th></tr>
  {sales_rows if sales_rows else '<tr><td colspan="6" style="text-align:center">이상 징후 없음</td></tr>'}
</table>

<h2> 조치 권고사항</h2>
<ul>{recs_html}</ul>

<div class="footer">SCM Agent 자동 생성 | {report_date.strftime('%Y-%m-%d')}</div>
</body>
</html>"""