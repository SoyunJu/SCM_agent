from app.analyzer.stock_analyzer import (
    detect_low_stock,
    detect_over_stock,
    detect_long_term_stock,
    run_stock_analysis,
    StockAnomaly,
)
from app.analyzer.sales_analyzer import (
    detect_sales_anomaly,
    run_sales_analysis,
    get_top_sales,
    SalesAnomaly,
)

from app.analyzer.stock_analyzer import run_stock_analysis as _run_stock

def detect_stock_anomalies(df_master, df_stock, df_sales):
    return _run_stock(df_master, df_stock, df_sales)


__all__ = [
    "detect_low_stock",
    "detect_over_stock",
    "detect_long_term_stock",
    "run_stock_analysis",
    "detect_sales_anomaly",
    "run_sales_analysis",
    "get_top_sales",
    "StockAnomaly",
    "SalesAnomaly",
]
