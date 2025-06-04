# main.py: FastAPI 애플리케이션의 메인 진입점 파일
import logging # logging 임포트 추가
import os # os 임포트 추가
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # CORS 미들웨어 임포트 추가
from app.routers import chat as chat_router # chat 라우터 import
from app.core.config import settings # 설정 import (prefix 등에 활용 가능)
from app.services.workflow.workflow_manager import workflow_manager # workflow_manager 임포트
from contextlib import asynccontextmanager # asynccontextmanager 임포트
from fastapi.staticfiles import StaticFiles # 정적 파일 제공을 위한 임포트

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 애플리케이션 시작 시 실행
    # 향상된 로깅 설정
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("app.log", mode="a")
        ]
    )
    
    # 시각화 관련 모듈 로그 레벨 DEBUG로 설정
    visualization_loggers = [
        "app.services.visualization",
        "app.routers.visualization",
        "app.schemas.visualization"
    ]
    
    for logger_name in visualization_loggers:
        module_logger = logging.getLogger(logger_name)
        module_logger.setLevel(logging.DEBUG)
    
    # 플로틀리 및 kaleido 관련 로그 레벨 설정
    plotly_loggers = [
        "plotly", 
        "kaleido"
    ]
    
    for logger_name in plotly_loggers:
        plotly_logger = logging.getLogger(logger_name)
        plotly_logger.setLevel(logging.DEBUG)
    
    logger = logging.getLogger(__name__) # logger 인스턴스 생성
    
    # 시스템 환경 정보 로깅
    logger.info(f"운영체제: {os.name} - {os.sys.platform}")
    logger.info(f"Python 버전: {os.sys.version}")
    logger.info(f"작업 디렉토리: {os.getcwd()}")
    
    # 정적 파일 디렉토리 확인 및 생성
    static_dir = os.path.join(os.getcwd(), "static")
    visualization_dir = os.path.join(static_dir, "visualizations")
    
    os.makedirs(static_dir, exist_ok=True)
    os.makedirs(visualization_dir, exist_ok=True)
    
    logger.info(f"정적 파일 디렉토리 확인: {static_dir} (존재: {os.path.exists(static_dir)})")
    logger.info(f"시각화 디렉토리 확인: {visualization_dir} (존재: {os.path.exists(visualization_dir)})")

    logger.info("애플리케이션 시작 - DB 초기화 시도 직전 (main.py lifespan)")
    db_init_success = await workflow_manager.async_initialize_db()
    if db_init_success:
        logger.info("DB 초기화 성공 (main.py lifespan)")
    else:
        logger.error("DB 초기화 실패 (main.py lifespan)")
    logger.info("DB 초기화 로직 완료 후 (main.py lifespan)")
    yield
    # 애플리케이션 종료 시 실행 (필요한 경우)
    logger.info("애플리케이션 종료 (main.py lifespan)")

app = FastAPI(
    title=f"{settings.PROJECT_NAME} (Qwen3-8B 기반)", 
    description="Qwen3-8B LLM을 사용하여 회의록 및 사내 문서 Q&A, Mattermost 연동 기능을 제공하는 FastAPI 기반 에이전틱 챗봇 API입니다.",
    version="0.1.0",
    lifespan=lifespan, # lifespan 이벤트 핸들러 등록
    openapi_tags=[
        {
            "name": "chat",
            "description": "채팅 관련 엔드포인트"
        },
        {
            "name": "visualization",
            "description": "시각화 관련 엔드포인트"
        }
    ]
)

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 출처 허용 (개발 환경)
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 HTTP 헤더 허용
)

# 정적 파일 마운트
app.mount("/static", StaticFiles(directory="static"), name="static")

# 루트 엔드포인트
@app.get("/")
async def read_root():
    return {"message": f"{settings.PROJECT_NAME}에 오신 것을 환영합니다!"}

# 채팅 라우터 추가
# tags를 명시적으로 지정하지 않고 라우터에서만 설정
app.include_router(chat_router.router, prefix=f"{settings.API_V1_STR}/chat")

# 시각화 라우터 추가
# app.include_router(visualization_router.router, prefix=f"{settings.API_V1_STR}/visualization")

if __name__ == "__main__":
    import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=8000) # Dockerfile/docker-compose에서 실행하므로 주석 처리 또는 개발용으로 남김
    # 개발 시 직접 실행을 원할 경우 위 주석을 해제하거나 아래와 같이 사용:
    uvicorn.run("main:app", host="0.0.0.0", port=8126, reload=True) # 포트 변경
