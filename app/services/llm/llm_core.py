"""
LLM 코어 모듈
Google Gemini API와의 기본 연결 및 설정을 담당합니다.
"""
import os
import logging
import importlib.metadata
from google import genai
from google.genai import types

# 로깅 설정
logger = logging.getLogger(__name__)

# 패키지 버전 확인
try:
    genai_version = importlib.metadata.version("google-genai")
    logger.info(f"google-genai 버전: {genai_version}")
except Exception as e:
    logger.error(f"패키지 버전 확인 실패: {e}")
    genai_version = "알 수 없음"

from app.core.config import settings

# Google Gemini API 키 설정
GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY") or settings.GOOGLE_API_KEY

# API 키 설정 확인
if not GEMINI_API_KEY:
    logger.warning("GOOGLE_GEMINI_API_KEY 환경 변수가 설정되지 않았습니다. LLM 서비스가 작동하지 않을 수 있습니다.")

class LLMCore:
    """Google Gemini API와의 기본 연결 및 설정을 관리하는 클래스"""
    
    def __init__(self):
        """LLM 코어를 초기화합니다."""
        self.api_key = GEMINI_API_KEY
        
        # 최신 모델 이름 설정 (최신 API와 호환되는 이름)
        # 사고 기능을 지원하는 모델로 설정
        self.model_name = "gemini-2.5-flash-preview-05-20"
        
        # 기본 생성 설정
        self.temperature = 0.7
        self.top_p = 1
        self.top_k = 1
        self.max_output_tokens = 2048
        
        # 내장 사고 기능 설정
        self.thinking_enabled = True
        self.thinking_budget = 5000  # 사고 예산 설정 (0~24576 범위)
        
        # 안전 설정
        self.safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        
        # API 초기화
        self.is_initialized = False
        self.client = None
        self._initialize()
    
    def _initialize(self):
        """Google Generative AI API를 초기화합니다."""
        if not self.api_key:
            logger.error("API 키가 제공되지 않아 Gemini API를 초기화할 수 없습니다.")
            return
        
        try:
            # Client 초기화
            self.client = genai.Client(api_key=self.api_key)
            logger.info(f"Gemini API 클라이언트 초기화 성공")
            
            # 모델 사용 가능 여부 확인
            try:
                # 최신 API에서는 list_models 메서드를 직접 호출하지 않고 특정 모델을 사용
                # 따라서 models 목록 확인 단계를 건너뛰고 직접 지정된 모델 사용
                
                # 간단한 테스트로 API 연결 확인
                try:
                    # 모델이 존재하는지 확인하기 위한 테스트 요청
                    generation_config = types.GenerateContentConfig(
                        temperature=0.7,
                        max_output_tokens=10
                    )
                    
                    # 간단한 프롬프트로 테스트
                    logger.info(f"모델 테스트 시도: {self.model_name}")
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents="테스트",
                        config=generation_config
                    )
                    
                    logger.info(f"API 연결 테스트 성공: {self.model_name}")
                except Exception as test_error:
                    # 지정된 모델에 오류가 발생하면 대체 모델 시도
                    logger.warning(f"지정된 모델({self.model_name})에 접근할 수 없습니다: {test_error}")
                    logger.warning("대체 모델(gemini-1.5-pro)을 시도합니다.")
                    self.model_name = "gemini-1.5-pro"
                    
                    # 대체 모델로 다시 테스트
                    try:
                        response = self.client.models.generate_content(
                            model=self.model_name,
                            contents="테스트",
                            config=generation_config
                        )
                        logger.info(f"대체 모델 테스트 성공: {self.model_name}")
                    except Exception as fallback_error:
                        # 마지막 대체 모델 시도
                        logger.warning(f"대체 모델(gemini-1.5-pro) 접근 실패: {fallback_error}")
                        logger.warning("최종 대체 모델(gemini-pro)을 시도합니다.")
                        self.model_name = "gemini-pro"
                        
                        try:
                            response = self.client.models.generate_content(
                                model=self.model_name,
                                contents="테스트",
                                config=generation_config
            )
                            logger.info(f"최종 대체 모델 테스트 성공: {self.model_name}")
                        except Exception as final_error:
                            # 모든 모델이 실패하면 초기화 실패로 표시
                            logger.error(f"모든 모델 테스트 실패: {final_error}")
                            self.is_initialized = False
                            return
                
                self.is_initialized = True
                logger.info(f"Gemini API가 성공적으로 초기화되었습니다. 모델: {self.model_name}")
                logger.info(f"사용 중인 google-genai 버전: {genai_version}")
            except Exception as e:
                logger.error(f"API 초기화 중 오류 발생: {e}")
                self.is_initialized = False
        except Exception as e:
            logger.error(f"Gemini API 초기화 중 오류 발생: {e}")
            self.is_initialized = False
    
    def get_generation_config(self):
        """
        GenerateContentConfig 객체를 생성하여 반환합니다.
        """
        try:
            # 기본 생성 설정
            generation_config = types.GenerateContentConfig(
                temperature=self.temperature,
                top_p=self.top_p,
                top_k=self.top_k,
                max_output_tokens=self.max_output_tokens
            )
            
            # 사고 기능이 활성화된 경우 ThinkingConfig 추가
            if self.thinking_enabled:
                thinking_config = types.ThinkingConfig(
                    thinking_budget=self.thinking_budget
                )
                generation_config.thinking_config = thinking_config
                
            return generation_config
        except Exception as e:
            logger.error(f"GenerateContentConfig 생성 실패: {e}")
            raise e
    
    def is_available(self):
        """LLM 서비스가 사용 가능한지 확인합니다."""
        return self.is_initialized and self.client is not None
    
    def create_chat(self, history=None):
        """
        새로운 채팅 세션을 생성합니다.
        최신 API에서는 채팅 세션을 별도로 생성하지 않고, 직접 모델에 요청합니다.
        
        Args:
            history (list, optional): 이전 대화 기록
            
        Returns:
            dict: 가상 채팅 세션 객체 (이전 API와의 호환성 유지)
        """
        if not self.is_available():
            logger.warning("LLM API가 초기화되지 않아 채팅을 생성할 수 없습니다.")
            return None
        
        try:
            # 대화 기록 처리
            processed_history = self._process_history(history)
            
            # 최신 API에서는 별도의 채팅 세션을 생성하지 않고, 
            # 각 요청마다 히스토리를 포함하여 전송합니다.
            # 이전 API와의 호환성을 위해 가상 채팅 세션 객체를 반환합니다.
            
            # 채팅 세션 정보 저장
            chat_session = {
                "model": self.model_name,
                "history": processed_history,
                # send_message 메서드 구현을 위한 내부 메서드
                "send_message": lambda text: self._send_chat_message(text, processed_history)
            }
            
            logger.info(f"가상 채팅 세션이 생성되었습니다. (최신 API 호환)")
            return chat_session
        except Exception as e:
            logger.error(f"채팅 세션 생성 중 오류 발생: {e}")
            # 대신 None을 반환하여 호출자가 오류를 처리할 수 있도록 합니다.
            return None
    
    def _send_chat_message(self, text, history=None):
        """
        채팅 메시지를 전송하고 응답을 받습니다. (내부 메서드)
        
        Args:
            text (str): 전송할 메시지 텍스트
            history (list): 이전 대화 기록
            
        Returns:
            응답 객체
        """
        try:
            # 생성 설정 준비
            generation_config = self.get_generation_config()
            
            # 이전 대화 기록 및 새 메시지 결합
            all_content = []
            
            # 히스토리가 있으면 추가
            if history:
                all_content.extend(history)
            
            # 새 메시지 추가 (최신 API 방식)
            # 단일 텍스트 메시지인 경우 텍스트 직접 전달
            
            # 응답 생성
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[{"role": "user", "parts": [{"text": text}]}],
                config=generation_config
            )
            
            return response
        except Exception as e:
            logger.error(f"채팅 메시지 전송 중 오류 발생: {e}")
            raise e
    
    def generate_content_stream(self, contents, **kwargs):
        """
        Gemini API를 사용하여 스트리밍 응답을 생성합니다.
        
        Args:
            contents (str): 생성할 컨텐츠 프롬프트
            **kwargs: 추가 파라미터
            
        Returns:
            스트리밍 응답 생성기
        """
        if not self.is_available():
            logger.error("Gemini API가 초기화되지 않았습니다.")
            raise RuntimeError("LLM 서비스가 초기화되지 않았습니다.")
            
        try:
            # 생성 설정 준비
            generation_config = kwargs.get('generation_config', self.get_generation_config())
            
            # 콘텐츠 형식 변환 (문자열 또는 복잡한 객체)
            formatted_contents = self._format_contents(contents)
            
            # 응답 생성 (스트리밍)
            logger.info(f"generate_content_stream 호출 - 모델: {self.model_name}")
            return self.client.models.generate_content_stream(
                model=self.model_name,
                contents=formatted_contents,
                config=generation_config
            )
        except Exception as e:
            logger.error(f"generate_content_stream 호출 실패: {e}")
            raise e
    
    def generate_content(self, contents, **kwargs):
        """
        Gemini API를 사용하여 컨텐츠를 생성합니다.
        
        Args:
            contents (str): 생성할 컨텐츠 프롬프트
            **kwargs: 추가 파라미터
            
        Returns:
            응답 객체
        """
        if not self.is_available():
            logger.error("Gemini API가 초기화되지 않았습니다.")
            raise RuntimeError("LLM 서비스가 초기화되지 않았습니다.")
            
        try:
            # 생성 설정 준비
            generation_config = kwargs.get('generation_config', self.get_generation_config())
            
            # 콘텐츠 형식 변환
            formatted_contents = self._format_contents(contents)
            
            # 스트리밍 여부 확인
            stream = kwargs.get('stream', False)
            
            if stream:
                # 스트리밍 요청은 generate_content_stream으로 위임
                return self.generate_content_stream(
                    contents=contents,
                    generation_config=generation_config
                )
            else:
                # 비스트리밍 요청
                logger.info(f"generate_content 호출 - 모델: {self.model_name}")
                return self.client.models.generate_content(
                    model=self.model_name,
                    contents=formatted_contents,
                    config=generation_config
                )
        except Exception as e:
            logger.error(f"generate_content 호출 실패: {e}")
            raise e
    
    def _format_contents(self, contents):
        """
        API에 전달할 콘텐츠를 적절한 형식으로 변환합니다.
        
        Args:
            contents: 원본 콘텐츠 (문자열, 리스트, 사전 등)
            
        Returns:
            콘텐츠 객체 또는 리스트
        """
        # 문자열인 경우 간단히 전달
        if isinstance(contents, str):
            return contents
            
        # 리스트인 경우 각 항목 변환
        elif isinstance(contents, list):
            formatted_list = []
            for item in contents:
                if isinstance(item, str):
                    formatted_list.append(item)
                elif isinstance(item, dict):
                    # 역할이 있는 경우 역할 기반 형식으로 변환
                    if 'role' in item and ('text' in item or 'content' in item):
                        role = item.get('role', 'user')
                        text = item.get('text', item.get('content', ''))
                        formatted_list.append({
                            "role": role,
                            "parts": [{"text": text}]
                        })
                    else:
                        # 그대로 사용
                        formatted_list.append(item)
            return formatted_list
            
        # 딕셔너리인 경우 형식 변환
        elif isinstance(contents, dict):
            if 'role' in contents and ('text' in contents or 'content' in contents):
                role = contents.get('role', 'user')
                text = contents.get('text', contents.get('content', ''))
                return {
                    "role": role,
                    "parts": [{"text": text}]
                }
            else:
                # 그대로 사용
                return contents
                
        # 기타 타입은 그대로 반환
        return contents
    
    def _process_history(self, history):
        """
        대화 기록을 처리하여 최신 API 형식으로 변환합니다.
        
        Args:
            history (list): 처리할 대화 기록
            
        Returns:
            list: 처리된 대화 기록
        """
        if not history:
            return []
        
        processed_history = []
        for entry in history:
            if not entry:
                continue
                
            # 'content' 필드가 있는 경우
            if 'content' in entry and entry['content'] and entry['content'].strip():
                role = entry.get("role", "user")
                processed_entry = {
                    "role": role,
                    "parts": [{"text": entry['content']}]
                }
                processed_history.append(processed_entry)
            # 'parts' 필드가 있는 경우 (구형 형식)
            elif 'parts' in entry and entry['parts'] and isinstance(entry['parts'], list):
                if 'text' in entry['parts'][0] and entry['parts'][0]['text'].strip():
                    role = entry.get("role", "user")
                    processed_entry = {
                        "role": role,
                        "parts": [{"text": entry['parts'][0]['text']}]
                    }
                    processed_history.append(processed_entry)
        
        return processed_history
    
    def update_config(self, temperature=None, max_output_tokens=None, thinking_budget=None):
        """
        모델 생성 설정을 업데이트합니다.
        
        Args:
            temperature (float, optional): 생성 다양성 조절 (0.0 ~ 1.0)
            max_output_tokens (int, optional): 최대 출력 토큰 수
            thinking_budget (int, optional): 사고 단계에 사용할 최대 토큰 수 (0~24576)
            
        Returns:
            bool: 업데이트 성공 여부
        """
        if temperature is not None:
            self.temperature = max(0.0, min(1.0, temperature))
            
        if max_output_tokens is not None:
            self.max_output_tokens = max_output_tokens
        
        if thinking_budget is not None:
            self.thinking_budget = max(0, min(24576, thinking_budget))
            if thinking_budget == 0:
                self.thinking_enabled = False
            else:
                self.thinking_enabled = True
                  
        return self.is_available()

# 싱글톤 인스턴스 생성
gemini_model = LLMCore()
