from celery.schedules import crontab
from datetime import timedelta

BEAT_SCHEDULE = {
    # 일일 보고서 (매일 00:00)
    "daily-report": {
        "task":     "app.celery_app.tasks.run_daily_report",
        "schedule": crontab(hour=0, minute=0),
    },
    # 크롤러 (매일 23:00)
    "daily-crawler": {
        "task":     "app.celery_app.tasks.run_crawler",
        "schedule": crontab(hour=23, minute=0),
    },
    # 오래된 데이터 정리 (매일 02:00)
    "cleanup-data": {
        "task":     "app.celery_app.tasks.run_cleanup",
        "schedule": crontab(hour=2, minute=0),
    },
    # Sheets->DB 15분 주기 동기화
    "sync-sheets-to-db": {
        "task":     "app.celery_app.tasks.run_sync_sheets_to_db",
        "schedule": timedelta(minutes=15),
    },
    # 수요 예측 분석 (매일 01:00)
    "demand-forecast": {
        "task":     "app.celery_app.tasks.run_demand_forecast",
        "schedule": crontab(hour=1, minute=0),
    },
    # 재고 회전율 분석 (매일 01:30)
    "turnover-analysis": {
        "task":     "app.celery_app.tasks.run_turnover_analysis",
        "schedule": crontab(hour=1, minute=30),
    },
    # ABC 분석 (매일 02:30)
    "abc-analysis": {
        "task":     "app.celery_app.tasks.run_abc_analysis_task",
        "schedule": crontab(hour=2, minute=30),
    },
}
