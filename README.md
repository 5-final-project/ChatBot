# 에이전틱 챗봇 API (Agentic Chatbot API)

Google Gemini 1.5 Pro LLM을 사용하여 회의록 및 사내 문서 Q&A, Mattermost 연동 기능을 제공하는 FastAPI 기반 에이전틱 챗봇 API입니다.

## 주요 기능

-   문서 기반 질의응답 (Q&A)
-   Mattermost를 통한 회의록 전송
-   사용자 질의 의도 자동 분류
-   LLM 추론 과정 로깅 및 프론트엔드 제공

## 기술 스택

-   Python
-   FastAPI
-   Google Gemini 1.5 Pro
-   Mattermost API
-   (예정) AWS S3, OpenSearch, SQL Database

## 설정 방법

1.  **저장소 복제:**
    ```bash
    git clone <repository_url>
    cd <repository_name>
    ```

2.  **가상 환경 생성 및 활성화:**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **의존성 설치:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **환경 변수 설정:**
    `.env.example` 파일을 복사하여 `.env` 파일을 생성하고, 필요한 API 키 및 설정 값을 입력합니다.
    ```bash
    cp .env.example .env
    # .env 파일 내용 수정
    ```

    필요한 환경 변수:
    -   `GOOGLE_API_KEY`: Google Gemini API 키
    -   `MATTERMOST_URL`: Mattermost 서버 URL
    -   `MATTERMOST_BOT_TOKEN`: Mattermost 봇 API 토큰
    -   (추후 추가) `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `S3_BUCKET_NAME`, `OPENSEARCH_HOST` 등

5.  **애플리케이션 실행:**
    ```bash
    uvicorn main:app --reload
    ```
    애플리케이션은 기본적으로 `http://127.0.0.1:8000` 에서 실행됩니다.

## API 엔드포인트

-   `POST /chat`: 사용자 질의를 받아 처리하고 응답을 반환합니다.

## 프로젝트 구조 (예시)

```
.
├── app/                  # 핵심 애플리케이션 로직
│   ├── __init__.py
│   ├── core/             # 설정, 공통 유틸리티 등
│   │   ├── __init__.py
│   │   └── config.py     # 환경 변수 및 설정 관리
│   ├── models/           # Pydantic 모델 (데이터 유효성 검사)
│   │   └── __init__.py
│   ├── routers/          # API 엔드포인트 정의
│   │   ├── __init__.py
│   │   └── chat.py       # 채팅 관련 라우터
│   ├── services/         # 비즈니스 로직 (LLM, Mattermost, DB 연동)
│   │   ├── __init__.py
│   │   ├── llm_service.py
│   │   ├── mattermost_service.py
│   │   └── workflow_service.py
│   └── schemas/          # API 요청/응답 스키마 (Pydantic 모델)
│       └── __init__.py
├── tests/                # 테스트 코드
├── .env                  # (Git에 포함되지 않음) 실제 환경 변수
├── .env.example          # 환경 변수 템플릿
├── .gitignore
├── main.py               # FastAPI 애플리케이션 진입점
├── README.md
└── requirements.txt
```
