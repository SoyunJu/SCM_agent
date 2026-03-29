from __future__ import annotations

from loguru import logger


class SlackService:

    @staticmethod
    def send_proposal(proposal) -> None:
        from app.notifier.slack_notifier import get_slack_client
        from app.config import settings
        from app.db.models import OrderProposal

        client  = get_slack_client()
        channel = settings.slack_channel_id

        try:
            resp = client.chat_postMessage(
                channel=channel,
                text=(
                    f"발주제안 #{proposal.id} | "
                    f"{proposal.product_code} {proposal.proposed_qty:,}개"
                ),
                blocks=SlackService._build_proposal_blocks(proposal),
            )

            proposal.slack_ts      = resp["ts"]
            proposal.slack_channel = channel
            logger.info(f"[SlackService] 발주제안 #{proposal.id} 전송 완료")
        except Exception as e:
            logger.warning(f"[SlackService] 발주제안 #{proposal.id} 전송 실패(스킵): {e}")

    @staticmethod
    def update_proposal_resolved(proposal) -> None:
        if not proposal.slack_ts or not proposal.slack_channel:
            return
        from app.notifier.slack_notifier import get_slack_client
        from app.db.models import ProposalStatus

        try:
            status_text = (
                "✅ 승인됨" if proposal.status == ProposalStatus.APPROVED
                else "❌ 거절됨"
            )
            price_str = (
                f"{proposal.unit_price:,.0f}원"
                if proposal.unit_price else "미입력"
            )
            approved_at = (
                proposal.approved_at.strftime("%Y-%m-%d %H:%M")
                if proposal.approved_at else ""
            )
            get_slack_client().chat_update(
                channel=proposal.slack_channel,
                ts=proposal.slack_ts,
                text=f"발주제안 #{proposal.id} — {proposal.status.value}",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"*[발주제안 #{proposal.id}]* "
                                f"`{proposal.product_code}` {proposal.product_name or ''}\n"
                                f"수량: {proposal.proposed_qty:,}개 | 단가: {price_str}\n"
                                f"*{status_text}* — "
                                f"{proposal.approved_by} ({approved_at})"
                            ),
                        },
                    },
                    {"type": "divider"},
                ],
            )
        except Exception as e:
            logger.warning(f"[SlackService] 메시지 업데이트 실패(스킵): {e}")

    @staticmethod
    def update_proposal_pending(proposal) -> None:
        if not proposal.slack_ts or not proposal.slack_channel:
            return
        from app.notifier.slack_notifier import get_slack_client

        try:
            get_slack_client().chat_update(
                channel=proposal.slack_channel,
                ts=proposal.slack_ts,
                text=(
                    f"발주제안 #{proposal.id} | "
                    f"{proposal.product_code} {proposal.proposed_qty:,}개 (수정됨)"
                ),
                blocks=SlackService._build_proposal_blocks(proposal),
            )
        except Exception as e:
            logger.warning(f"[SlackService] 수정 업데이트 실패(스킵): {e}")


    # --- 자동 승인 결과 통보 (버튼 없음) ---
    @staticmethod
    def send_auto_approved(proposal) -> None:
        from app.notifier.slack_notifier import get_slack_client
        from app.config import settings

        client  = get_slack_client()
        channel = settings.slack_channel_id

        try:
            resp = client.chat_postMessage(
                channel=channel,
                text=f"✅ [자동승인] 발주제안 #{proposal.id} | {proposal.product_code} {proposal.proposed_qty:,}개",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"✅ *자동 승인 완료* — 발주제안 #{proposal.id}\n"
                                f"상품: *{proposal.product_name}* (`{proposal.product_code}`)\n"
                                f"수량: *{proposal.proposed_qty:,}개* | "
                                f"단가: {proposal.unit_price:,.0f}원\n"
                                f"사유: {proposal.reason or '-'}"
                            ),
                        },
                    },
                    {"type": "context",
                     "elements": [{"type": "mrkdwn",
                                   "text": "SCM Agent 자동 승인 (AUTO_ORDER_APPROVAL=true)"}]},
                ],
            )
            proposal.slack_ts      = resp["ts"]
            proposal.slack_channel = channel
            logger.info(f"[SlackService] 자동승인 #{proposal.id} 전송 완료")
        except Exception as e:
            logger.warning(f"[SlackService] 자동승인 #{proposal.id} 전송 실패(스킵): {e}")


    # ── 블록 빌더 ─────────────────────────────────────────────────────

    @staticmethod
    def _build_proposal_blocks(proposal) -> list[dict]:
        price_str = (
            f"{proposal.unit_price:,.0f}원"
            if proposal.unit_price and proposal.unit_price > 0
            else "미입력"
        )
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*[발주제안 #{proposal.id}]* "
                        f"`{proposal.product_code}` {proposal.product_name or ''}\n"
                        f"카테고리: {proposal.category or '-'} | "
                        f"*제안수량: {proposal.proposed_qty:,}개* | "
                        f"단가: {price_str}\n"
                        f"_{proposal.reason or ''}_"
                    ),
                },
            },
            {
                "type": "actions",
                "block_id": f"proposal_actions_{proposal.id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ 승인"},
                        "style": "primary",
                        "action_id": "approve_proposal",
                        "value": str(proposal.id),
                        "confirm": {
                            "title":   {"type": "plain_text", "text": "승인 확인"},
                            "text":    {"type": "mrkdwn",
                                        "text": f"*{proposal.product_code}* "
                                                f"{proposal.proposed_qty:,}개 발주를 승인하시겠습니까?"},
                            "confirm": {"type": "plain_text", "text": "승인"},
                            "deny":    {"type": "plain_text", "text": "취소"},
                        },
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ 거절"},
                        "style": "danger",
                        "action_id": "reject_proposal",
                        "value": str(proposal.id),
                        "confirm": {
                            "title":   {"type": "plain_text", "text": "거절 확인"},
                            "text":    {"type": "mrkdwn",
                                        "text": "이 발주 제안을 거절하시겠습니까?"},
                            "confirm": {"type": "plain_text", "text": "거절"},
                            "deny":    {"type": "plain_text", "text": "취소"},
                        },
                    },
                ],
            },
            {"type": "divider"},
        ]