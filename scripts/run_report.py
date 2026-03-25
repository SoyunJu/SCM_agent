
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from loguru import logger
from app.sheets.reader import read_product_master, read_sales, read_stock
from app.analyzer.stock_analyzer import run_stock_analysis
from app.analyzer.sales_analyzer import run_sales_analysis
from app.ai.sentiment_analyzer import batch_analyze_sales_anomalies
from app.ai.insight_generator import generate_daily_insight
from app.report.pdf_generator import generate_daily_pdf


def run():
    logger.info("===== 보고서 생성 시작 =====")

    # 1. Sheets 데이터 읽기
    df_master = read_product_master()
    df_sales  = read_sales()
    df_stock  = read_stock()

    # 2. 분석
    stock_anomalies = run_stock_analysis(df_master, df_stock, df_sales)
    sales_anomalies = run_sales_analysis(df_master, df_sales)

    # 3. HuggingFace 감성 분석
    sales_anomalies = batch_analyze_sales_anomalies(sales_anomalies)

    # 4. OpenAI 인사이트 생성
    insight = generate_daily_insight(
        stock_anomalies=stock_anomalies,
        sales_anomalies=sales_anomalies,
        total_products=len(df_master),
    )

    # 5. PDF 생성
    pdf_path = generate_daily_pdf(
        report_date=date.today(),
        total_products=len(df_master),
        stock_anomalies=[dict(a) for a in stock_anomalies],
        sales_anomalies=sales_anomalies,
        insight=insight,
    )

    # 6. Slack 알림 + PDF 전송
    today_str = date.today().strftime("%Y-%m-%d")
    slack_ok = send_daily_report_notification(
        report_date=today_str,
        total_products=len(df_master),
        stock_anomaly_count=len(stock_anomalies),
        sales_anomaly_count=len(sales_anomalies),
        risk_level=insight.get("risk_level", "medium"),
        pdf_path=pdf_path,
    )

    if slack_ok:
        logger.info("Slack 전송 완료")
    else:
        logger.warning("Slack 전송 실패 (로컬 저장)")

    logger.info(f"===== 보고서 생성 완료: {pdf_path} =====")


if __name__ == "__main__":
    run()