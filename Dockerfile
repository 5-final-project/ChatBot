# Dockerfile: FastAPI 기반 AI 채팅 애플리케이션을 위한 Docker 이미지 설정

# 최신 Python 3.11 베이스 이미지 사용 (보안 업데이트 반영)
FROM python:3.11-slim-bookworm

# 메타데이터 설정
LABEL maintainer="FISA AI Team"
LABEL description="AI 기반 Q&A 및 자동화 챗봇 시스템"

# 작업 디렉토리 설정
WORKDIR /app

# Python 환경 설정 (보안 강화 및 출력 버퍼링 비활성화)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    TZ=Asia/Seoul \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 비료트 사용자 생성 및 사용
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 시스템 패키지 업데이트 및 필수 라이브러리만 설치 (최소화)
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    gcc \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt 복사 및 종속성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 애플리케이션 소스 코드 복사 (필요한 파일만 복사)
COPY app/ ./app/
COPY main.py .

# 필요한 디렉토리 생성 및 권한 설정
RUN mkdir -p /app/logs /app/data && \
    chown -R appuser:appuser /app

# 비료트 사용자로 스위치
USER appuser

# 포트 노출
EXPOSE 8126

# 헬스책 엔드포인트 정의
HEALTHCHECK CMD curl --fail http://localhost:8126/docs || exit 1

# 애플리케이션 실행 (Uvicorn 웹 서버)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8126", "--reload"]
