
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from app.sheets.reader import read_product_master, read_sales, read_stock
from app.analyzer.stock_analyzer import run_stock_analysis
from app.analyzer.sales_analyzer import run_sales_analysis
from app.db.connection import SessionLocal
from app.db.repository import create_anomaly_log
from app.db.models import AnomalyType, Severity


def run():
    logger.info("################## 분석 실행 시작 ##################")

    # 1. Sheets Read
    df_master = read_product_master()
    df_sales = read_sales()
    df_stock = read_stock()

    # 2. 재고 분석
    stock_anomalies = run_stock_analysis(df_master, df_stock, df_sales)

    # 3. 판매 분석
    sales_anomalies = run_sales_analysis(df_master, df_sales)

    # 4. 전체 이상 징후 DB 저장
    db = SessionLocal()
    try:
        for item in stock_anomalies:
            create_anomaly_log(
                db=db,
                product_code=item["product_code"],
                product_name=item["product_name"],
                anomaly_type=AnomalyType(item["anomaly_type"]),
                severity=Severity(item["severity"]),
                current_stock=item.get("current_stock"),
                daily_avg_sales=item.get("daily_avg_sales"),
                days_until_stockout=item.get("days_until_stockout"),
            )

        for item in sales_anomalies:
            create_anomaly_log(
                db=db,
                product_code=item["product_code"],
                product_name=item["product_name"],
                anomaly_type=AnomalyType(item["anomaly_type"]),
                severity=Severity(item["severity"]),
            )
    finally:
        db.close()

    logger.info(f"################## 분석 완료: 재고 {len(stock_anomalies)}건 / 판매 {len(sales_anomalies)}건 ##################")


if __name__ == "__main__":
    run()