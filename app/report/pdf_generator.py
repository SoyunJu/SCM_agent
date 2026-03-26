
from pathlib import Path
from datetime import date, datetime
from weasyprint import HTML
from loguru import logger
from app.report.template import build_daily_report_html


REPORTS_DIR = Path("reports")


def _ensure_reports_dir() -> None:
    REPORTS_DIR.mkdir(exist_ok=True)


def generate_daily_pdf(
        report_date: date,
        total_products: int,
        stock_anomalies: list[dict],
        sales_anomalies: list[dict],
        insight: dict,
) -> Path:

    _ensure_reports_dir()

    filename = f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    output_path = REPORTS_DIR / filename

    try:
        html_content = build_daily_report_html(
            report_date=report_date,
            total_products=total_products,
            stock_anomalies=stock_anomalies,
            sales_anomalies=sales_anomalies,
            insight=insight,
        )
        HTML(string=html_content).write_pdf(str(output_path))
        logger.info(f"################## PDF 보고서 생성 완료: {output_path} ##################")
        return output_path

    except Exception as e:
        logger.error(f"################## PDF 보고서 생성 실패: {e} ##################")
        raise