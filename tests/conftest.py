import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  # registra todos los mappers
from app.core.database import Base


@pytest.fixture()
def sesion() -> Session:
    motor = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(motor)
    fabrica = sessionmaker(bind=motor, expire_on_commit=False)
    with fabrica() as session:
        yield session
    Base.metadata.drop_all(motor)
    motor.dispose()

