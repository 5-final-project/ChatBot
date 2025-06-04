from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import time
import os
import logging
from app.core.config import settings
from app.routers import chat, health, document, agent, rag

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME, 
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# CORS 설정
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:8080",
    "*",  # 개발 환경에서 모든 출처 허용 (프로덕션에서는 제거하고 실제 도메인으로 대체)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 요청 처리 시간 측정 미들웨어
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# 정적 파일 서빙 설정
# 시각화 이미지 폴더 생성
visualizations_dir = os.path.join(os.getcwd(), "static", "visualizations")
os.makedirs(visualizations_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 라우터 설정
app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}/chat")
app.include_router(document.router, prefix=f"{settings.API_V1_STR}/document")
app.include_router(agent.router, prefix=f"{settings.API_V1_STR}/agent")
app.include_router(rag.router, prefix=f"{settings.API_V1_STR}/rag")

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Welcome to Financial Regulatory Compliance Chatbot API"}

# 전역 예외 처리
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "내부 서버 오류가 발생했습니다. 관리자에게 문의하세요."}
    ) 