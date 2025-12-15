from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

# DB 접속 정보
DB_USER = "dbid253"
DB_PASSWORD = "dbpass253"
DB_HOST = "localhost"
DB_NAME = "db25342"

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{DB_NAME}"
    "?charset=utf8mb4"
)

# Engine 생성
# pool_pre_ping=True → 연결 끊김 자동 복구
# pool_recycle=3600 → 1시간마다 재연결
# pool_size=10 → 최대 동시 연결 수
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
    poolclass=QueuePool,
)

# 세션 팩토리
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base 클래스 (모든 모델이 상속)
Base = declarative_base()

# Dependency - API에서 DB 세션 생성/닫기
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()