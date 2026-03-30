
from pathlib import Path
from loguru import logger
from langchain.agents import AgentExecutor, create_react_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferWindowMemory

from app.config import settings
from app.ai.tools import (
    get_low_stock,
    get_top_sales_tool,
    get_stock_by_product,
    get_sales_trend_tool,
    get_anomalies,
    generate_report,
    get_demand_forecast_tool,
    approve_anomaly_orders,
    resolve_anomaly_tool,
    generate_order_proposals,
)
from app.db.connection import SessionLocal
from app.db.repository import save_chat_message, get_chat_history
from app.db.models import ChatRole


# ##### Tool List #####################
TOOLS = [
    get_low_stock,
    get_top_sales_tool,
    get_stock_by_product,
    get_sales_trend_tool,
    get_anomalies,
    generate_report,
    get_demand_forecast_tool,
    approve_anomaly_orders,
    resolve_anomaly_tool,
    generate_order_proposals,
]


def _load_prompt() -> str:
    path = Path("prompts/chat_agent.txt")
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"프롬프트 로드 실패: {e}")
        return "당신은 SCM Agent입니다. 재고와 판매 데이터를 분석하여 답변하세요."


def _build_react_prompt() -> PromptTemplate:

    system_prompt = _load_prompt()

    template = system_prompt + """

사용 가능한 Tool 목록:
{tools}

Tool 이름 목록: {tool_names}

## 반드시 지켜야 할 응답 형식
Question: 사용자 질문
Thought: 어떤 Tool을 써야 할지 생각
Action: Tool 이름 (반드시 tool_names 중 정확히 하나)
Action Input: Tool에 전달할 입력값 (따옴표 없이 순수 텍스트)
Observation: Tool 실행 결과
Thought: 결과를 보고 최종 답변을 도출할 수 있는지 판단
Final Answer: 최종 답변 (한국어, Observation 결과를 그대로 활용)

## 중요 규칙
- Observation 결과가 나오면 즉시 Final Answer로 답변하세요.
- 같은 Tool을 두 번 이상 호출하지 마세요.
- 데이터가 부족해도 Observation 결과로 Final Answer를 작성하세요.

이전 대화:
{chat_history}

Question: {input}
Thought: {agent_scratchpad}"""

    return PromptTemplate.from_template(template)


def run_agent(
        message: str,
        session_id: str,
        user_id: str,
) -> str:

    db = SessionLocal()
    try:
        # DB → LangChain Memory
        history_records = get_chat_history(db, session_id)
        memory = ConversationBufferWindowMemory(
            memory_key="chat_history",
            k=10,                   # 최근 10턴 유지
            return_messages=False,
        )
        for record in history_records:
            if record.role == ChatRole.USER:
                memory.chat_memory.add_user_message(record.message)
            else:
                memory.chat_memory.add_ai_message(record.message)

        #  Agent 구성
        llm = ChatOpenAI(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            temperature=0,
            max_tokens=settings.openai_max_tokens,
        )
        prompt    = _build_react_prompt()
        agent     = create_react_agent(llm=llm, tools=TOOLS, prompt=prompt)
        executor  = AgentExecutor(
            agent=agent,
            tools=TOOLS,
            memory=memory,
            verbose=True,                            # Tool 호출 과정 로그 출력
            max_iterations=3,                        # Tool 최대 5회 호출
            max_execution_time=30,                   # 30초 타임아웃
            early_stopping_method="generate",        # limit 도달 시 강제 Final Answer 생성
            handle_parsing_errors=True,
        )

        # Agent 실행
        logger.info(f"Agent 실행: session={session_id}, user={user_id}, msg={message[:50]}")
        result = executor.invoke({"input": message})
        reply  = result.get("output", "답변을 생성할 수 없습니다.")

        # 대화 이력 DB 저장
        save_chat_message(db, session_id, user_id, ChatRole.USER, message)
        save_chat_message(db, session_id, user_id, ChatRole.ASSISTANT, reply)

        logger.info(f"Agent 응답 완료: session={session_id}")
        return reply

    except Exception as e:
        logger.error(f"Agent 실행 오류: {e}")
        return f"처리 중 오류가 발생했습니다: {e}"
    finally:
        db.close()