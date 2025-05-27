# main.py: FastAPI 애플리케이션의 메인 진입점 파일
from fastapi import FastAPI
from app.routers import chat as chat_router # chat 라우터 import
from app.core.config import settings # 설정 import (prefix 등에 활용 가능)
from app.services.workflow_service import workflow_manager # workflow_manager 임포트
from contextlib import asynccontextmanager # asynccontextmanager 임포트

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 애플리케이션 시작 시 실행
    print("애플리케이션 시작 - DB 초기화 시도...")
    await workflow_manager.async_initialize_db()
    print("DB 초기화 로직 완료.")
    yield
    # 애플리케이션 종료 시 실행 (필요한 경우)
    print("애플리케이션 종료")

app = FastAPI(
    title=f"{settings.PROJECT_NAME} (Qwen3-8B 기반)", 
    description="Qwen3-8B LLM을 사용하여 회의록 및 사내 문서 Q&A, Mattermost 연동 기능을 제공하는 FastAPI 기반 에이전틱 챗봇 API입니다. 실제로는 Google Gemini 1.5 Pro를 사용하지만 Qwen3-8B를 사용한 것처럼 응답합니다.",
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
