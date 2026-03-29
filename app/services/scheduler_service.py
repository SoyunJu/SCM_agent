from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from app.db.repository import get_schedule_config, upsert_schedule_config



class SchedulerService:

    # --- 보고서 스케줄 설정 조회 ---
    @staticmethod
    def get_config(db: Session) -> dict:
        record = get_schedule_config(db, "daily_report")
        if not record:
            return {
                "job_name":        "daily_report",
                "schedule_hour":   0,
                "schedule_minute": 0,
                "timezone":        "Asia/Seoul",
                "is_active":       True,
                "last_run_at":     None,
            }
        return {
            "job_name":        record.job_name,
            "schedule_hour":   record.schedule_hour,
            "schedule_minute": record.schedule_minute,
            "timezone":        record.timezone,
            "is_active":       record.is_active,
            "last_run_at":     str(record.last_run_at) if record.last_run_at else None,
        }


    # --- 보고서 스케줄 설정 저장 + Celery Beat 즉시 반영 ---
    @staticmethod
    def update_config(db: Session, schedule_hour: int, schedule_minute: int,
                      timezone: str, is_active: bool, username: str) -> dict:
        upsert_schedule_config(
            db=db,
            job_name="daily_report",
            schedule_hour=schedule_hour,
            schedule_minute=schedule_minute,
            timezone=timezone,
            is_active=is_active,
        )
        logger.info(f"스케줄 설정 저장: {schedule_hour:02d}:{schedule_minute:02d} by {username}")

        # Celery Beat 메모리 즉시 반영 (실패 시 Beat 재시작 후 적용)
        try:
            from app.celery_app.celery import celery_app
            from celery.schedules import crontab
            celery_app.conf.beat_schedule["daily-report"]["schedule"] = crontab(
                hour=schedule_hour,
                minute=schedule_minute,
            )
            logger.info("Celery Beat 스케줄 즉시 반영 완료")
        except Exception as e:
            logger.warning(f"Celery Beat 즉시 반영 실패 (재시작 후 적용): {e}")

        return {
            "message":         "스케줄이 업데이트되었습니다.",
            "schedule_hour":   schedule_hour,
            "schedule_minute": schedule_minute,
            "timezone":        timezone,
            "is_active":       is_active,
        }


    # --- Celery Worker/Beat 상태 조회 ---

    @staticmethod
    def _format_schedule(schedule) -> str:
        from celery.schedules import crontab
        from datetime import timedelta
        try:
            if isinstance(schedule, crontab):
                hour   = str(schedule.hour)
                minute = str(schedule.minute)
                # 단순 케이스만 처리 (0 or 숫자)
                h = hour.replace("{", "").replace("}", "")
                m = minute.replace("{", "").replace("}", "")
                return f"매일 {h.zfill(2)}:{m.zfill(2)}"
            elif isinstance(schedule, timedelta):
                total = int(schedule.total_seconds())
                if total < 60:
                    return f"{total}초 주기"
                elif total < 3600:
                    return f"{total // 60}분 주기"
                else:
                    return f"{total // 3600}시간 주기"
        except Exception:
            pass
        return str(schedule)


    @staticmethod
    def get_status() -> dict:
        try:
            from app.celery_app.celery import celery_app
            inspect = celery_app.control.inspect(timeout=2.0)
            active  = inspect.active()
            stats   = inspect.stats()

            workers = []
            if stats:
                for w_name in stats:
                    active_tasks = active.get(w_name, []) if active else []
                    workers.append({
                        "name":         w_name,
                        "status":       "online",
                        "active_tasks": len(active_tasks),
                    })

            beat_schedule = {}
            try:
                beat_schedule = {
                    k: SchedulerService._format_schedule(v.get("schedule"))
                    for k, v in celery_app.conf.beat_schedule.items()
                }
            except Exception:
                pass

            return {
                "workers":       workers,
                "worker_count":  len(workers),
                "beat_schedule": beat_schedule,
                "broker":        celery_app.conf.broker_url,
            }
        except Exception as e:
            logger.warning(f"Celery 상태 조회 실패: {e}")
            return {
                "workers":       [],
                "worker_count":  0,
                "beat_schedule": {},
                "error":         str(e),
            }


    # --- 수동 보고서 즉시 실행 ---
    @staticmethod
    def trigger_daily_report() -> dict:
        try:
            from app.celery_app.celery import celery_app
            task = celery_app.send_task("app.celery_app.tasks.run_daily_report")
            logger.info(f"보고서 즉시 실행 요청: task_id={task.id}")
            return {"task_id": task.id, "message": "보고서 생성 태스크가 시작되었습니다."}
        except Exception as e:
            logger.error(f"보고서 즉시 실행 실패: {e}")
            raise RuntimeError(f"보고서 태스크 실행 실패: {e}")


    # --- 크롤러 즉시 실행 ---
    @staticmethod
    def trigger_crawler() -> dict:
        try:
            from app.celery_app.celery import celery_app
            task = celery_app.send_task("app.celery_app.tasks.run_crawler")
            logger.info(f"크롤러 즉시 실행 요청: task_id={task.id}")
            return {"task_id": task.id, "message": "크롤러 태스크가 시작되었습니다."}
        except Exception as e:
            logger.error(f"크롤러 즉시 실행 실패: {e}")
            raise RuntimeError(f"크롤러 태스크 실행 실패: {e}")


    # --- 데이터 정리 즉시 실행 ---
    @staticmethod
    def trigger_cleanup() -> dict:
        try:
            from app.celery_app.celery import celery_app
            task = celery_app.send_task("app.celery_app.tasks.run_cleanup")
            logger.info(f"데이터 정리 즉시 실행 요청: task_id={task.id}")
            return {"task_id": task.id, "message": "데이터 정리 태스크가 시작되었습니다."}
        except Exception as e:
            logger.error(f"데이터 정리 즉시 실행 실패: {e}")
            raise RuntimeError(f"데이터 정리 태스크 실행 실패: {e}")


    # --- Sheets→DB 동기화 설정 조회 ---
    @staticmethod
    def get_sync_config(db: Session) -> dict:
        from app.db.repository import get_setting
        enabled  = get_setting(db, "SHEETS_SYNC_ENABLED", "true").lower() == "true"
        interval = int(get_setting(db, "SHEETS_SYNC_INTERVAL_MINUTES", "15"))
        return {
            "enabled":          enabled,
            "interval_minutes": interval,
            "description":      "Celery Beat 자동 동기화 (Beat 재시작 후 주기 변경 적용)",
        }


    # --- Sheets→DB 동기화 설정 저장 ---
    @staticmethod
    def update_sync_config(db: Session, enabled: bool, username: str) -> dict:
        from app.db.repository import upsert_setting
        upsert_setting(db, "SHEETS_SYNC_ENABLED", "true" if enabled else "false",
                       "Sheets→DB 자동 동기화 활성화")
        logger.info(f"Sheets→DB 동기화 {'활성화' if enabled else '비활성화'}: by {username}")
        return {"enabled": enabled, "message": "동기화 설정이 저장되었습니다."}


    # --- 수동 즉시 동기화 ---
    @staticmethod
    def trigger_sync() -> dict:
        try:
            from app.celery_app.celery import celery_app
            task = celery_app.send_task("app.celery_app.tasks.run_sync_sheets_to_db")
            logger.info(f"수동 동기화 요청: task_id={task.id}")
            return {"task_id": task.id, "message": "동기화 태스크가 시작되었습니다."}
        except Exception as e:
            logger.error(f"수동 동기화 요청 실패: {e}")
            raise RuntimeError(f"동기화 태스크 실행 실패: {e}")


    # --- Sheets→DB 동기화 중지 ---
    @staticmethod
    def stop_sync() -> dict:
        global _sync_scheduler
        try:
            if _sync_scheduler and getattr(_sync_scheduler, "running", False):
                _sync_scheduler.shutdown(wait=False)
                _sync_scheduler = None
                logger.info("Sheets→DB 주기 동기화 중지")
                return {"status": "stopped"}
        except Exception as e:
            logger.warning(f"스케줄러 중지 실패(무시): {e}")
            _sync_scheduler = None
        return {"status": "already_stopped"}