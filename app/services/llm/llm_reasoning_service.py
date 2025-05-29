"""
LLM 추론 서비스
LLM의 추론 단계를 처리하고 구조화하는 기능을 제공합니다.
"""
import logging
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from app.schemas.chat import LLMReasoningStep

logger = logging.getLogger(__name__)

class ReasoningService:
    """LLM의 추론 단계를 처리하고 구조화하는 서비스"""
    
    def __init__(self):
        """추론 서비스를 초기화합니다."""
        pass
    
    def extract_reasoning_steps(self, content: str) -> Tuple[List[LLMReasoningStep], str]:
        """
        LLM 응답에서 추론 단계를 추출하고, 정제된 응답 텍스트를 반환합니다.
        
        Args:
            content (str): LLM 원본 응답 텍스트
            
        Returns:
            Tuple[List[LLMReasoningStep], str]: 추출된 추론 단계 목록과 정제된 응답 텍스트
        """
        reasoning_steps = []
        cleaned_content = content
        
        # [THOUGHT]...[/THOUGHT] 패턴 추출
        thought_pattern = r'\[THOUGHT\](.*?)\[\/THOUGHT\]'
        matches = re.finditer(thought_pattern, content, re.DOTALL)
        
        offset = 0
        for match in matches:
            # 추론 단계 추출 및 저장
            thought_text = match.group(1).strip()
            reasoning_steps.append(LLMReasoningStep(step_description=thought_text))
            
            # 추출된 부분을 원본 텍스트에서 제거
            start_pos = match.start() - offset
            end_pos = match.end() - offset
            cleaned_content = cleaned_content[:start_pos] + cleaned_content[end_pos:]
            offset += end_pos - start_pos
        
        # 연속된 공백 및 줄바꿈 정리
        cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content)
        cleaned_content = re.sub(r'  +', ' ', cleaned_content)
        cleaned_content = cleaned_content.strip()
        
        return reasoning_steps, cleaned_content
    
    def parse_reasoning_json(self, content: str) -> Optional[Dict[str, Any]]:
        """
        LLM 응답에서 JSON 형식의 추론 데이터를 파싱합니다.
        
        Args:
            content (str): LLM 응답 텍스트
            
        Returns:
            Optional[Dict[str, Any]]: 파싱된 JSON 데이터 또는 None
        """
        # JSON 블록 추출
        json_pattern = r'```json\s*(.*?)\s*```'
        match = re.search(json_pattern, content, re.DOTALL)
        
        if match:
            try:
                json_text = match.group(1).strip()
                return json.loads(json_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON 파싱 오류: {e}")
                return None
        
        # 일반 텍스트에서 JSON 형식 찾기 시도
        try:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = content[json_start:json_end]
                return json.loads(json_text)
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"JSON 추출 시도 실패: {e}")
            return None
        
        return None
    
    def format_reasoning_steps(self, reasoning_steps: List[LLMReasoningStep]) -> str:
        """
        추론 단계를 사용자에게 표시하기 위한 텍스트로 포맷팅합니다.
        
        Args:
            reasoning_steps (List[LLMReasoningStep]): 추론 단계 목록
            
        Returns:
            str: 포맷된 추론 단계 텍스트
        """
        if not reasoning_steps:
            return ""
        
        result = "💭 **추론 과정:**\n\n"
        
        for i, step in enumerate(reasoning_steps):
            result += f"**단계 {i+1}**: {step.step_description}\n\n"
        
        return result
