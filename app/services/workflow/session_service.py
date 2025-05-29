"""
세션 서비스 모듈
사용자 세션 및 대화 컨텍스트 관리를 담당하는 서비스를 제공합니다.
"""
import logging
import uuid
from typing import Dict, List, Any, Optional
from app.schemas.chat import MeetingContext
from app.services.chat_history_service import ChatHistoryService

logger = logging.getLogger(__name__)

class SessionService:
    """사용자 세션 및 대화 컨텍스트 관리를 담당하는 서비스"""
    
    def __init__(self):
        """세션 서비스를 초기화합니다."""
        self.session_meeting_contexts: Dict[str, MeetingContext] = {}
        self.chat_history_service = ChatHistoryService()
    
    def generate_session_id(self) -> str:
        """
        새 세션 ID를 생성합니다.
        
        Returns:
            str: 생성된 세션 ID
        """
        return str(uuid.uuid4())
    
    def get_meeting_context(self, session_id: str) -> Optional[MeetingContext]:
        """
        세션 ID에 해당하는 회의 컨텍스트를 가져옵니다.
        
        Args:
            session_id (str): 세션 ID
            
        Returns:
            Optional[MeetingContext]: 회의 컨텍스트 또는 None
        """
        return self.session_meeting_contexts.get(session_id)
    
    def set_meeting_context(self, session_id: str, meeting_context: Optional[MeetingContext]) -> None:
        """
        세션 ID에 회의 컨텍스트를 설정합니다.
        
        Args:
            session_id (str): 세션 ID
            meeting_context (MeetingContext, optional): 회의 컨텍스트
        """
        if meeting_context is None:
            logger.info(f"[{session_id}] 세션에 회의 컨텍스트 없음")
            return
            
        self.session_meeting_contexts[session_id] = meeting_context
        meeting_id = getattr(meeting_context, 'hub_meeting_id', '알 수 없음')
        logger.info(f"[{session_id}] 세션에 회의 컨텍스트 설정: {meeting_id}")
    
    def remove_meeting_context(self, session_id: str) -> bool:
        """
        세션 ID의 회의 컨텍스트를 제거합니다.
        
        Args:
            session_id (str): 세션 ID
            
        Returns:
            bool: 제거 성공 여부
        """
        if session_id in self.session_meeting_contexts:
            del self.session_meeting_contexts[session_id]
            logger.info(f"[{session_id}] 세션의 회의 컨텍스트 제거됨")
            return True
        return False
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        세션 ID의 최근 10개 대화 기록을 가져옵니다.
        
        Args:
            session_id (str): 세션 ID
            
        Returns:
            List[Dict[str, Any]]: 최근 10개의 대화 기록
        """
        return self.chat_history_service.get_recent_history(session_id, k=10)
    
    def add_user_message(self, session_id: str, message: str) -> None:
        """
        사용자 메시지를 대화 기록에 추가합니다.
        
        Args:
            session_id (str): 세션 ID
            message (str): 사용자 메시지
        """
        self.chat_history_service.add_message(session_id, "user", message)
        logger.info(f"[{session_id}] 사용자 메시지 기록됨: {message[:50]}{'...' if len(message) > 50 else ''}")
    
    def add_assistant_message(self, session_id: str, message: str) -> None:
        """
        어시스턴트 메시지를 대화 기록에 추가합니다.
        
        Args:
            session_id (str): 세션 ID
            message (str): 어시스턴트 메시지
        """
        self.chat_history_service.add_message(session_id, "assistant", message)
        logger.info(f"[{session_id}] 어시스턴트 메시지 기록됨: {message[:50]}{'...' if len(message) > 50 else ''}")
    
    def clear_history(self, session_id: str) -> None:
        """
        세션 ID의 대화 기록을 초기화합니다.
        
        Args:
            session_id (str): 세션 ID
        """
        self.chat_history_service.clear_history(session_id)
        logger.info(f"[{session_id}] 대화 기록 초기화됨")
