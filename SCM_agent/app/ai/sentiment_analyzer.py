
from transformers import pipeline, Pipeline
from loguru import logger
from typing import Optional
from app.config import settings


# 최초 1회
_sentiment_pipeline: Optional[Pipeline] = None


def get_sentiment_pipeline() -> Pipeline:

    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        logger.info(f"################## HuggingFace 모델 로딩 중: {settings.hf_model_name} ##################")
        try:
            _sentiment_pipeline = pipeline(
                task="text-classification",
                model=settings.hf_model_name,
                tokenizer=settings.hf_model_name,
                top_k=None,       # 전체 클래스 확률 반환
            )
            logger.info("################## HuggingFace 모델 로딩 완료 ##################")
        except Exception as e:
            logger.error(f"################## HuggingFace 모델 로딩 실패: {e} ##################")
            raise
    return _sentiment_pipeline


def analyze_sentiment(text: str) -> dict:

    try:
        pipe = get_sentiment_pipeline()
        results = pipe(text[:512])   # 토큰 길이 제한

        # top_k=None 이면 리스트 안에 리스트
        scores = results[0] if isinstance(results[0], list) else results

        # 가장 높은 확률 레이블 선택
        top = max(scores, key=lambda x: x["score"])
        label_map = {
            "positive": "긍정",
            "negative": "부정",
            "neutral":  "중립",
            # KR-FinBert 레이블 대응
            "LABEL_0": "부정",
            "LABEL_1": "중립",
            "LABEL_2": "긍정",
        }
        label_kor = label_map.get(top["label"].lower(), top["label"])

        return {
            "label": label_kor,
            "score": round(top["score"], 4),
            "all_scores": scores,
        }
    except Exception as e:
        logger.error(f"################## 감성 분석 실패 (text={text[:30]}...): {e} ##################")
        return {"label": "분석실패", "score": 0.0, "all_scores": []}


def analyze_sales_anomaly_sentiment(
        product_name: str,
        anomaly_type: str,
        change_rate: float,
) -> dict:

    if anomaly_type in ("sales_surge", "SALES_SURGE"):
        text = (
            f"{product_name} 상품의 판매량이 전주 대비 {abs(change_rate):.1f}% 급등했습니다. "
            f"매출 급등으로 재고 소진 가능성이 높습니다."
        )
    else:
        text = (
            f"{product_name} 상품의 판매량이 전주 대비 {abs(change_rate):.1f}% 급락했습니다. "
            f"수요 급락으로 재고 과잉 우려가 있습니다."
        )

    result = analyze_sentiment(text)

    if anomaly_type in ("sales_surge", "SALES_SURGE"):
        result["interpretation"] = (
            f"판매 급등 신호 ({result['label']}, 확률 {result['score']*100:.1f}%) — "
            f"!! 긴급 재고 확보 검토 필요 !!"
        )
    else:
        result["interpretation"] = (
            f"판매 급락 신호 ({result['label']}, 확률 {result['score']*100:.1f}%) — "
            f"!! 프로모션 또는 재고 조정 검토 필요 !!"
        )

    logger.info(f"################## 감성 분석 완료: {product_name} → {result['label']} ({result['score']}) ##################")
    return result


def batch_analyze_sales_anomalies(anomalies: list[dict]) -> list[dict]:

    logger.info(f"################## 일괄 감성 분석 시작: {len(anomalies)}건 ##################")
    enriched = []

    for item in anomalies:
        sentiment = analyze_sales_anomaly_sentiment(
            product_name=item["product_name"],
            anomaly_type=item["anomaly_type"],
            change_rate=item.get("change_rate", 0.0),
        )
        enriched.append({**item, "sentiment": sentiment})

    logger.info("################## 일괄 감성 분석 완료 ##################")
    return enriched