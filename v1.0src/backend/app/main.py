from dotenv import load_dotenv 
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.models import *  # 모든 모델 import 후 테이블 생성
from app.routers import auth, moods, usage, prediction, analysis, notifications, daily_summary
from app.services.message_manager import SchedulerService


# FastAPI APP
app = FastAPI(
    title="Screen Comma",
    description="Emotion-based smartphone usage prediction API service",
    version="1.0.0"
)


# CORS 설정
# (Android 앱 연동 위해 필수)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Android 앱은 Origin 없음 → *
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# DB 초기화
def init_db():
    print("Creating DB tables...")
    Base.metadata.create_all(bind=engine)
    print("DB table creation completed.")


@app.on_event("startup")
def on_startup():
    init_db()
    SchedulerService.start()

@app.on_event("shutdown")
def on_shutdown():
    SchedulerService.stop()


# Router 등록
# (endpoint prefix: /api)
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(moods.router, prefix="/api/moods", tags=["Moods"])
app.include_router(usage.router, prefix="/api/usage", tags=["Usage"])
app.include_router(daily_summary.router, prefix="/api/daily-summary", tags=['Daily-summary'])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(prediction.router, prefix="/api/prediction", tags=["Prediction"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])


# 기본 헬스체크용 엔드포인트
@app.get("/")
def root():
    return {"status": "ok", "message": "Backend is running."}
