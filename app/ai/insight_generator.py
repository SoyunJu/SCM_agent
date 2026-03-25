
import json
from pathlib import Path
from openai import OpenAI
from loguru import logger
from app.config import settings


_client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def _load_prompt(filename: str) -> str:
    path = Path("prompts") / filename
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"프롬프트 파일 로드 실패 ({filename}): {e}")
        raise


def generate_daily_insight(
        stock_anomalies: list[dict],
        sales_anomalies: list[dict],
        total_products: int,
) -> dict:

    # 분석 데이터 summary
    analysis_data = {
        "total_products": total_products,
        "stock_anomalies": [
            {
                "product": a["product_name"],
                "type": a["anomaly_type"],
                "current_stock": a.get("current_stock"),
                "days_until_stockout": a.get("days_until_stockout"),
                "severity": a["severity"],
            }
            for a in stock_anomalies
        ],
        "sales_anomalies": [
            {
                "product": a["product_name"],
                "type": a["anomaly_type"],
                "change_rate": a.get("change_rate"),
                "severity": a["severity"],
                "sentiment": a.get("sentiment", {}).get("label", ""),
            }
            for a in sales_anomalies
        ],
    }

    prompt_template = _load_prompt("daily_report.txt")
    prompt = prompt_template.format(analysis_data=json.dumps(analysis_data, ensure_ascii=False))

    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=settings.openai_max_tokens,
            temperature=0.3,     # 일관된 톤 유지
            messages=[
                {"role": "system", "content": "당신은 재고 관리 전문가입니다. JSON 형식으로만 응답합니다."},
                {"role": "user", "content": prompt},
            ],
        )
        raw = response.choices[0].message.content.strip()
        logger.info("################## OpenAI 인사이트 생성 완료 ##################")
        return json.loads(raw)

    except json.JSONDecodeError as e:
        logger.error(f"################## OpenAI 응답 JSON 파싱 실패: {e} / 원문: {raw} ##################")
        return _fallback_insight(stock_anomalies, sales_anomalies)
    except Exception as e:
        logger.error(f"################## OpenAI API 호출 실패: {e} ##################")
        return _fallback_insight(stock_anomalies, sales_anomalies)


def _fallback_insight(stock_anomalies: list, sales_anomalies: list) -> dict:
    return {
        "overall_summary": f"재고 이상 {len(stock_anomalies)}건, 판매 이상 {len(sales_anomalies)}건이 감지되었습니다.",
        "key_issues": [a["product_name"] + " - " + a["anomaly_type"] for a in (stock_anomalies + sales_anomalies)[:3]],
        "recommendations": ["담당자 확인 필요"],
        "risk_level": "medium",
    }