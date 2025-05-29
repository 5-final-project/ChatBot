"""
워크플로우 코어 모듈
워크플로우 서비스의 기본 클래스 및 공통 기능을 제공합니다.
"""
import logging
import json
import asyncio
import uuid
from threading import Lock
from typing import Dict, List, Any, Optional, AsyncGenerator
from app.schemas.chat import ChatRequest, MeetingContext, LLMResponseChunk, MessageType
from app.services.llm import llm_manager
from app.services.mattermost import mattermost_manager
from app.services.external_rag_service import ExternalRAGService
from app.services.chat_history_service import ChatHistoryService

logger = logging.getLogger(__name__)

class WorkflowCore:
    """워크플로우 서비스의 기본 클래스"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls, *args, **kwargs):
        """싱글톤 패턴 구현"""
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """워크플로우 코어를 초기화합니다."""
        # 서비스 초기화 완료 여부
        self._initialized = False
        
        if self._initialized:
            return
        
        # 서비스 인스턴스
        self.llm_service = llm_manager
        self.mm_service = mattermost_manager
        self.external_rag_service = ExternalRAGService()
        self.chat_history_service = ChatHistoryService()
        
        # 세션 데이터
        self.session_meeting_contexts: Dict[str, MeetingContext] = {}
        
        # DB 초기화 상태
        self.db_initialized = False
        
        self._initialized = True
        logger.info("WorkflowCore 초기화 완료")
    
    def _format_sse_chunk(self, session_id: str, type: MessageType, content: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> str:
        """
        Server-Sent Events(SSE) 메시지 청크를 포맷팅합니다.
        
        Args:
            session_id (str): 세션 ID
            type (MessageType): 메시지 유형
            content (str, optional): 메시지 내용
            data (Dict[str, Any], optional): 추가 데이터
            
        Returns:
            str: SSE 형식의 메시지 청크
        """
        payload = {
            "session_id": session_id,
            "type": type.value,  # Enum 값을 문자열로 사용
        }
        
        if content is not None:
            payload["content"] = content
            
        if data is not None:
            payload["data"] = data
        
        json_payload = json.dumps(payload, ensure_ascii=False)
        return f"data: {json_payload}\n\n"
    
    def generate_session_id(self) -> str:
        """
        새 세션 ID를 생성합니다.
        
        Returns:
            str: 생성된 세션 ID
        """
        return str(uuid.uuid4())
    
    def get_meeting_context(self, session_id: str, request: ChatRequest) -> Optional[MeetingContext]:
        """
        세션 ID와 요청으로부터 회의 컨텍스트를 가져옵니다.
        
        Args:
            session_id (str): 세션 ID
            request (ChatRequest): 채팅 요청 객체
            
        Returns:
            Optional[MeetingContext]: 회의 컨텍스트 또는 None
        """
        # 1. 요청에 회의 컨텍스트가 있는 경우
        if request.meeting_context:
            logger.info(f"[{session_id}] 요청에 새로운 meeting_context가 포함되어 세션 정보를 업데이트합니다.")
            self.session_meeting_contexts[session_id] = request.meeting_context
            return request.meeting_context
            
        # 2. 세션 저장소에 회의 컨텍스트가 있는 경우
        elif session_id in self.session_meeting_contexts:
            logger.info(f"[{session_id}] 요청에 meeting_context가 없지만, 저장된 세션 정보가 있어 이를 사용합니다.")
            return self.session_meeting_contexts[session_id]
            
        # 3. 회의 컨텍스트가 없는 경우
        else:
            logger.info(f"[{session_id}] 요청 및 세션 저장소에 meeting_context 정보가 없습니다.")
            return None
