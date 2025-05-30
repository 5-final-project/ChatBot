# app/schemas/chat.py: 채팅 API 요청 및 응답 스키마 정의
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Dict, Any, List, Union
from enum import Enum
from datetime import datetime

class MessageType(str, Enum):
    """
    스트리밍 응답의 메시지 타입.
    """
    START = "start"          # 스트리밍 시작
    CONTENT = "content"      # 실제 내용 조각
    END = "end"            # 스트리밍 종료
    ERROR = "error"          # 오류 발생
    INFO = "info"            # 정보 메시지 (예: 검색된 문서, 추론 단계)
    THINKING = "thinking"    # 처리 중 상태 (예: RAG 검색 시작, LLM 요청)
    RETRIEVED_DOCUMENT = "retrieved_document" # 개별 검색된 문서 정보
    RETRIEVED_DOCUMENTS = "retrieved_documents" # 검색된 문서 정보 (목록)
    LLM_REASONING_STEP = "llm_reasoning_step" # LLM 추론 단계 정보
    INTENT_CLASSIFIED = "intent_classified" # 의도 분류 결과
    TASK_COMPLETE = "task_complete" # 특정 작업 완료 (예: Mattermost 전송 완료)
    RESULT = "result"  # 최종 결과 메시지 (예: Mattermost 전송 성공/실패 요약)
    WARNING = "warning"  # 경고 메시지

class LLMResponseChunk(BaseModel):
    """
    스트리밍 LLM 응답의 각 조각입니다.
    
    Attributes:
        type (MessageType): 응답 메시지의 유형
        content (str, optional): 응답 내용 (CONTENT, ERROR, INFO 타입일 때 사용)
        data (Any, optional): 추가 데이터 (RETRIEVED_DOCUMENTS, LLM_REASONING_STEP 등)
        session_id (str, optional): 세션 ID
    """
    type: MessageType = Field(..., description="응답 메시지의 유형")
    content: Optional[str] = Field(
        None, 
        description="응답 내용 (CONTENT, ERROR, INFO 타입일 때 사용)",
        example="안녕하세요! 무엇을 도와드릴까요?"
    )
    data: Optional[Any] = Field(
        None, 
        description="추가 데이터 (RETRIEVED_DOCUMENTS, LLM_REASONING_STEP 등)",
        example={"step": "사용자 의도 분석 중..."}
    )
    session_id: Optional[str] = Field(
        None, 
        description="세션 ID (선택사항, 세션 관리에 사용)",
        example="session_12345"
    )

class MeetingContext(BaseModel):
    """
    외부 허브에서 제공된 현재 회의 관련 정보 모델입니다.
    
    Attributes:
        hub_meeting_title (str, optional): 허브 회의 제목
        hub_participant_names (List[str], optional): 허브 회의 참석자 이름 목록
        hub_minutes_s3_url (str, optional): 허브 회의록 S3 URL
    """
    hub_meeting_title: Optional[str] = Field(None, description="허브 회의 제목", example="2024년 2분기 전략 회의")
    hub_participant_names: Optional[List[str]] = Field(None, description="허브 회의 참석자 이름 목록", example=["김철수", "이영희", "박지성"])
    hub_minutes_s3_url: Optional[str] = Field(None, description="허브 회의록 S3 URL", example="s3://my-bucket/minutes/meeting_xyz789.pdf")

class ChatRequest(BaseModel):
    """
    RAG 기반 채팅 스트리밍 엔드포인트에 대한 사용자 요청 모델입니다.
    이 모델은 사용자의 질의와 함께 검색 범위, 세션 정보, 그리고 외부 시스템(예: 허브)에서 제공된
    회의 관련 맥락 정보를 포함할 수 있습니다.
    
    Attributes:
        query (str): 사용자 질의 (필수)
        session_id (str, optional): 세션 ID (선택사항)
        search_in_meeting_documents_only (bool, optional): 회의 문서만 검색할지 여부 (기본값: False)
        target_document_ids (List[str], optional): 특정 문서 ID로 검색 제한
        meeting_context (MeetingContext, optional): 외부 허브에서 제공된 현재 회의 관련 정보
    """
    query: str = Field(
        ..., 
        description="사용자 질의 (필수)",
        example="지난 주 회의에서 결정된 내용을 알려줘",
        min_length=1
    )
    session_id: Optional[str] = Field(
        None, 
        description="세션 ID (선택사항, 대화 맥락 유지에 사용)",
        example="sess_abc123"
    )
    search_in_meeting_documents_only: Optional[bool] = Field(
        False, 
        description="회의 관련 문서만 검색할지 여부 (기본값: False)",
        example=True
    )
    target_document_ids: Optional[List[str]] = Field(
        None, 
        description="특정 문서 ID 리스트 (지정된 문서에서만 검색)",
        example=["doc_123", "doc_456"]
    )
    meeting_context: Optional[MeetingContext] = Field(
        None, 
        description="외부 허브에서 제공된 현재 회의 관련 정보"
    )

    class Config:
        schema_extra = {
            "example": {
                "query": "지난 주 회의에서 결정된 내용을 알려줘",
                "session_id": "sess_abc123",
                "search_in_meeting_documents_only": True,
                "target_document_ids": ["meeting_20230520"],
                "meeting_context": {
                    "hub_meeting_title": "5월 20일 팀 회의",
                    "hub_participant_names": ["John Doe", "Jane Doe"],
                    "hub_minutes_s3_url": "https://example.s3.amazonaws.com/meeting_minutes.pdf"
                }
            }
        }

class RetrievedDocument(BaseModel):
    """
    검색된 문서 조각 정보 모델입니다.
    
    Attributes:
        source_document_id (str): 문서의 고유 ID
        content_chunk (str): 검색된 문서 내용 조각
        score (float, optional): 검색 결과의 유사도 점수 (0-1)
        metadata (Dict[str, Any], optional): 문서의 추가 메타데이터
    """
    source_document_id: str = Field(
        ..., 
        description="문서의 고유 ID",
        example="meeting_20230520_page3"
    )
    content_chunk: str = Field(
        ..., 
        description="검색된 문서 내용 조각",
        example="5월 20일 회의록: 프로젝트 일정이 2주 연기되었습니다."
    )
    score: Optional[float] = Field(
        None, 
        description="검색 결과의 유사도 점수 (0-1)",
        example=0.87,
        ge=0.0,
        le=1.0
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="문서의 추가 메타데이터 (제목, 출처, 생성일 등)",
        example={
            "title": "5월 20일 팀 회의록",
            "source": "meeting_minutes",
            "created_at": "2023-05-20T14:30:00Z"
        }
    )

class LLMReasoningStep(BaseModel):
    """
    LLM의 중간 추론 단계를 나타내는 모델입니다.
    
    Attributes:
        step_description (str): 추론 단계에 대한 설명
        details (Dict[str, Any], optional): 추론 단계의 상세 정보
    """
    step_description: str = Field(
        ..., 
        description="추론 단계에 대한 설명",
        example="사용자 질의의 의도를 분석하는 중..."
    )
    details: Optional[Dict[str, Any]] = Field(
        None, 
        description="추론 단계의 상세 정보 (선택사항)",
        example={
            "intent": "meeting_inquiry",
            "confidence": 0.95,
            "entities": ["last week", "decision"]
        }
    )
