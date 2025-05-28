# AI 기반 Q&A 및 자동화 챗봇 API

**버전:** 1.0.0
**최종 업데이트:** 2025-05-27

## 1. 프로젝트 개요

본 프로젝트는  QWEN-8B LLM을 기반으로 하는 FastAPI 웹 애플리케이션입니다. 주요 기능은 사내 문서 및 회의록에 대한 질의응답(Q&A)이며, Retriever-Augmented Generation (RAG) 기술을 활용하여 정확하고 관련성 높은 답변을 제공합니다. 또한, LLM의 추론 과정을 스트리밍하여 사용자에게 투명성을 제공하고, Mattermost와 연동하여 특정 업무 자동화 기능을 수행합니다.

**주요 목표:**

*   지능형 정보 검색 및 업무 자동화 기능 제공
*   고품질 Q&A 응답 생성
*   RAG 파이프라인을 통한 정보 접근성 강화
*   LLM 추론 과정의 투명한 시각화
*   선별적인 Mattermost 업무 자동화 (예: 회의록 요약 전송)
*   안정적이고 확장 가능한 시스템 구축
*   자동화된 테스트 및 배포 파이프라인 (Docker 활용)

## 2. 기술 스택

*   **프로그래밍 언어:** Python 3.9+
*   **웹 프레임워크:** FastAPI
*   **LLM:** QWEN-8B
*   **데이터 유효성 검사:** Pydantic
*   **비동기 처리:** `asyncio`, `httpx`
*   **RAG 백엔드 (예정/연동):** OpenSearch (또는 유사 벡터 DB)
*   **데이터베이스 (예정/연동):** PostgreSQL 또는 MySQL (Mattermost 사용자 정보 등 관리)
*   **메시징/협업:** Mattermost API
*   **컨테이너화:** Docker, Docker Compose
*   **CI/CD (기본 구성):** [entrypoint.sh](cci:7://file:///c:/ITStudy/CHAT/entrypoint.sh:0:0-0:0) 내 `pytest` 실행

```
## 3. 디렉토리 구조
c:\ITStudy\CHAT 
├── .env # (Git 무시) 실제 환경 변수 설정 파일 
├── .env.example # 환경 변수 설정 예시 파일 
├── .gitignore # Git 무시 파일 목록 
├── .pytest_cache/ # Pytest 캐시 디렉토리 
├── Dockerfile # Docker 이미지 빌드 설정 
├── README.md # 본 문서 
├── pycache/ # Python 컴파일 캐시 
├── app/ # 핵심 애플리케이션 로직 
│ ├── init.py 
│ ├── core/ # 설정, 공통 유틸리티, 로깅 등 
│ │ ├── init.py 
│ │ ├── config.py # 환경 변수 로드 및 애플리케이션 설정 관리 
│ │ └── logger.py # (예시) 로깅 설정 
│ ├── models/ # (현재 미사용, 필요시 DB 모델 정의) 
│ │ └── init.py 
│ ├── routers/ # API 엔드포인트(라우트) 정의 
│ │ ├── init.py 
│ │ └── chat.py # 채팅 관련 API 라우터 (/api/v1/chat/rag/stream) │ ├── schemas/ # Pydantic 스키마 (API 요청/응답 데이터 모델) │ │ ├── init.py │ │ └── chat.py # ChatRequest, LLMResponseChunk 등 정의 │ └── services/ # 비즈니스 로직 (핵심 기능 구현) │ ├── init.py │ ├── chat_history_service.py # 대화 기록 관리 서비스 │ ├── db_service.py # 데이터베이스 연동 서비스 (사용자 정보 등) │ ├── external_rag_service.py # 외부 RAG 서비스(OpenSearch) 연동 │ ├── llm_service.py # LLM(Gemini) API 연동 및 응답 생성 │ ├── mattermost_service.py # Mattermost API 연동 │ └── workflow_service.py # 전체 요청 처리 흐름(오케스트레이션) 관리 ├── data/ # (예시) 초기 데이터, 임시 파일 등 (현재는 비어있음) ├── docker-compose.yml # Docker Compose 설정 (서비스 실행 환경 정의) ├── entrypoint.sh # Docker 컨테이너 시작 시 실행되는 스크립트 ├── logs/ # (예시) 애플리케이션 로그 저장 디렉토리 ├── main.py # FastAPI 애플리케이션의 주 진입점 ├── manage_mattermost_users.py # Mattermost 사용자 관리 및 DB 동기화 스크립트 └── requirements.txt # Python 의존성 패키지 목록
```

## 4. 주요 파일 및 모듈 상세 설명

*   **[main.py](cci:7://file:///c:/ITStudy/CHAT/main.py:0:0-0:0)**: FastAPI 애플리케이션을 초기화하고, `app.routers.chat`에 정의된 API 라우터를 포함합니다. Uvicorn을 통해 실행됩니다.
*   **[Dockerfile](cci:7://file:///c:/ITStudy/CHAT/Dockerfile:0:0-0:0)**: Python 3.9 이미지를 기반으로 애플리케이션 실행 환경을 구성합니다. [requirements.txt](cci:7://file:///c:/ITStudy/CHAT/requirements.txt:0:0-0:0) 의존성을 설치하고, [entrypoint.sh](cci:7://file:///c:/ITStudy/CHAT/entrypoint.sh:0:0-0:0)를 실행합니다.
*   **[docker-compose.yml](cci:7://file:///c:/ITStudy/CHAT/docker-compose.yml:0:0-0:0)**: `api` 서비스를 정의하여 Docker 컨테이너를 빌드하고 실행합니다. 포트 매핑, 환경 변수 파일 로드, 볼륨 마운트 등을 설정합니다.
*   **[entrypoint.sh](cci:7://file:///c:/ITStudy/CHAT/entrypoint.sh:0:0-0:0)**: Docker 컨테이너 시작 시 실행됩니다. 주요 역할은 (1) Python 캐시 정리, (2) `pytest`를 사용한 자동 테스트 실행, (3) 테스트 성공 시 Uvicorn 웹 서버 시작입니다.
*   **`app/core/config.py`**: [.env](cci:7://file:///c:/ITStudy/CHAT/.env:0:0-0:0) 파일로부터 환경 변수를 로드하고, Pydantic 모델을 사용하여 애플리케이션 설정을 관리합니다.
*   **`app/schemas/chat.py`**: API 요청 및 응답에 사용되는 데이터 구조를 Pydantic 모델로 정의합니다.
    *   `ChatRequest`: 클라이언트로부터 받는 채팅 요청 스키마.
    *   `LLMResponseChunk`: 서버에서 클라이언트로 스트리밍되는 각 응답 조각의 스키마.
    *   `MessageType`: `LLMResponseChunk`의 `type` 필드에 사용되는 Enum (예: `CONTENT`, `LLM_REASONING_STEP`).
    *   `LLMReasoningStep`: LLM의 추론 과정을 나타내는 스키마.
    *   `RetrievedDocument`: RAG 검색 결과를 나타내는 스키마.
*   **`app/routers/chat.py`**: 채팅 관련 API 엔드포인트를 정의합니다. 핵심 엔드포인트는 `POST /api/v1/chat/rag/stream`입니다.
*   **`app/services/workflow_service.py`**: (`workflow_manager` 인스턴스)
    *   채팅 요청 처리의 전체적인 흐름을 관장하는 핵심 서비스입니다.
    *   `process_chat_request_stream` 메소드: 사용자 요청을 받아 의도 분류, RAG 검색 (필요시), LLM 질의, 응답 스트리밍까지의 과정을 오케스트레이션합니다.
*   **`app/services/llm_service.py`**: (`LLMService` 클래스)
    *   QWEN-8B과 통신합니다.
    *   `classify_intent`: 사용자 질의의 의도를 분류합니다.
    *   `generate_response_stream`: RAG 검색 결과 및 대화 히스토리를 바탕으로 LLM에게 답변 생성을 요청하고, 그 결과를 스트리밍 방식으로 반환합니다. LLM의 내부 추론 과정(`[THOUGHT]...[/THOUGHT]`)을 파싱하여 `LLMReasoningStep` 객체로 만듭니다.
*   **`app/services/external_rag_service.py`**: (`ExternalRAGService` 클래스)
    *   외부 벡터 데이터베이스(예: OpenSearch)와 통신하여 사용자 질의와 관련된 문서를 검색합니다.
    *   `search_documents`: `OPENSEARCH_API_URL` 환경 변수에 지정된 URL로 검색 요청을 보냅니다.
*   **`app/services/mattermost_service.py`**: (`MattermostService` 클래스)
    *   Mattermost API와 연동하여 메시지 전송 등의 기능을 수행합니다. (현재는 회의록 요약 전송 등 특정 기능에 초점)
    *   `MATTERMOST_URL`, `MATTERMOST_BOT_TOKEN` 환경 변수를 사용합니다.
*   **`app/services/db_service.py`**:
    *   데이터베이스(SQL) 연동 로직을 담당합니다. (예: Mattermost 사용자 이름과 ID 매핑 정보 저장/조회)
    *   [manage_mattermost_users.py](cci:7://file:///c:/ITStudy/CHAT/manage_mattermost_users.py:0:0-0:0) 스크립트와 함께 사용될 수 있습니다.
*   **`app/services/chat_history_service.py`**: (`ChatHistoryService` 클래스)
    *   세션별 대화 기록을 인메모리(또는 Redis 등)에 저장하고 관리합니다.
*   **[manage_mattermost_users.py](cci:7://file:///c:/ITStudy/CHAT/manage_mattermost_users.py:0:0-0:0)**: Mattermost 사용자 정보를 가져와 로컬 데이터베이스에 동기화하는 유틸리티 스크립트입니다. (메모리 참조)

## 5. 환경 변수 설정

프로젝트 루트의 [.env.example](cci:7://file:///c:/ITStudy/CHAT/.env.example:0:0-0:0) 파일을 복사하여 [.env](cci:7://file:///c:/ITStudy/CHAT/.env:0:0-0:0) 파일을 생성하고, 아래 환경 변수들을 실제 값으로 설정해야 합니다.

| 변수명                      | 설명                                                                 | 예시 값                                        | 필수 여부 |
| :-------------------------- | :------------------------------------------------------------------- | :--------------------------------------------- | :------ |
| `MATTERMOST_URL`            | 연동할 Mattermost 서버의 URL                                           | `https://team5mattermost.ap.loclx.i`           | 선택    |
| `MATTERMOST_BOT_TOKEN`      | Mattermost 봇 계정의 API 접근 토큰                                     | `gu61f5wkzfycu8e3pubu4y8mfc`                   | 선택    |
| `OPENSEARCH_API_URL`        | 외부 RAG 서비스(OpenSearch) API 엔드포인트 URL                         | `https://team5opensearch.ap.loclx.io/search`   | 선택    |
| `DB_TYPE`                   | 사용할 데이터베이스 종류 (미구현, 예정)                                | `postgresql`                                   | 선택    |
| `DB_HOST`                   | 데이터베이스 호스트 주소 (미구현, 예정)                                | `localhost`                                    | 선택    |
| `DB_PORT`                   | 데이터베이스 포트 (미구현, 예정)                                       | `5432`                                         | 선택    |
| `DB_USER`                   | 데이터베이스 사용자 이름 (미구현, 예정)                                | `admin`                                        | 선택    |
| `DB_PASSWORD`               | 데이터베이스 사용자 비밀번호 (미구현, 예정)                              | `password`                                     | 선택    |
| `DB_NAME`                   | 사용할 데이터베이스 이름 (미구현, 예정)                                | `chatbot_db`                                   | 선택    |
| `LOG_LEVEL`                 | 애플리케이션 로그 레벨                                                 | `INFO` (DEBUG, WARNING, ERROR 등)              | 선택    |
| `DEBUG`                     | 디버그 모드 활성화 여부 (오류 상세 정보 노출 등)                         | `True` 또는 `False`                            | 선택    |
| `PYTHONUNBUFFERED`          | Docker 환경에서 Python 출력 버퍼링 비활성화 (로그 즉시 확인용)         | `1`                                            | 권장    |
| `ENVIRONMENT`               | 실행 환경 (development, production 등)                               | `development`                                  | 선택    |

**참고:** `DB_*` 관련 변수들은 [manage_mattermost_users.py](cci:7://file:///c:/ITStudy/CHAT/manage_mattermost_users.py:0:0-0:0) 스크립트나 향후 DB 연동 기능 구현 시 사용됩니다. 현재 핵심 Q&A 기능에는 직접적인 영향이 없을 수 있습니다.

## 6. 실행 방법

### 6.1. Docker를 사용한 실행 (권장)

1.  Docker 및 Docker Compose가 설치되어 있는지 확인합니다.
2.  프로젝트 루트 디렉토리에서 [.env](cci:7://file:///c:/ITStudy/CHAT/.env:0:0-0:0) 파일이 올바르게 설정되었는지 확인합니다.
3.  다음 명령어를 실행하여 Docker 이미지를 빌드하고 컨테이너를 시작합니다:
    ```bash
    docker-compose up --build
    ```
    백그라운드 실행을 원할 경우 `-d` 옵션을 추가합니다:
    ```bash
    docker-compose up --build -d
    ```
4.  애플리케이션은 기본적으로 `http://localhost:8000` (또는 [docker-compose.yml](cci:7://file:///c:/ITStudy/CHAT/docker-compose.yml:0:0-0:0)에 설정된 포트)에서 실행됩니다.
5.  API 문서는 `http://localhost:8000/docs` 에서 확인할 수 있습니다.
6.  로그는 `docker-compose logs -f api` 명령어로 실시간 확인할 수 있습니다.

### 6.2. 로컬 개발 환경에서 실행

1.  Python 3.9 이상 버전이 설치되어 있는지 확인합니다.
2.  가상 환경을 생성하고 활성화합니다:
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```
3.  필요한 의존성 패키지를 설치합니다:
    ```bash
    pip install -r requirements.txt
    ```
4.  프로젝트 루트 디렉토리에 [.env](cci:7://file:///c:/ITStudy/CHAT/.env:0:0-0:0) 파일을 생성하고 환경 변수를 설정합니다.
5.  Uvicorn을 사용하여 FastAPI 애플리케이션을 실행합니다:
    ```bash
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```
    `--reload` 옵션은 코드 변경 시 자동으로 서버를 재시작합니다.

## 7. 허브 연동 가이드 (Hub Integration Guide)

본 섹션은 허브(또는 다른 외부 시스템) 담당자가 이 챗봇 API와 효과적으로 연동할 수 있도록 상세 정보를 제공합니다.

### 7.1. 핵심 API 엔드포인트: 스트리밍 채팅

*   **URL:** `POST /api/v1/chat/rag/stream`
*   **Method:** `POST`
*   **Content-Type:** `application/json`
*   **Response Media Type:** `text/event-stream` (Server-Sent Events, SSE)

#### 7.1.1. 요청 (Request)

요청 본문은 `app.schemas.chat.ChatRequest` Pydantic 모델을 따르는 JSON 객체여야 합니다.

**`ChatRequest` 스키마:**

```json
{
  "query": "string (필수, 사용자 질문)",
  "session_id": "string (선택, 없으면 서버에서 생성. 대화 연속성 유지에 사용)",
  "user_id": "string (선택, 사용자 식별자)",
  "search_in_meeting_documents_only": "boolean (선택, 기본값: false. True이면 회의록 문서 내에서만 검색)",
  "target_document_ids": "array[string] (선택, 특정 문서 ID 목록 내에서만 검색)",
  "meeting_context": { // 선택, 현재 대화의 회의 관련 문맥 정보
    "meeting_id": "string (선택, 회의 식별자)",
    "document_id": "string (선택, 현재 참조 중인 문서 식별자)",
    "participants": "array[string] (선택, 회의 참석자 목록)",
    "meeting_title": "string (선택, 회의 제목)"
  },
  "additional_params": "object (선택, 추가적인 매개변수 전달용)"
}
필드 설명:

query: 사용자의 실제 질문 내용입니다.
session_id: 동일한 사용자와의 대화 세션을 식별합니다. 이 ID를 기준으로 대화 히스토리 및 컨텍스트가 관리됩니다. 클라이언트에서 생성하여 전달하거나, 생략 시 서버에서 임의의 ID를 생성하여 첫 응답에 포함시켜 반환합니다.
user_id: 사용자 계정을 식별하는 ID입니다. (예: Mattermost 사용자 ID)
search_in_meeting_documents_only: true로 설정하면 RAG 검색 시 회의록 관련 문서만을 대상으로 합니다.
target_document_ids: 특정 문서 ID 목록을 제공하여 해당 문서들 내에서만 검색하도록 제한합니다.
meeting_context: 현재 대화가 특정 회의와 관련된 경우, 해당 회의의 ID, 관련 문서 ID, 참석자 등의 정보를 전달하여 더 정확한 답변을 유도할 수 있습니다.
additional_params: 향후 확장을 위해 예약된 필드입니다.
7.1.2. 응답 (Response - Server-Sent Events)
응답은 Server-Sent Events (SSE) 스트림으로 제공됩니다. 각 이벤트는 data: 로 시작하고 \n\n으로 끝나는 형식입니다. data: 다음에는 app.schemas.chat.LLMResponseChunk Pydantic 모델을 JSON 문자열로 직렬화한 값이 포함됩니다.

LLMResponseChunk 스키마:

json
CopyInsert
{
  "session_id": "string (요청 시 사용된 세션 ID 또는 서버 생성 ID)",
  "type": "string (MessageType Enum 값)",
  "content": "string (선택, type이 'CONTENT'일 때 실제 답변 내용 조각)",
  "data": "object (선택, type에 따라 다른 구조의 데이터 포함)",
  "timestamp": "string (ISO 8601 형식의 타임스탬프)"
}
MessageType Enum 값 및 data 필드 구조:

START: 스트리밍 시작을 알림.
data: {"session_id": "서버에서 생성된 경우 해당 ID"}
INTENT_CLASSIFIED: 사용자 질의의 의도 분류 결과를 알림.
data: {"intent": "분류된 의도명 (예: qna, greeting)", "entities": {"key": "value"}, "description": "의도 설명"}
THINKING: LLM 또는 RAG 시스템이 현재 처리 중인 단계를 알림.
data: {"step_description": "현재 처리 단계 설명 (예: RAG 검색 시작, 관련 문서 필터링 중)"}
RETRIEVED_DOCUMENT: (현재 기본 비활성화, 향후 사용 가능) RAG를 통해 검색된 개별 문서 정보를 전달.
data: RetrievedDocument 스키마 객체 (예: {"document_id": "doc1", "content_preview": "...", "score": 0.85})
LLM_REASONING_STEP: LLM의 내부 추론 과정(생각 단계)을 전달.
data: LLMReasoningStep 스키마 객체 (예: {"step_number": 1, "thought_process": "사용자의 질문은 IT 부서 장애 대응에 관한 것이다...", "action_taken": "관련 키워드로 문서를 검색해야겠다."})
CONTENT: LLM이 생성한 실제 답변 내용의 조각(chunk)을 전달. 이 조각들을 순서대로 이어 붙이면 전체 답변이 됩니다.
content: "답변 내용의 일부 문자열"
ERROR: 처리 중 오류 발생 시 전달.
data: {"error": "오류 메시지", "details": "상세 오류 정보 (디버그 모드 시)"}
END: 스트리밍 종료를 알림.
data: {"message": "스트리밍이 정상적으로 종료되었습니다."}
SSE 스트림 예시:

CopyInsert
data: {"session_id":"sess_1716808282","type":"START","content":null,"data":{"session_id":"sess_1716808282"},"timestamp":"2025-05-27T20:11:22.123Z"}

data: {"session_id":"sess_1716808282","type":"INTENT_CLASSIFIED","content":null,"data":{"intent":"qna","entities":{},"description":"사용자 의도를 'qna'로 파악했습니다."},"timestamp":"2025-05-27T20:11:22.567Z"}

data: {"session_id":"sess_1716808282","type":"THINKING","content":null,"data":{"step_description":"RAG 검색을 시작합니다."},"timestamp":"2025-05-27T20:11:22.890Z"}

data: {"session_id":"sess_1716808282","type":"LLM_REASONING_STEP","content":null,"data":{"step_number":1,"thought_process":"질문의 핵심은 'IT 부서 장애 대응'과 '회의록'의 연관성이다.","action_taken":"회의록 데이터에서 해당 키워드를 검색한다."},"timestamp":"2025-05-27T20:11:23.123Z"}

data: {"session_id":"sess_1716808282","type":"CONTENT","content":"회의록에 따르면, 지난 분기 IT 부서의 주요 장애 사례","data":null,"timestamp":"2025-05-27T20:11:23.567Z"}

data: {"session_id":"sess_1716808282","type":"CONTENT","content":" 분석 회의에서 해당 내용이 논의되었습니다. 특히, 예방 조치에 대한","data":null,"timestamp":"2025-05-27T20:11:23.890Z"}

data: {"session_id":"sess_1716808282","type":"CONTENT","content":" 부분이 강조되었습니다.","data":null,"timestamp":"2025-05-27T20:11:24.123Z"}

data: {"session_id":"sess_1716808282","type":"END","content":null,"data":{"message":"스트리밍이 정상적으로 종료되었습니다."},"timestamp":"2025-05-27T20:11:24.567Z"}
7.2. 세션 관리
클라이언트는 ChatRequest에 session_id를 포함하여 이전 대화의 연속성을 유지할 수 있습니다.
session_id가 제공되지 않으면 서버는 새로운 세션을 시작하고, 생성된 session_id를 첫 START 타입의 LLMResponseChunk에 포함하여 반환합니다. 클라이언트는 이 ID를 저장했다가 다음 요청부터 사용해야 합니다.
대화 히스토리 및 meeting_context와 같은 세션 정보는 서버의 ChatHistoryService 및 WorkflowService 내에서 session_id를 키로 하여 관리됩니다. (현재는 인메모리, 향후 Redis 등 외부 저장소 사용 가능)
7.3. Mattermost 연동
MattermostService는 특정 조건(예: 사용자 의도가 '회의록 요약 전송'으로 분류될 경우)에 따라 Mattermost API를 호출하여 메시지를 전송할 수 있습니다.
필요한 환경 변수: MATTERMOST_URL, MATTERMOST_BOT_TOKEN.
Mattermost 사용자 ID와 내부 시스템 사용자 ID 간의 매핑은 DBService를 통해 관리될 수 있으며, manage_mattermost_users.py 스크립트로 관련 정보를 동기화할 수 있습니다. (메모리 참조)
7.4. 외부 RAG 서비스 (OpenSearch) 연동
ExternalRAGService는 OPENSEARCH_API_URL 환경 변수에 지정된 OpenSearch (또는 호환 API를 제공하는 벡터 DB) 엔드포인트로 검색 쿼리를 전송합니다.
검색 대상 필드, 필터링 조건 등은 ExternalRAGService 내부 로직 또는 OpenSearch 쿼리 DSL을 통해 정의됩니다. 허브 시스템에서 OpenSearch 인덱스 구조 및 검색 로직을 이해하고 있다면, 보다 정교한 연동이 가능합니다.
