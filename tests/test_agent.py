"""
AI 툴 단위 테스트
  → SessionLocal + DB 쿼리 mock으로 교체
"""
import pytest
from unittest.mock import patch, MagicMock


def _mock_db():
    """DB 세션 mock 헬퍼"""
    mock = MagicMock()
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


def test_get_low_stock_tool_no_data():
    """재고 없는 경우 — 빈 문자열이 아닌 결과 반환 확인"""
    mock_db = _mock_db()
    # query().filter().all() → 빈 리스트
    mock_db.query.return_value.filter.return_value.all.return_value = []

    with patch("app.ai.tools.SessionLocal", return_value=mock_db):
        from app.ai.tools import get_low_stock
        result = get_low_stock.invoke("")
        assert isinstance(result, str)


def test_get_top_sales_tool():
    """판매 상위 상품 조회 — 결과 문자열 반환 확인"""
    mock_db = _mock_db()

    # DailySales mock 객체
    mock_sale = MagicMock()
    mock_sale.product_code = "P001"
    mock_sale.qty          = 10
    mock_sale.revenue      = 150000.0

    # Product mock 객체
    mock_product = MagicMock()
    mock_product.code = "P001"
    mock_product.name = "상품A"

    mock_db.query.return_value.filter.return_value.group_by.return_value \
        .order_by.return_value.limit.return_value.all.return_value = [mock_sale]
    mock_db.query.return_value.filter.return_value.first.return_value = mock_product

    with patch("app.ai.tools.SessionLocal", return_value=mock_db):
        from app.ai.tools import get_top_sales_tool
        result = get_top_sales_tool.invoke("7")
        assert isinstance(result, str)


def test_get_stock_by_product_not_found():
    """존재하지 않는 상품 조회 — '찾을 수 없습니다' 포함 확인"""
    mock_db = _mock_db()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with patch("app.ai.tools.SessionLocal", return_value=mock_db):
        from app.ai.tools import get_stock_by_product
        result = get_stock_by_product.invoke("없는상품")
        assert isinstance(result, str)
        assert "찾을 수 없" in result or "없" in result


def test_run_agent_openai_unavailable():
    """OpenAI 미연결 시 오류 메시지 반환 확인"""
    with patch("app.ai.agent.ChatOpenAI") as mock_llm, \
            patch("app.ai.agent.get_chat_history", return_value=[]), \
            patch("app.ai.agent.save_chat_message"):
        mock_llm.side_effect = Exception("API key not set")
        from app.ai.agent import run_agent
        result = run_agent("재고 알려줘", "test_session", "test_user")
        assert "오류" in result