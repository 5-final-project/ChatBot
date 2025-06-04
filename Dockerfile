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
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 시스템 패키지 업데이트 및 필수 라이브러리만 설치 (최소화)
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    gcc \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    xvfb \
    xauth \
    libxrender1 \
    libfontconfig1 \
    libxtst6 \
    fontconfig \
    fonts-nanum \
    fonts-noto-cjk \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 한글 폰트 설정
RUN fc-cache -fv && \
    echo "설치된 한글 폰트 목록:" && \
    fc-list :lang=ko

# pip 최신 버전으로 업그레이드
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 구 버전 패키지 제거 후 새 버전 설치
RUN pip uninstall -y google-generativeai || true
RUN pip install --no-cache-dir --force-reinstall "google-genai>=1.16.0"

# 패키지 버전 확인 (디버깅용)
RUN pip list | grep google

# requirements.txt 복사 및 종속성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# kaleido 패키지 명시적 설치 (종속성 문제 해결을 위해)
RUN pip uninstall -y kaleido || true
RUN pip install --no-cache-dir "kaleido==0.2.1" plotly>=5.18.0 --force-reinstall

# API 패키지가 다운그레이드되지 않도록 다시 확인
RUN pip install --no-cache-dir --force-reinstall "google-genai>=1.16.0"
RUN pip list | grep google

# 애플리케이션 소스 코드 복사 (필요한 파일만 복사)
COPY app/ ./app/
COPY main.py .

# 필요한 디렉토리 생성
RUN mkdir -p /app/logs /app/data /app/static/visualizations

# 포트 노출
EXPOSE 8126

# 헬스책 엔드포인트 정의
HEALTHCHECK CMD curl --fail http://localhost:8126/docs || exit 1

# 애플리케이션 실행 (Uvicorn 웹 서버)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8126", "--reload"]
