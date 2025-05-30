"""
LLM 스트리밍 서비스
Google Gemini API의 스트리밍 응답을 처리하는 기능을 제공합니다.
"""
import logging
import asyncio
import time
import json
from typing import List, Dict, Any, AsyncGenerator, Union, Optional
from google import genai
from google.genai import types

from app.services.llm.llm_core import gemini_model
from app.schemas.chat import LLMReasoningStep, RetrievedDocument

logger = logging.getLogger(__name__)

class StreamingService:
    """Google Gemini API의 스트리밍 응답을 처리하는 서비스"""
    
    def __init__(self):
        """스트리밍 서비스를 초기화합니다."""
        self.model = gemini_model
        # 스트리밍 설정
        self.stream_chunk_size = 30  # 30글자마다 전송
        self.stream_delay = 0.3      # 또는 0.3초마다 전송
        # 디버깅 모드 설정
        self.debug_mode = True
    
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
            logger.error("LLM 모델이 사용 불가능합니다.")
            yield {
                'type': 'error', 
                'data': {'message': 'LLM 서비스 불가', 'is_final': True}
            }
            return

        try:
            # 대화 기록 변환
            gemini_chat_history = []
            if conversation_history:
                # 대화 기록 처리는 llm_core의 _process_history 메서드로 이미 처리됨
                gemini_chat_history = self.model._process_history(conversation_history)
                logger.debug(f"대화 기록 변환 완료: {len(gemini_chat_history)}개 메시지")
            
            # 시스템 인스트럭션 및 프롬프트 구성
            system_instruction = (
                "당신은 사용자 질문에 답변하는 AI 어시스턴트입니다.\n"
                "당신은 사용자와의 이전 대화 기록을 기억하고, 이를 활용하여 대화의 맥락을 유지해야 합니다.\n"
                "최종 답변은 반드시 한국어로 작성해야 합니다."
            )
            
            # 사용자 프롬프트가 비어있는지 확인하고 로깅
            if not prompt or prompt.strip() == "":
                logger.error("사용자 프롬프트가 비어 있습니다.")
                yield "사용자 질문이 비어 있습니다. 질문을 입력해주세요."
                return
            
            # 대화 기록 요약 생성
            conversation_summary = ""
            if gemini_chat_history:
                conversation_summary = "=== 이전 대화 기록 ===\n"
                for entry in gemini_chat_history:
                    # 사전 형식으로 변경된 대화 기록 처리
                    role = "사용자" if entry.get('role') == "user" else "어시스턴트"
                    
                    # parts 배열에서 텍스트 추출
                    text = ""
                    if 'parts' in entry and entry['parts'] and len(entry['parts']) > 0:
                        if isinstance(entry['parts'][0], dict) and 'text' in entry['parts'][0]:
                            text = entry['parts'][0]['text']
                        elif isinstance(entry['parts'][0], str):
                            text = entry['parts'][0]
                    
                    if text:
                        conversation_summary += f"{role}: {text[:200]}{'...' if len(text) > 200 else ''}\n"
                conversation_summary += "===================\n\n"
            
            user_message_text = f"{system_instruction}\n\n{conversation_summary}사용자 질문: {prompt.strip()}"
            logger.debug(f"사용자 메시지 생성 완료: {len(user_message_text)}자")
            
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
                logger.debug(f"검색된 문서 {len(retrieved_documents)}개 추가됨")
            
            # 최종 메시지 길이 확인
            logger.debug(f"최종 메시지 길이: {len(user_message_text)}자")
            
            # 메시지 전송 전 최종 확인
            if not user_message_text or user_message_text.strip() == "":
                logger.error("LLM에 전송할 메시지가 비어 있습니다.")
                yield "메시지 생성 중 오류가 발생했습니다. 다시 시도해주세요."
                return
            
            # 응답 생성 (스트리밍)
            try:
                logger.info("스트리밍 응답 생성 시작")
                
                # 생성 설정 준비 - 생각 기능 활성화
                generation_config = types.GenerateContentConfig(
                    temperature=0.7,
                    top_p=1,
                    top_k=1,
                    max_output_tokens=2048,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=5000,  # 충분한 예산 설정
                        include_thoughts=True  # 추론 과정 항상 포함
                    )
                )
                
                # 응답 생성 (스트리밍)
                response_stream = self.model.client.models.generate_content_stream(
                    model=self.model.model_name,
                    contents=user_message_text,
                    config=generation_config
                )
                
                # 디버깅 모드일 때 처음 몇 개의 청크 구조를 로깅
                debug_chunk_count = 0
                debug_max_chunks = 5
                
                # 추론 과정을 모으는 버퍼
                thought_buffer = ""
                in_thought_phase = False
                
                # 스트림 처리 시작
                try:
                    # 청크가 도착할 때마다 바로 처리
                    # 일반 제너레이터이므로 async for 대신 for 루프 사용
                    for chunk in response_stream:
                        # 디버깅 - 처음 몇 개 청크 로깅
                        if self.debug_mode and debug_chunk_count < debug_max_chunks:
                            try:
                                chunk_repr = repr(chunk)
                                logger.info(f"청크 {debug_chunk_count+1} 구조: {chunk_repr[:500]}...")
                                
                                # 청크에서 사고 과정 필드 찾기 시도
                                if hasattr(chunk, 'candidates'):
                                    logger.info(f"청크 {debug_chunk_count+1}에 candidates 속성 있음")
                                    for j, candidate in enumerate(chunk.candidates):
                                        if hasattr(candidate, 'content'):
                                            logger.info(f"후보 {j+1}에 content 속성 있음")
                                            content = candidate.content
                                            # content 객체의 모든 속성 확인
                                            attrs = [attr for attr in dir(content) if not attr.startswith('_')]
                                            logger.info(f"content 속성들: {attrs}")
                                            
                                            # 가능한 '사고' 관련 속성 확인
                                            for attr in ['thought', 'thoughts', 'thinking', 'thinking_process', 'reasoning']:
                                                if hasattr(content, attr):
                                                    logger.info(f"사고 과정 속성 발견: {attr}")
                                            
                                            # parts 속성 확인
                                            if hasattr(content, 'parts'):
                                                logger.info(f"parts 속성 있음, 길이: {len(content.parts)}")
                                                for k, part in enumerate(content.parts):
                                                    part_attrs = [attr for attr in dir(part) if not attr.startswith('_')]
                                                    logger.info(f"part {k+1} 속성들: {part_attrs}")
                                                    
                                                    # text와 thought 속성 확인
                                                    if hasattr(part, 'text'):
                                                        logger.info(f"part {k+1}에 text 속성 있음")
                                                    if hasattr(part, 'thought'):
                                                        logger.info(f"part {k+1}에 thought 속성 있음: {part.thought}")
                            except Exception as chunk_error:
                                logger.error(f"청크 분석 중 오류: {chunk_error}")
                            
                            debug_chunk_count += 1
                        
                        # 청크에서 추론 과정 및 텍스트 추출
                        if hasattr(chunk, 'candidates') and chunk.candidates:
                            for candidate in chunk.candidates:
                                if hasattr(candidate, 'content') and candidate.content and hasattr(candidate.content, 'parts') and candidate.content.parts:
                                    for part in candidate.content.parts:
                                        # 추론 과정(thought=True)과 일반 텍스트를 구분
                                        if hasattr(part, 'thought') and part.thought is True:
                                            # 추론 과정 발견 - 즉시 스트리밍
                                            if hasattr(part, 'text') and part.text:
                                                # 추론 시작 또는 계속 중
                                                text_to_send = part.text
                                                
                                                # 추론 시작시 <think> 태그 추가
                                                if not in_thought_phase:
                                                    in_thought_phase = True
                                                    text_to_send = f"<think>{text_to_send}"
                                                    logger.debug("추론 시작 태그 추가")
                                                
                                                # 스트리밍 추론 청크 전송 - LLM_REASONING_STEP이 아닌 CONTENT 타입으로 전송
                                                yield {
                                                    "type": "CONTENT",
                                                    "data": {"text": text_to_send, "is_final": False},
                                                    "timestamp": int(time.time() * 1000)
                                                }
                                                logger.debug(f"추론 청크 전송: {text_to_send[:30]}...")
                                        elif hasattr(part, 'text') and part.text:
                                            # 일반 텍스트 발견
                                            
                                            # 추론 과정이 끝났으면 </think> 태그 추가
                                            if in_thought_phase:
                                                # 추론 종료 태그 전송
                                                yield {
                                                    "type": "CONTENT",
                                                    "data": {"text": "</think>", "is_final": False},
                                                    "timestamp": int(time.time() * 1000)
                                                }
                                                in_thought_phase = False
                                                logger.debug("추론 종료 태그 추가")
                                            
                                            # 일반 텍스트 전송
                                            yield {
                                                "type": "CONTENT",
                                                "data": {"text": part.text, "is_final": False},
                                                "timestamp": int(time.time() * 1000)
                                            }
                                            logger.debug(f"텍스트 청크 전송: {part.text[:30]}...")
                        
                        # 비동기 함수에서 일반 루프를 사용할 때, 다른 태스크가 실행될 수 있도록 
                        # 짧은 대기 시간을 추가합니다.
                        await asyncio.sleep(0.01)
                    
                    # 마지막 추론 과정이 끝나지 않은 경우 종료 태그 추가
                    if in_thought_phase:
                        yield {
                            "type": "CONTENT",
                            "data": {"text": "</think>", "is_final": False},
                            "timestamp": int(time.time() * 1000)
                        }
                        in_thought_phase = False
                        logger.debug("마지막 추론 종료 태그 추가")
                    
                except asyncio.CancelledError:
                    logger.info("스트리밍 작업 취소됨")
                    raise  # 예외를 다시 발생시켜 외부에서 처리하도록 함
                except Exception as e:
                    logger.error(f"스트리밍 처리 중 오류: {e}", exc_info=True)
                    yield {
                        'type': 'error',
                        'data': {'message': '스트리밍 처리 중 오류 발생', 'is_final': True},
                        'timestamp': int(time.time() * 1000)
                    }
                finally:
                    # 마지막 END 이벤트 전송
                    yield {
                        "type": "END",
                        "data": {"message": "Stream ended", "is_final": True},
                        "timestamp": int(time.time() * 1000)
                    }
                    logger.info("스트리밍 응답 처리 완료")

            except Exception as e:
                # 오류 메시지에서 차단된 프롬프트인지 확인
                if 'BlockedPrompt' in str(e) or 'blocked' in str(e).lower():
                    logger.error(f"프롬프트 차단 오류: {e}")
                    block_reason = getattr(e, 'block_reason_message', '부적절한 콘텐츠')
                    yield {
                        'type': 'error',
                        'data': {
                            'message': f"프롬프트가 부적절한 콘텐츠로 인해 차단되었습니다. 이유: {block_reason}",
                            'is_final': True
                        },
                        'timestamp': int(time.time() * 1000)
                    }
                else:
                    logger.error(f"응답 생성 중 오류: {e}", exc_info=True)
                    yield {
                        'type': 'error',
                        'data': {'message': f"LLM 응답 생성 중 오류 발생: {str(e)}", 'is_final': True},
                        'timestamp': int(time.time() * 1000)
                    }
            finally:
                logger.info("스트리밍 응답 생성 종료")
                # END 이벤트는 router 단에서 관리하므로 여기서는 보내지 않음

        except Exception as e:
            logger.error(f"LLM 응답 처리 중 오류 발생: {e}", exc_info=True)
            yield {
                'type': 'error',
                'data': {'message': f"오류: {str(e)}", 'is_final': True}
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
            # 생성 설정 준비
            generation_config = types.GenerateContentConfig(
                temperature=0.7,
                top_p=1,
                top_k=1,
                max_output_tokens=2048,
                thinking_config=types.ThinkingConfig(
                    thinking_budget=5000
                )
            )
            
            # 응답 생성
            response = self.model.client.models.generate_content(
                model=self.model.model_name,
                contents=prompt,
                config=generation_config
            )
            
            # 디버깅 - 응답 구조 확인
            if self.debug_mode:
                try:
                    logger.info(f"응답 구조: {repr(response)[:500]}...")
                    
                    # 응답의 모든 속성 확인
                    attrs = [attr for attr in dir(response) if not attr.startswith('_')]
                    logger.info(f"응답 속성들: {attrs}")
                    
                    # candidates 확인
                    if hasattr(response, 'candidates'):
                        logger.info(f"candidates 수: {len(response.candidates)}")
                        for i, candidate in enumerate(response.candidates):
                            if hasattr(candidate, 'content'):
                                content = candidate.content
                                content_attrs = [attr for attr in dir(content) if not attr.startswith('_')]
                                logger.info(f"content {i+1} 속성들: {content_attrs}")
                except Exception as debug_error:
                    logger.error(f"응답 디버깅 중 오류: {debug_error}")
            
            # 응답 처리
            thinking_text = ""
            response_text = ""
            
            # 응답 구조에 따른 처리
            if hasattr(response, 'candidates') and response.candidates:
                for candidate in response.candidates:
                    if hasattr(candidate, 'content'):
                        content = candidate.content
                        
                        # 사고 과정 추출 시도 (여러 가능한 속성 확인)
                        for attr in ['thought', 'thoughts', 'thinking', 'thinking_process', 'reasoning']:
                            if hasattr(content, attr):
                                attr_value = getattr(content, attr)
                                if attr_value:
                                    thinking_text += str(attr_value)
                                    logger.info(f"사고 과정 감지: {attr}={attr_value[:100]}...")
                        
                        # 일반 텍스트 추출
                        if hasattr(content, 'parts'):
                            for part in content.parts:
                                if hasattr(part, 'text') and part.text:
                                    # part.thought 속성 확인
                                    if hasattr(part, 'thought') and part.thought:
                                        thinking_text += part.text
                                    else:
                                        response_text += part.text
            
            # 단순 텍스트 응답 처리
            elif hasattr(response, 'text'):
                response_text = response.text
            
            # 사고 과정이 없으면 에러 발생
            if not thinking_text:
                error_message = "오류: LLM이 사고 과정을 생성하지 않았습니다. 모델 설정을 확인하세요."
                logger.error(error_message)
                return error_message
            
            # 사고와 응답 결합
            if thinking_text:
                return f"<think>{thinking_text}</think>{response_text}"
            else:
                return response_text
            
        except Exception as e:
            logger.error(f"응답 생성 중 오류 발생: {e}")
            return f"죄송합니다, 응답 생성 중에 오류가 발생했습니다: {str(e)}"
