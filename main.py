# main.py: FastAPI 애플리케이션의 메인 진입점 파일
import logging # logging 임포트 추가
from fastapi import FastAPI
from app.routers import chat as chat_router # chat 라우터 import
from app.core.config import settings # 설정 import (prefix 등에 활용 가능)
from app.services.workflow.workflow_manager import workflow_manager # workflow_manager 임포트
from contextlib import asynccontextmanager # asynccontextmanager 임포트

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 애플리케이션 시작 시 실행
    # 기본 로깅 설정 (레벨 INFO 이상)
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__) # logger 인스턴스 생성

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
        }
    ]
)

# 루트 엔드포인트
@app.get("/")
async def read_root():
    return {"message": f"{settings.PROJECT_NAME}에 오신 것을 환영합니다!"}

# 채팅 라우터 추가
# tags를 명시적으로 지정하지 않고 라우터에서만 설정
app.include_router(chat_router.router, prefix=f"{settings.API_V1_STR}/chat")

if __name__ == "__main__":
    import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=8000) # Dockerfile/docker-compose에서 실행하므로 주석 처리 또는 개발용으로 남김
    # 개발 시 직접 실행을 원할 경우 위 주석을 해제하거나 아래와 같이 사용:
    uvicorn.run("main:app", host="0.0.0.0", port=8126, reload=True) # 포트 변경
