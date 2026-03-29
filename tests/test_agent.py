"""
AI 툴 단위 테스트
"""
import pytest
from unittest.mock import patch, MagicMock


def _make_mock_db():
    mock = MagicMock()
    return mock


def test_get_low_stock_tool_no_data():
    """재고 부족 없는 경우 — 문자열 반환 확인"""
    with patch("app.db.connection.SessionLocal") as mock_cls:
        mock_cls.return_value = _make_mock_db()

        from app.ai.tools import get_low_stock
        result = get_low_stock.invoke("")
        assert isinstance(result, str)


def test_get_top_sales_tool():
    """판매 상위 상품 조회 — 문자열 반환 확인"""
    with patch("app.db.connection.SessionLocal") as mock_cls:
        mock_cls.return_value = _make_mock_db()

        from app.ai.tools import get_top_sales_tool
        result = get_top_sales_tool.invoke("7")
        assert isinstance(result, str)


def test_get_stock_by_product_not_found():
    """존재하지 않는 상품 조회 — 문자열 반환 확인"""
    with patch("app.db.connection.SessionLocal") as mock_cls:
        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_cls.return_value = mock_db

        from app.ai.tools import get_stock_by_product
        result = get_stock_by_product.invoke("없는상품")
        assert isinstance(result, str)


def test_run_agent_openai_unavailable():
    """OpenAI 미연결 시 오류 메시지 반환 확인"""
    with patch("app.ai.agent.ChatOpenAI") as mock_llm, \
            patch("app.ai.agent.get_chat_history", return_value=[]), \
            patch("app.ai.agent.save_chat_message"):
        mock_llm.side_effect = Exception("API key not set")
        from app.ai.agent import run_agent
        result = run_agent("재고 알려줘", "test_session", "test_user")
        assert "오류" in result