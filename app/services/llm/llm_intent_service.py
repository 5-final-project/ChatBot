"""
LLM 의도 분류 서비스
사용자 질의의 의도를 분석하고 분류하는 기능을 제공합니다.
"""
import logging
import json
import re
import traceback
from typing import Dict, Any
from app.services.llm.llm_core import gemini_model

logger = logging.getLogger(__name__)

class IntentService:
    """사용자 질의의 의도를 분석하고 분류하는 서비스"""
    
    def __init__(self):
        """의도 분류 서비스를 초기화합니다."""
        self.model = gemini_model
    
    async def classify_intent(self, query: str) -> Dict[str, Any]:
        """
        사용자의 질의 의도를 분류하고 관련 엔티티를 추출합니다.
        
        Args:
            query (str): 사용자 질의 내용
            
        Returns:
            Dict[str, Any]: 의도 분류 결과 및 엔티티 정보
        """
        default_entities = {}
        
        # LLM 모델 사용 불가능 시 키워드 기반 분류 사용
        if not self.model.is_available():
            logger.warning("LLM 모델이 초기화되지 않아 키워드 기반 의도 분류를 시도합니다.")
            return self._classify_intent_by_keywords(query)
        
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

        reasoning_steps = [{
            "step_description": "Intent classification and entity extraction prompt prepared", 
            "details": {"prompt_length": len(prompt)}
        }]
        
        extracted_intent = "unknown"
        extracted_entities = {}
        
        try:
            # Gemini API 호출
            chat = self.model.create_chat()
            if not chat:
                logger.error("채팅 세션 생성 실패, 키워드 기반 분류로 대체합니다")
                return self._classify_intent_by_keywords(query)
            
            response = await chat.send_message_async(prompt)
            raw_llm_response = response.text.strip()
            
            reasoning_steps.append({
                "step_description": "LLM raw response for intent/entity", 
                "details": {"raw_llm_response": raw_llm_response}
            })
            
            # LLM 응답 파싱
            processed_llm_response = self._clean_json_response(raw_llm_response)
            
            try:
                parsed_response = json.loads(processed_llm_response)
                extracted_intent = parsed_response.get("intent", "unknown")
                extracted_entities = parsed_response.get("entities", {})
                
                reasoning_steps.append({
                    "step_description": "LLM response parsed successfully",
                    "details": {
                        "parsed_intent": extracted_intent, 
                        "parsed_entities": extracted_entities
                    }
                })
                
                return {
                    "intent": extracted_intent, 
                    "entities": extracted_entities, 
                    "reasoning_steps": reasoning_steps
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"LLM 응답 JSON 파싱 오류: {e}. 응답: {processed_llm_response}")
                reasoning_steps.append({
                    "step_description": "LLM response JSON parsing error", 
                    "details": {"error": str(e), "raw_response": processed_llm_response}
                })
                
                # 파싱 실패 시 키워드 기반 분류로 폴백
                keyword_result = self._classify_intent_by_keywords(query)
                keyword_result["reasoning_steps"] = reasoning_steps + keyword_result.get("reasoning_steps", [])
                return keyword_result
                
        except Exception as e:
            logger.error(f"LLM 호출 중 오류 발생: {e}")
            logger.error(traceback.format_exc())
            
            reasoning_steps.append({
                "step_description": "LLM call error", 
                "details": {"error": str(e)}
            })
            
            # 오류 발생 시 키워드 기반 분류로 폴백
            keyword_result = self._classify_intent_by_keywords(query)
            keyword_result["reasoning_steps"] = reasoning_steps + keyword_result.get("reasoning_steps", [])
            return keyword_result
    
    def _clean_json_response(self, response: str) -> str:
        """
        LLM 응답에서 JSON 부분을 추출하고 정리합니다.
        
        Args:
            response (str): LLM 원본 응답
            
        Returns:
            str: 정리된 JSON 문자열
        """
        # 코드 블록 마크다운 제거
        if "```json" in response:
            response = response.split("```json", 1)[1]
        
        if "```" in response:
            response = response.split("```", 1)[0]
        
        # 앞뒤 공백 제거
        return response.strip()
    
    def _classify_intent_by_keywords(self, query: str) -> Dict[str, Any]:
        """
        키워드 기반 간단한 의도 분류 (LLM 폴백용)
        
        Args:
            query (str): 사용자 질의 내용
            
        Returns:
            Dict[str, Any]: 의도 분류 결과 및 엔티티 정보
        """
        default_entities = {}
        
        # 회의록 전송 관련 키워드 검사
        if "회의록" in query and ("전송" in query or "매터모스트" in query or "전달" in query or "보내" in query or "공유" in query):
            # 간단한 회의 ID 추출 시도
            match = re.search(r"회의록\s*(\S+)|(\S+)\s*회의록", query)
            if match:
                default_entities["meeting_id"] = match.group(1) or match.group(2) or "unknown_meeting_id"
            
            return {
                "intent": "send_mattermost_minutes", 
                "entities": default_entities, 
                "reasoning_steps": [{
                    "step_description": "Keyword-based intent classification", 
                    "details": {"reason": "Meeting document sharing keywords detected"}
                }]
            }
        
        # 지원하지 않는 기능 관련 키워드 검사
        elif "날씨" in query or "영화" in query or "주식" in query or "음악" in query or "식당" in query:
            return {
                "intent": "unsupported", 
                "entities": default_entities, 
                "reasoning_steps": [{
                    "step_description": "Keyword-based intent classification", 
                    "details": {"reason": "Unsupported feature keywords detected"}
                }]
            }
        
        # 기본값: 일반 Q&A 의도
        else:
            return {
                "intent": "qna", 
                "entities": default_entities, 
                "reasoning_steps": [{
                    "step_description": "Keyword-based intent classification", 
                    "details": {"reason": "Default classification for general queries"}
                }]
            }
