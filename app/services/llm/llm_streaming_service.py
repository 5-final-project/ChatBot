"""
LLM 스트리밍 서비스
Google Gemini API의 스트리밍 응답을 처리하는 기능을 제공합니다.
"""
import logging
import asyncio
from typing import List, Dict, Any, AsyncGenerator, Union, Optional
from app.services.llm.llm_core import gemini_model
from app.schemas.chat import LLMReasoningStep, RetrievedDocument

logger = logging.getLogger(__name__)

class StreamingService:
    """Google Gemini API의 스트리밍 응답을 처리하는 서비스"""
    
    def __init__(self):
        """스트리밍 서비스를 초기화합니다."""
        self.model = gemini_model
    
    async def generate_response_stream(
        self, 
        prompt: str, 
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        retrieved_documents: Optional[List[Union[RetrievedDocument, Dict[str, Any]]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Gemini API를 사용하여 프롬프트에 대한 응답을 스트리밍 방식으로 생성합니다.
        
        Args:
            prompt (str): 사용자 프롬프트
            conversation_history (List[Dict], optional): 이전 대화 기록
            retrieved_documents (List[RetrievedDocument], optional): 검색된 문서 조각들
            
        Yields:
            Dict[str, Any]: 스트리밍 응답 데이터
        """
        if not self.model.is_available():
            yield {
                'type': 'error', 
                'data': {'message': 'LLM 서비스 불가', 'is_final': True}
            }
            return

        try:
            # 대화 기록 변환
            gemini_chat_history = []
            if conversation_history:
                for entry in conversation_history:
                    gemini_chat_history.append({
                        "role": entry.get("role", "user"),
                        "parts": [{"text": entry.get("content", "")}]
                    })
            
            # 시스템 인스트럭션 및 프롬프트 구성
            system_instruction = (
                "당신은 사용자 질문에 답변하기 전에, 스스로의 생각 과정을 먼저 상세히 기술하는 AI 어시스턴트입니다.\n"
                "다음 사용자 질문을 분석하고, 이 질문에 답변하기 위해 어떤 단계를 거쳐 생각하고 접근할 것인지, 고려 사항은 무엇인지 등을 \"<think>\"이라는 제목 아래에 단계별로 서술해주세요.\n"
                "마치 당신이 지금 이 요청을 받고 실시간으로 고민하고 계획을 세우는 것처럼 자연스럽게 작성해야 합니다.\n"
                "중요: 추론 과정은 반드시 영어로 작성하세요. 예: <think>First, I need to understand what the user is asking about...\n"
                "나의 생각 과정을 모두 서술한 후, 원래 사용자 질문에 대한 최종 답변을 \"Answer:\"이라는 제목 아래에 제시해주세요.\n"
                "최종 답변은 반드시 한국어로 작성해야 합니다."
            )
            
            user_message_text = f"{system_instruction}\n\n사용자 질문: {prompt}"
            
            # 검색된 문서가 있으면 추가
            if retrieved_documents and len(retrieved_documents) > 0:
                context_text = "\n\n--- 참고 문서 조각 ---"
                for i, doc in enumerate(retrieved_documents):
                    if isinstance(doc, RetrievedDocument):
                        doc_content = doc.content_chunk
                    elif isinstance(doc, dict):
                        doc_content = doc.get("content_chunk", "문서 내용 없음")
                    else:
                        doc_content = str(doc)
                    
                    context_text += f"\n문서 {i+1}: {doc_content}"
                user_message_text += context_text
            
            # 채팅 세션 시작
            chat = self.model.create_chat(history=gemini_chat_history)
            if not chat:
                logger.error("채팅 세션 생성 실패")
                yield f"죄송합니다, 채팅 세션을 생성할 수 없습니다. 관리자에게 문의하세요."
                return
            
            # 응답 스트리밍 시작
            response_stream = await chat.send_message_async(user_message_text, stream=True)
            
            buffer = ""
            in_think_section = False
            async for chunk in response_stream:
                if not chunk.parts:
                    continue
                
                # 원본 텍스트 그대로 유지 (띄어쓰기, 개행 등 포함)
                chunk_text = chunk.parts[0].text
                buffer += chunk_text
                
                # <think> 태그 처리
                think_start_index = buffer.lower().find("<think>")
                if think_start_index != -1 and not in_think_section:
                    # <think> 태그 이전의 텍스트가 있다면 일반 텍스트로 처리
                    if think_start_index > 0:
                        # 원본 텍스트 그대로 전송
                        yield buffer[:think_start_index]
                    
                    # <think> 섹션 시작
                    in_think_section = True
                    buffer = buffer[think_start_index:]  # 버퍼 업데이트
                    continue
                
                # answer: 태그 처리
                answer_index = buffer.lower().find("answer:")
                if answer_index != -1 and in_think_section:
                    # <think> 섹션 내용 추출하여 추론 단계로 처리 (원본 형식 유지)
                    think_content = buffer[:answer_index].replace("<think>", "").strip()
                    yield LLMReasoningStep(
                        step_description="Model's thinking process", 
                        details={"reasoning": think_content}
                    )
                    
                    # Answer: 이후의 내용을 처리
                    in_think_section = False
                    buffer = buffer[answer_index + len("answer:"):]
                    
                    # 남은 답변 내용 원본 그대로 전송
                    if buffer.strip():
                        yield buffer
                    buffer = ""
                    continue
                
                # 일반 텍스트 처리 (추론 과정이나 answer 태그가 없는 경우)
                if not in_think_section and buffer:
                    # 원본 텍스트 청크 그대로 전송
                    yield chunk_text
                    buffer = ""
            
            # 스트림 종료 후 남은 버퍼 내용 처리
            if buffer:
                if in_think_section:
                    # 남은 추론 과정이 있으면 추론 단계로 처리
                    think_content = buffer.replace("<think>", "").strip()
                    yield LLMReasoningStep(
                        step_description="Model's thinking process", 
                        details={"reasoning": think_content}
                    )
                else:
                    # 남은 일반 텍스트 원본 그대로 전송
                    yield buffer

        except Exception as e:
            yield {
                'type': 'error',
                'data': {'message': str(e), 'is_final': True}
            }
    
    async def generate_chat_response(
        self, 
        prompt: str, 
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Gemini API를 사용하여 프롬프트에 대한 비스트리밍 응답을 생성합니다.
        
        Args:
            prompt (str): 사용자 프롬프트
            conversation_history (List[Dict], optional): 이전 대화 기록
            
        Returns:
            str: 생성된 응답 텍스트
        """
        if not self.model.is_available():
            logger.error("LLM 모델이 초기화되지 않아 응답을 생성할 수 없습니다.")
            return "죄송합니다, 현재 LLM 서비스를 사용할 수 없습니다. 관리자에게 문의하세요."
        
        try:
            # 대화 기록 변환
            gemini_chat_history = []
            if conversation_history:
                for entry in conversation_history:
                    gemini_chat_history.append({
                        "role": entry.get("role", "user"),
                        "parts": [{"text": entry.get("content", "")}]
                    })
            
            # 채팅 세션 시작
            chat = self.model.create_chat(history=gemini_chat_history)
            if not chat:
                logger.error("채팅 세션 생성 실패")
                return "죄송합니다, 채팅 세션을 생성할 수 없습니다. 관리자에게 문의하세요."
            
            # 응답 생성
            response = await chat.send_message_async(prompt)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"응답 생성 중 오류 발생: {e}")
            return f"죄송합니다, 응답 생성 중에 오류가 발생했습니다: {str(e)}"
