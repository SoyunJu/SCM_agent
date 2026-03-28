from celery.schedules import crontab

BEAT_SCHEDULE = {
    # 일일 보고서
    "daily-report": {
        "task":     "app.celery_app.tasks.run_daily_report",
        "schedule": crontab(hour=0, minute=0),
    },
    # 크롤러 실행
    "daily-crawler": {
        "task":     "app.celery_app.tasks.run_crawler",
        "schedule": crontab(hour=23, minute=0),
    },
    # 오래된 데이터 정리
    "cleanup-data": {
        "task":     "app.celery_app.tasks.run_cleanup",
        "schedule": crontab(hour=2, minute=0),
    },
}
