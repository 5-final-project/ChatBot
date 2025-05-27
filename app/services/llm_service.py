# app/services/llm_service.py: Google Gemini LLM과의 상호작용을 담당하는 서비스
import google.generativeai as genai
import os
from dotenv import load_dotenv
import logging
import asyncio
from app.core.config import settings
from app.schemas.chat import RetrievedDocument, LLMReasoningStep
from typing import List, Tuple, Optional, Dict, Any, AsyncGenerator, Union
import json
import re

load_dotenv()
logger = logging.getLogger(__name__)

# MEMORY[ef1b135b-5f04-47f0-9298-3b35333c9761] - Google Gemini API 키
GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY") or settings.GOOGLE_API_KEY

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("GOOGLE_GEMINI_API_KEY 환경 변수가 설정되지 않았습니다. LLMService가 제대로 작동하지 않을 수 있습니다.")

class LLMService:
    def __init__(self):
        self.model = None
        if GEMINI_API_KEY:
            # 모델 설정 (필요에 따라 조정)
            self.generation_config = {
                "temperature": 0.7,
                "top_p": 1,
                "top_k": 1,
                "max_output_tokens": 2048,
            }
            self.safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
            try:
                self.model = genai.GenerativeModel(
                    model_name="gemini-1.5-pro-latest", # 또는 gemini-1.5-flash 등
                    generation_config=self.generation_config,
                    safety_settings=self.safety_settings
                )
                logger.info("Gemini 모델이 성공적으로 로드되었습니다.")
            except Exception as e:
                logger.error(f"Gemini 모델 로드 중 오류 발생: {e}")
        else:
            logger.error("LLMService 초기화 실패: API 키가 제공되지 않았습니다.")

    async def classify_intent(self, query: str) -> Dict[str, Any]: 
        """
        사용자의 질의 의도를 분류하고 관련 엔티티를 추출합니다.
        (예: "qna", "send_mattermost_minutes" 등 및 관련 정보)
        LLM을 사용하여 의도와 엔티티를 파악합니다.
        """
        default_entities = {}
        if not self.model:
            logger.warning("LLM 모델이 초기화되지 않아 키워드 기반 의도 분류를 시도합니다.")
            # API 설정 실패 시 키워드 기반 분류 적용
            if "회의록" in query and ("전송" in query or "매터모스트" in query or "전달" in query or "보내" in query or "공유" in query):
                # 간단한 회의 ID 추출 시도 (예시)
                match = re.search(r"회의록\s*(\S+)|(\S+)\s*회의록", query)
                if match:
                    default_entities["meeting_id"] = match.group(1) or match.group(2) or "unknown_meeting_id"
                return {"intent": "send_mattermost_minutes", "entities": default_entities, "reasoning_steps": [{"step_description": "Keyword-based intent classification (API fallback)", "details": {"reason": "Meeting document sharing keywords detected"}}]}
            elif "날씨" in query or "영화" in query or "주식" in query or "음악" in query or "식당" in query:
                return {"intent": "unsupported", "entities": default_entities, "reasoning_steps": [{"step_description": "Keyword-based intent classification (API fallback)", "details": {"reason": "Unsupported feature keywords detected"}}]}
            else:
                return {"intent": "qna", "entities": default_entities, "reasoning_steps": [{"step_description": "Keyword-based intent classification (API fallback)", "details": {"reason": "Default classification for general queries"}}]}

        # 한국어 프롬프트 템플릿 (엔티티 추출 강화)
        prompt = f"""당신은 사용자 질문의 의도를 분석하고 관련된 주요 정보를 추출하는 AI입니다.
사용자 질문을 읽고, 다음 지침에 따라 JSON 형식으로 답변해주세요.

JSON 형식:
{{
  "intent": "<분류된 의도>",
  "entities": {{
    "<엔티티1_이름>": "<엔티티1_값>",
    "<엔티티2_이름>": "<엔티티2_값>"
  }}
}}

분류 가능한 의도:
- "qna": 일반적인 질문, 정보 요청, 회의/문서 관련 질문.
  (예: "어제 회의 요약해줘", "프로젝트 X 진행 상황은?", "AI 윤리 가이드라인 찾아줘")
- "send_mattermost_minutes": 회의록이나 문서를 Mattermost로 전송 요청.
  (예: "주간 회의록 팀 채널에 보내줘", "[문서명] 매터모스트로 전달", "어제자 회의록 [사용자명/채널명]에게 공유")
  추출해야 할 엔티티: "document_name" (문서/회의록 이름 또는 ID), "target_user_or_channel" (전송 대상 사용자 또는 채널, 명시된 경우)
- "unsupported": 시스템이 지원하지 않는 기능 요청.
  (예: "오늘 날씨 어때?", "음악 틀어줘")

사용자 질문: "{query}"

분석 결과 (JSON 형식으로만 답변, 다른 설명은 절대 포함하지 마세요):
"""

        reasoning_steps = [{"step_description": "Intent classification and entity extraction prompt prepared", "details": {"prompt_length": len(prompt)}}]
        extracted_intent = "unknown"
        extracted_entities = {}

        try:
            chat = self.model.start_chat(history=[])
            response = await chat.send_message_async(prompt)
            raw_llm_response = response.text.strip()
            reasoning_steps.append({"step_description": "LLM raw response for intent/entity", "details": {"raw_llm_response": raw_llm_response}})

            # LLM 응답이 JSON 형식이라고 가정하고 파싱
            processed_llm_response = raw_llm_response
            if processed_llm_response.startswith("```json"):
                processed_llm_response = processed_llm_response[len("```json"):].strip()
            if processed_llm_response.endswith("```"):
                processed_llm_response = processed_llm_response[:-len("```")].strip()

            try:
                parsed_response = json.loads(processed_llm_response)
                extracted_intent = parsed_response.get("intent", "unknown")
                extracted_entities = parsed_response.get("entities", {})
                reasoning_steps.append({"step_description": "Successfully parsed LLM JSON response", "details": {"parsed_intent": extracted_intent, "parsed_entities": extracted_entities}})
            except json.JSONDecodeError as json_err:
                logger.warning(f"LLM 응답 JSON 파싱 실패: {json_err}. 원본 응답: {raw_llm_response}, 처리된 응답: {processed_llm_response}. 키워드 기반으로 폴백 시도.")
                reasoning_steps.append({"step_description": "LLM response JSON parsing failed", "details": {"error": str(json_err), "raw_response": raw_llm_response, "processed_response": processed_llm_response}})
                # JSON 파싱 실패 시, 기존 키워드 기반 로직으로 폴백 (간단화된 버전)
                if "send_mattermost_minutes" in raw_llm_response or ("회의록" in query and ("전송" in query or "보내" in query or "공유" in query)):
                    extracted_intent = "send_mattermost_minutes"
                elif "qna" in raw_llm_response:
                    extracted_intent = "qna"
                elif "unsupported" in raw_llm_response:
                    extracted_intent = "unsupported"
                else:
                    extracted_intent = "qna" # 기본값
                # 엔티티 추출은 이 경우 어려우므로 비워둠

            # 최종 결과 구성
            result = {
                "intent": extracted_intent,
                "entities": extracted_entities,
                "reasoning_steps": reasoning_steps
            }
            logger.info(f"Intent classification result: {result}")
            return result

        except Exception as e:
            error_message = f"Error during intent classification with Gemini: {e}"
            logger.error(error_message, exc_info=True)
            reasoning_steps.append({"step_description": "Error during LLM call for intent classification", "details": {"error": str(e)}})
            # LLM 오류 시 키워드 기반으로 대체 (위의 fallback과 유사하게)
            if "회의록" in query and ("전송" in query or "매터모스트" in query or "전달" in query or "보내" in query or "공유" in query):
                match = re.search(r"회의록\s*(\S+)|(\S+)\s*회의록", query)
                if match:
                    default_entities["meeting_id"] = match.group(1) or match.group(2) or "unknown_meeting_id"
                return {"intent": "send_mattermost_minutes", "entities": default_entities, "reasoning_steps": reasoning_steps}
            elif "날씨" in query or "영화" in query or "주식" in query or "음악" in query or "식당" in query:
                return {"intent": "unsupported", "entities": default_entities, "reasoning_steps": reasoning_steps}
            else:
                return {"intent": "qna", "entities": default_entities, "reasoning_steps": reasoning_steps}

    async def generate_response_stream(self, prompt: str, retrieved_chunks: list = None, conversation_history: list = None) -> AsyncGenerator[Union[str, LLMReasoningStep], None]:
        """
        Gemini API를 사용하여 프롬프트에 대한 응답을 스트리밍 방식으로 생성합니다.
        대화 맥락을 유지하기 위해 이전 대화 기록을 활용합니다.
        이 메서드는 LLM의 추론 단계(LLMReasoningStep) 또는 순수한 텍스트 조각(str)을 반환합니다.
        
        Args:
            prompt (str): 사용자 질문
            retrieved_chunks (list, optional): RAG에서 검색된 문서 조각들 (문자열 리스트여야 함)
            conversation_history (list, optional): 이전 대화 기록 목록
        """
        if not self.model:
            logger.error("LLM 모델이 초기화되지 않아 스트리밍을 시작할 수 없습니다.")
            # 호출하는 쪽에서 이 경우를 처리하거나, 여기서 특정 예외를 발생시킬 수 있습니다.
            # 여기서는 간단히 빈 async generator로 만듭니다.
            if False: # 이 블록은 실행되지 않지만 async generator를 유지하기 위함
                yield "LLM 모델이 초기화되지 않았습니다."
            return

        try:
            gemini_chat_history_for_model = []
            if conversation_history:
                gemini_chat_history_for_model.extend(conversation_history)
            
            # 시스템 메시지 (추론 과정 출력 요청 포함)
            # Gemini는 명시적인 system role을 첫 번째 user 메시지에 합치거나, 튜닝된 모델을 사용해야 합니다.
            # 여기서는 프롬프트 시작 부분에 지시사항을 추가합니다.
            system_instruction = (
                "당신은 친절하고 상세하게 답변하는 AI 어시스턴트입니다. "
                "사용자의 질문에 답변할 때, 당신의 생각 과정을 단계별로 설명해주세요. "
                "각 생각 단계는 반드시 `[THOUGHT]`로 시작하고 `[/THOUGHT]`로 끝나야 합니다. "
                "예시: `[THOUGHT] 사용자의 질문 의도를 파악합니다. 질문은 X에 관한 것입니다. [/THOUGHT]` "
                "최종 답변은 생각 단계를 제외하고 명확하게 전달해주세요."
            )

            current_user_message_parts_text = f"{system_instruction}\n\n사용자 질문: {prompt}"

            if retrieved_chunks:
                context_text = "\n\n--- 참고 문서 조각 ---"
                for i, chunk_content in enumerate(retrieved_chunks):
                    # content_chunk가 객체일 수 있으므로 문자열로 변환
                    chunk_str = str(chunk_content.content_chunk if hasattr(chunk_content, 'content_chunk') else chunk_content)
                    context_text += f"\n문서 {i+1}: {chunk_str}"
                current_user_message_parts_text += f"{context_text}"
            
            gemini_chat_history_for_model.append({
                "role": "user",
                "parts": [current_user_message_parts_text]
            })

            # 이전 응답이 있다면 모델 역할로 추가 (Gemini는 user/model 턴을 번갈아 사용)
            # 이 부분은 conversation_history가 이미 올바른 role을 가지고 있다고 가정합니다.
            # 만약 마지막 메시지가 user였다면, LLM은 model로 응답해야 합니다.
            # 여기서는 단순화를 위해 history가 올바르게 구성되었다고 가정합니다.

            chat_session = self.model.start_chat(history=gemini_chat_history_for_model)
            
            logger.debug(f"Sending prompt to Gemini for QnA: {current_user_message_parts_text}")
            logger.debug(f"Gemini chat history for QnA: {gemini_chat_history_for_model}")

            # 스트리밍 응답 요청
            # Gemini API는 send_message_async를 사용하고, response.stream = True 설정이 필요할 수 있습니다.
            # google-generativeai 라이브러리는 기본적으로 stream=True로 동작하는 경우가 많습니다.
            # 여기서는 response.text가 아닌, response 객체를 순회하며 청크를 받습니다.
            response_stream = await chat_session.send_message_async(current_user_message_parts_text, stream=True)

            buffer = ""
            async for chunk in response_stream:
                if not chunk.parts:
                    continue
                chunk_text = chunk.parts[0].text
                buffer += chunk_text

                # [THOUGHT] ... [/THOUGHT] 패턴 처리
                while True:
                    start_tag_index = buffer.find("[THOUGHT]")
                    if start_tag_index == -1:
                        break # 시작 태그 없음

                    # 시작 태그 이전의 텍스트가 있다면 일반 텍스트로 yield
                    if start_tag_index > 0:
                        yield buffer[:start_tag_index]
                        buffer = buffer[start_tag_index:]
                        start_tag_index = 0 # 버퍼가 업데이트되었으므로 인덱스 재설정
                    
                    end_tag_index = buffer.find("[/THOUGHT]", start_tag_index)
                    if end_tag_index == -1:
                        # 종료 태그가 아직 도착하지 않음, 다음 청크 대기
                        break
                    
                    # [THOUGHT]와 [/THOUGHT] 사이의 내용 추출
                    thought_content = buffer[start_tag_index + len("[THOUGHT]"):end_tag_index].strip()
                    yield LLMReasoningStep(step_description=thought_content) # LLMReasoningStep 객체 yield
                    
                    # 처리된 부분 버퍼에서 제거
                    buffer = buffer[end_tag_index + len("[/THOUGHT]"):]

            # 스트림 종료 후 남은 버퍼 내용 처리
            if buffer:
                yield buffer

        except Exception as e:
            error_message = f"Error during Gemini stream generation: {e}"
            logger.error(error_message, exc_info=True)
            # 오류 발생 시 LLMReasoningStep 또는 텍스트로 오류 알림
            yield LLMReasoningStep(step_description="LLM 응답 생성 중 오류 발생", details={"error": str(e)})
            yield f"오류: {error_message}"

    async def rewrite_query(self, original_query: str) -> str:
        """
        사용자 질의를 LLM이 더 잘 이해할 수 있도록 재작성합니다.
        이 과정에서 다음을 수행합니다:
        1. 불필요한 단어나 구문 제거
        2. 모호한 표현 명확화
        3. 맥락에 맞는 키워드 강조
        4. 질문의 의도 명확화
        
        Args:
            original_query (str): 사용자의 원본 질의
            
        Returns:
            str: 재작성된 질의
        """
        if not self.model:
            logger.warning("LLM 모델이 초기화되지 않아 원본 쿼리를 그대로 반환합니다.")
            return original_query
            
        try:
            # 쿼리 재작성을 위한 프롬프트 구성
            rewrite_prompt = f"""
            다음 질문을 더 명확하고 검색하기 좋은 형태로 다시 작성해주세요. 
            원래 질문의 의미는 유지하되, 다음을 개선해주세요:
            - 불필요한 단어 제거
            - 모호한 표현 구체화
            - 중요 키워드 포함
            - 검색에 유용한 형태로 구조화
            
            결과는 재작성된 질문만 출력하고, 다른 설명은 포함하지 마세요.
            
            원본 질문: {original_query}
            재작성된 질문:
            """
            
            # 재작성 결과 생성 (스트리밍 없이 한 번에 처리)
            response = await self.model.generate_content_async(rewrite_prompt)
            rewritten_query = response.text.strip()
            
            # 재작성된 쿼리가 비어있거나 너무 짧은 경우 원본 사용
            if not rewritten_query or len(rewritten_query) < 5:
                logger.warning("쿼리 재작성 결과가 너무 짧아 원본 쿼리를 사용합니다.")
                return original_query
                
            logger.info(f"쿼리 재작성: '{original_query}' -> '{rewritten_query}'")
            return rewritten_query
            
        except Exception as e:
            logger.error(f"쿼리 재작성 중 오류 발생: {e}")
            # 오류 발생 시 원본 쿼리 반환
            return original_query

# 이 서비스의 함수들은 workflow_service.py에서 호출되어 사용됩니다.
