"""
LLM 서비스 모듈
Google Gemini API와 통신하여 다양한 LLM 기능을 제공합니다.
"""
from app.services.llm.llm_core import LLMCore, gemini_model
from app.services.llm.llm_intent_service import IntentService
from app.services.llm.llm_streaming_service import StreamingService
from app.services.llm.llm_reasoning_service import ReasoningService
from app.services.llm.llm_manager import LLMManager

# 싱글톤 인스턴스 생성 - 기존 LLMService와 동일한 방식으로 접근 가능
llm_manager = LLMManager()

__all__ = [
    'LLMCore',
    'gemini_model',
    'IntentService',
    'StreamingService',
    'ReasoningService',
    'LLMManager',
    'llm_manager'
]
