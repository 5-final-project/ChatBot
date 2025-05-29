"""
LLM 관리자 서비스
LLM 관련 모든 서비스를 통합 관리하는 클래스를 제공합니다.
"""
import logging
from typing import List, Dict, Any, AsyncGenerator, Union, Optional
from app.services.llm.llm_core import gemini_model
from app.services.llm.llm_intent_service import IntentService
from app.services.llm.llm_streaming_service import StreamingService
from app.services.llm.llm_reasoning_service import ReasoningService
from app.schemas.chat import LLMReasoningStep, RetrievedDocument

logger = logging.getLogger(__name__)

class LLMManager:
    """LLM 관련 모든 서비스를 통합 관리하는 클래스"""
    
    _instance = None
    
    def __new__(cls):
        """싱글톤 패턴 구현"""
        if cls._instance is None:
            cls._instance = super(LLMManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """LLM 서비스를 초기화합니다."""
        if self._initialized:
            return
        
        logger.info("LLMManager 초기화 중...")
        self.core = gemini_model
        self.intent_service = IntentService()
        self.streaming_service = StreamingService()
        self.reasoning_service = ReasoningService()
        self._initialized = True
        logger.info("LLMManager 초기화 완료")
    
    async def classify_intent(self, query: str) -> Dict[str, Any]:
        """
        사용자 질의의 의도를 분류합니다.
        
        Args:
            query (str): 사용자 질의 내용
            
        Returns:
            Dict[str, Any]: 의도 분류 결과 및 엔티티 정보
        """
        return await self.intent_service.classify_intent(query)
    
    async def generate_response_stream(
        self, 
        prompt: str, 
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        retrieved_documents: Optional[List[Union[RetrievedDocument, Dict[str, Any]]]] = None
    ) -> AsyncGenerator[Union[str, LLMReasoningStep], None]:
        """
        스트리밍 방식으로 응답을 생성합니다.
        
        Args:
            prompt (str): 사용자 프롬프트
            conversation_history (List[Dict], optional): 이전 대화 기록
            retrieved_documents (List[RetrievedDocument], optional): 검색된 문서 조각들
            
        Yields:
            Union[str, LLMReasoningStep]: 텍스트 조각 또는 추론 단계
        """
        async for chunk in self.streaming_service.generate_response_stream(
            prompt=prompt,
            conversation_history=conversation_history,
            retrieved_documents=retrieved_documents
        ):
            yield chunk
    
    async def generate_chat_response(
        self, 
        prompt: str, 
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        비스트리밍 방식으로 응답을 생성합니다.
        
        Args:
            prompt (str): 사용자 프롬프트
            conversation_history (List[Dict], optional): 이전 대화 기록
            
        Returns:
            str: 생성된 응답 텍스트
        """
        return await self.streaming_service.generate_chat_response(
            prompt=prompt,
            conversation_history=conversation_history
        )
    
    def extract_reasoning_steps(self, content: str):
        """
        응답 텍스트에서 추론 단계를 추출합니다.
        
        Args:
            content (str): LLM 응답 텍스트
            
        Returns:
            Tuple[List[LLMReasoningStep], str]: 추출된 추론 단계와 정제된 텍스트
        """
        return self.reasoning_service.extract_reasoning_steps(content)
    
    def parse_reasoning_json(self, content: str):
        """
        응답 텍스트에서 JSON 형식의 추론 데이터를 추출합니다.
        
        Args:
            content (str): LLM 응답 텍스트
            
        Returns:
            Optional[Dict[str, Any]]: 파싱된 JSON 데이터 또는 None
        """
        return self.reasoning_service.parse_reasoning_json(content)
    
    def is_available(self) -> bool:
        """
        LLM 서비스 사용 가능 여부를 확인합니다.
        
        Returns:
            bool: LLM 서비스 사용 가능 여부
        """
        return self.core.is_available()


# LLMManager의 싱글톤 인스턴스 생성
llm_manager = LLMManager()
