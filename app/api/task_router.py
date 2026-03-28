from typing import Annotated

from celery import states
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.api.auth_router import TokenData, get_current_user
from fastapi import Depends

router = APIRouter(prefix="/scm/tasks", tags=["tasks"])

_STATUS_MSG = {
    states.PENDING:  "분석 대기 중",
    states.STARTED:  "분석 진행 중",
    states.SUCCESS:  "분석 완료",
    states.FAILURE:  "분석 실패",
    states.REVOKED:  "작업 취소됨",
    states.RETRY:    "재시도 중",
}


@router.get("/{task_id}/status")
async def get_task_status(
        task_id: str,
        current_user: Annotated[TokenData, Depends(get_current_user)],
):

    try:
        from app.celery_app.celery import celery_app
        async_result = celery_app.AsyncResult(task_id)
        state   = async_result.state
        message = _STATUS_MSG.get(state, state)

        base = {"task_id": task_id, "state": state, "message": message}

        if state == states.SUCCESS:
            base["result"] = async_result.result
        elif state == states.FAILURE:
            meta = async_result.info or {}
            base["error"] = str(meta.get("error", async_result.result))
        elif state == states.STARTED:
            meta = async_result.info or {}
            base["progress"] = meta.get("status", "")

        return base

    except Exception as exc:
        logger.error(f"[태스크상태] 조회 실패 task_id={task_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"태스크 상태 조회 중 오류 발생: {exc}")
