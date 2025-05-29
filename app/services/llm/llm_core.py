"""
LLM 코어 모듈
Google Gemini API와의 기본 연결 및 설정을 담당합니다.
"""
import os
import logging
import google.generativeai as genai
from app.core.config import settings

# 로깅 설정
logger = logging.getLogger(__name__)

# Google Gemini API 키 설정
GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY") or settings.GOOGLE_API_KEY

# API 키 설정 확인
if not GEMINI_API_KEY:
    logger.warning("GOOGLE_GEMINI_API_KEY 환경 변수가 설정되지 않았습니다. LLM 서비스가 작동하지 않을 수 있습니다.")
else:
    # API 키로 Gemini 초기화
    genai.configure(api_key=GEMINI_API_KEY)

class LLMCore:
    """Google Gemini API와의 기본 연결 및 설정을 관리하는 클래스"""
    
    def __init__(self):
        """LLM 코어를 초기화합니다."""
        self.api_key = GEMINI_API_KEY
        self.model_name = "gemini-1.5-pro-latest"  # 또는 gemini-1.5-flash 등
        
        # 기본 생성 설정
        self.generation_config = {
            "temperature": 0.7,
            "top_p": 1,
            "top_k": 1,
            "max_output_tokens": 2048,
        }
        
        # 안전 설정
        self.safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        
        # 모델 초기화
        self.model = self._initialize_model()
    
    def _initialize_model(self):
        """Gemini 모델을 초기화하고 반환합니다."""
        if not self.api_key:
            logger.error("API 키가 제공되지 않아 Gemini 모델을 초기화할 수 없습니다.")
            return None
        
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )
            logger.info(f"Gemini 모델({self.model_name})이 성공적으로 로드되었습니다.")
            return model
        except Exception as e:
            logger.error(f"Gemini 모델 로드 중 오류 발생: {e}")
            return None
    
    def is_available(self):
        """LLM 서비스가 사용 가능한지 확인합니다."""
        return self.model is not None
    
    def create_chat(self, history=None):
        """
        새로운 채팅 세션을 생성합니다.
        
        Args:
            history (list, optional): 이전 대화 기록
            
        Returns:
            Chat: Gemini 채팅 객체 또는 None
        """
        if not self.is_available():
            logger.warning("LLM 모델이 초기화되지 않아 채팅을 생성할 수 없습니다.")
            return None
        
        try:
            if history is None:
                history = []
            return self.model.start_chat(history=history)
        except Exception as e:
            logger.error(f"채팅 세션 생성 중 오류 발생: {e}")
            return None
    
    def update_config(self, temperature=None, max_output_tokens=None):
        """
        모델 생성 설정을 업데이트합니다.
        
        Args:
            temperature (float, optional): 생성 다양성 조절 (0.0 ~ 1.0)
            max_output_tokens (int, optional): 최대 출력 토큰 수
            
        Returns:
            bool: 업데이트 성공 여부
        """
        if temperature is not None:
            self.generation_config["temperature"] = max(0.0, min(1.0, temperature))
            
        if max_output_tokens is not None:
            self.generation_config["max_output_tokens"] = max_output_tokens
        
        # 모델 재초기화
        try:
            self.model = self._initialize_model()
            return self.model is not None
        except Exception as e:
            logger.error(f"모델 설정 업데이트 중 오류 발생: {e}")
            return False

# 싱글톤 인스턴스 생성
gemini_model = LLMCore()
