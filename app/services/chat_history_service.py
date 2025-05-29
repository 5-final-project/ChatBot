from typing import List, Dict, Any
from threading import Lock
import time

class ChatHistoryService:
    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.conversation_history: Dict[str, List[Dict[str, Any]]] = {}
        # logger.info("ChatHistoryService initialized.") # 필요한 경우 로깅 추가

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        지정된 세션 ID에 대한 대화 기록을 검색합니다.
        """
        return self.conversation_history.get(session_id, [])

    def add_message(self, session_id: str, role: str, content: str, **kwargs):
        """
        지정된 세션 ID의 대화 기록에 메시지를 추가합니다.
        'role'은 'user', 'assistant', 'system' 등이 될 수 있습니다.
        kwargs를 통해 추가적인 메타데이터(예: timestamp, message_id)를 저장할 수 있습니다.
        """
        # 빈 메시지는 추가하지 않음
        if not content or not content.strip():
            return
            
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = []
        
        message = {"role": role, "content": content, "timestamp": time.time()}
        message.update(kwargs) # 추가 메타데이터 병합
            
        self.conversation_history[session_id].append(message)
        # logger.debug(f"Message added to session {session_id}: {message}") # 필요한 경우 로깅 추가

    def clear_history(self, session_id: str):
        """
        지정된 세션 ID에 대한 대화 기록을 지웁니다.
        """
        if session_id in self.conversation_history:
            del self.conversation_history[session_id]
            # logger.info(f"History cleared for session {session_id}.") # 필요한 경우 로깅 추가

    def get_recent_history(self, session_id: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        지정된 세션 ID에 대한 최근 k개의 대화 기록을 검색합니다.
        """
        history = self.conversation_history.get(session_id, [])
        return history[-k:]
