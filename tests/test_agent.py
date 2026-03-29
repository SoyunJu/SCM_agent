"""
AI 툴 단위 테스트
- _get_anomalies 만 내부에서 SessionLocal local import
"""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock


def test_get_low_stock_tool_no_data():
    """재고 부족 없는 경우 — 문자열 반환 확인"""
    with patch("app.ai.tools.read_product_master", return_value=pd.DataFrame({
        "상품코드": ["P001"], "상품명": ["상품A"],
        "카테고리": ["Books"], "안전재고기준": [10],
    })), \
            patch("app.ai.tools.read_stock", return_value=pd.DataFrame({
                "상품코드": ["P001"], "현재재고": [50],
                "입고예정일": ["2026-04-01"], "입고예정수량": [100],
            })), \
            patch("app.ai.tools.read_sales", return_value=pd.DataFrame(
                columns=["날짜", "상품코드", "판매수량", "매출액"]
            )):
        from app.ai.tools import get_low_stock
        result = get_low_stock.invoke("")
        assert isinstance(result, str)


def test_get_top_sales_tool():
    """판매 상위 상품 조회 — 결과 포함 확인"""
    with patch("app.ai.tools.read_product_master", return_value=pd.DataFrame({
        "상품코드": ["P001"], "상품명": ["상품A"],
        "카테고리": ["Books"], "안전재고기준": [10],
    })), \
            patch("app.ai.tools.read_sales", return_value=pd.DataFrame({
                "날짜": ["2026-03-25"], "상품코드": ["P001"],
                "판매수량": [10], "매출액": [150000],
            })):
        from app.ai.tools import get_top_sales_tool
        result = get_top_sales_tool.invoke("7")
        assert isinstance(result, str)


def test_get_stock_by_product_not_found():
    """존재하지 않는 상품 조회 — '찾을 수 없습니다' 포함 확인"""
    with patch("app.ai.tools.read_product_master", return_value=pd.DataFrame({
        "상품코드": ["P001"], "상품명": ["상품A"],
        "카테고리": ["Books"], "안전재고기준": [10],
    })), \
            patch("app.ai.tools.read_stock", return_value=pd.DataFrame({
                "상품코드": ["P001"], "현재재고": [50],
                "입고예정일": ["2026-04-01"], "입고예정수량": [100],
            })):
        from app.ai.tools import get_stock_by_product
        result = get_stock_by_product.invoke("없는상품")
        assert "찾을 수 없습니다" in result


def test_run_agent_openai_unavailable():
    """OpenAI 미연결 시 오류 메시지 반환 확인"""
    with patch("app.ai.agent.ChatOpenAI") as mock_llm, \
            patch("app.ai.agent.get_chat_history", return_value=[]), \
            patch("app.ai.agent.save_chat_message"):
        mock_llm.side_effect = Exception("API key not set")
        from app.ai.agent import run_agent
        result = run_agent("재고 알려줘", "test_session", "test_user")
        assert "오류" in result