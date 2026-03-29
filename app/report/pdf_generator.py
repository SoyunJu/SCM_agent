
from pathlib import Path
from datetime import date, datetime
from loguru import logger
from app.report.template import build_daily_report_html

REPORTS_DIR = Path("reports")

_FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
    Path("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"),
    Path("/usr/share/fonts/nanum/NanumGothic.ttf"),
    Path("/usr/local/share/fonts/NanumGothic.ttf"),
]

def _find_font() -> Path | None:
    for p in _FONT_CANDIDATES:
        if p.exists():
            return p
    return None


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

    filename    = f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    output_path = REPORTS_DIR / filename

    try:
        from xhtml2pdf import pisa
        from xhtml2pdf.default import DEFAULT_FONT

        font_path = _find_font()
        if font_path:
            logger.info(f"[PDF] 한글 폰트 사용: {font_path}")
        else:
            logger.warning("[PDF] 한글 폰트 없음 — 깨짐 발생 가능")

        html_content = build_daily_report_html(
            report_date=report_date,
            total_products=total_products,
            stock_anomalies=stock_anomalies,
            sales_anomalies=sales_anomalies,
            insight=insight,
            font_path=str(font_path) if font_path else None,
        )

        with open(output_path, "wb") as f:
            status = pisa.CreatePDF(
                html_content,
                dest=f,
                encoding="utf-8",
            )

        if status.err:
            raise RuntimeError(f"xhtml2pdf 오류 코드: {status.err}")

        logger.info(f"[PDF] 보고서 생성 완료: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"[PDF] 보고서 생성 실패: {e}")
        raise