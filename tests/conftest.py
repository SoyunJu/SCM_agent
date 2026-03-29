from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


TEST_DB_URL = "sqlite://"   # in-memory


@pytest.fixture(scope="session")
def engine():
    _engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,   # 모든 커넥션이 동일 물리 연결 재사용
    )
    from app.db.models import Base
    Base.metadata.create_all(bind=_engine)
    yield _engine
    Base.metadata.drop_all(bind=_engine)
    _engine.dispose()


@pytest.fixture(scope="session")
def TestingSessionLocal(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="function")
def db_session(TestingSessionLocal):
    session = TestingSessionLocal()
    yield session
    session.rollback()
    from app.db.models import (
        AnomalyLog, OrderProposal, ReportExecution, AnalysisCache,
        DailySales, StockLevel, ChatHistory, ScheduleConfig,
        Product, AdminUser, SystemSettings,
    )
    for model in [
        AnomalyLog, OrderProposal, ReportExecution, AnalysisCache,
        DailySales, StockLevel, ChatHistory, ScheduleConfig,
        Product, AdminUser, SystemSettings,
    ]:
        try:
            session.query(model).delete()
            session.commit()
        except Exception:
            session.rollback()
    session.close()


@pytest.fixture(scope="session")
def app(engine, TestingSessionLocal):
    patches = [
        patch("app.cache.redis_client.cache_get",      return_value=None),
        patch("app.cache.redis_client.cache_set",      return_value=None),
        patch("app.cache.redis_client.cache_delete",   return_value=None),
        patch("app.notifier.slack_notifier.get_slack_client", return_value=MagicMock()),
        patch("app.celery_app.celery.celery_app.send_task",
              return_value=MagicMock(id="mock-task-id")),
    ]
    for p in patches:
        p.start()

    import app.db.connection as db_conn
    db_conn.engine = engine
    db_conn.SessionLocal = TestingSessionLocal

    from app.main import app as _app
    from app.db.connection import get_db
    from app.api.auth_router import get_current_user, require_admin, TokenData

    admin_user = TokenData(username="test_admin", role="admin")

    #    세션을 매번 새로 만들지 않고 같은 factory에서 생성
    #   → StaticPool이므로 물리 커넥션은 동일, 단 세션 캐시는 독립
    #   → seed_products에서 commit()하면 다른 세션에서도 읽힘
    def _get_test_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    _app.dependency_overrides[get_db]           = _get_test_db
    _app.dependency_overrides[get_current_user]  = lambda: admin_user
    _app.dependency_overrides[require_admin]     = lambda: admin_user

    yield _app

    for p in patches:
        p.stop()


@pytest.fixture(scope="session")
def client(app):
    return TestClient(app, raise_server_exceptions=False)


# ── 시드 데이터 ───────────────────────────────────────────────────────────────
@pytest.fixture(scope="function")
def seed_products(db_session):
    from app.db.models import Product, ProductStatus
    products = [
        Product(code="P001", name="상품A", category="카테고리1",
                safety_stock=10, status=ProductStatus.ACTIVE),
        Product(code="P002", name="상품B", category="카테고리1",
                safety_stock=5,  status=ProductStatus.ACTIVE),
        Product(code="P003", name="상품C", category="카테고리2",
                safety_stock=20, status=ProductStatus.INACTIVE),
    ]
    db_session.add_all(products)
    db_session.commit()
    db_session.expunge_all()
    return products


@pytest.fixture(scope="function")
def seed_stock(db_session, seed_products):
    from app.db.models import StockLevel
    stocks = [
        StockLevel(product_code="P001", current_stock=3,   restock_qty=50),
        StockLevel(product_code="P002", current_stock=100, restock_qty=0),
        StockLevel(product_code="P003", current_stock=60,  restock_qty=0),
    ]
    db_session.add_all(stocks)
    db_session.commit()
    db_session.expunge_all()
    return stocks


@pytest.fixture(scope="function")
def seed_sales(db_session, seed_products):
    from app.db.models import DailySales
    from datetime import date, timedelta
    today = date.today()
    sales = []
    for i in range(7):
        d = today - timedelta(days=i)
        sales.append(DailySales(date=d, product_code="P001",
                                qty=5,  revenue=50000.0, cost=30000.0))
        sales.append(DailySales(date=d, product_code="P002",
                                qty=10, revenue=100000.0, cost=60000.0))
    db_session.add_all(sales)
    db_session.commit()
    db_session.expunge_all()
    return sales


@pytest.fixture(scope="function")
def seed_anomalies(db_session, seed_products):
    from app.db.models import AnomalyLog, AnomalyType, Severity
    anomalies = [
        AnomalyLog(
            product_code="P001", product_name="상품A", category="카테고리1",
            anomaly_type=AnomalyType.LOW_STOCK, severity=Severity.CRITICAL,
            current_stock=3, daily_avg_sales=5.0, days_until_stockout=0.6,
            is_resolved=False,
        ),
        AnomalyLog(
            product_code="P002", product_name="상품B", category="카테고리1",
            anomaly_type=AnomalyType.OVER_STOCK, severity=Severity.LOW,
            current_stock=100, is_resolved=False,
        ),
        AnomalyLog(
            product_code="P001", product_name="상품A", category="카테고리1",
            anomaly_type=AnomalyType.SALES_SURGE, severity=Severity.HIGH,
            is_resolved=True,
        ),
    ]
    db_session.add_all(anomalies)
    db_session.commit()
    db_session.expunge_all()
    return anomalies


@pytest.fixture(scope="function")
def seed_proposals(db_session, seed_products):
    from app.db.models import OrderProposal, ProposalStatus
    proposals = [
        OrderProposal(
            product_code="P001", product_name="상품A", category="카테고리1",
            proposed_qty=50, unit_price=6000.0,
            reason="재고 3개 / 일평균 5.0개 / 리드타임 14일",
            status=ProposalStatus.PENDING,
        ),
        OrderProposal(
            product_code="P002", product_name="상품B", category="카테고리1",
            proposed_qty=20, unit_price=4000.0,
            reason="재고 100개 / 일평균 10.0개 / 리드타임 14일",
            status=ProposalStatus.APPROVED,
            approved_by="test_admin",
        ),
    ]
    db_session.add_all(proposals)
    db_session.commit()
    db_session.expunge_all()
    return proposals