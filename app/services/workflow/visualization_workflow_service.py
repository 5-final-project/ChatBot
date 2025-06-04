import logging
from typing import Dict, Any, List, Optional
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.services.chat.llm_service import LLMService
from app.services.visualization.visualization_service import VisualizationService
from app.schemas.visualization import ChartType
from app.schemas.chat import ChatMessage, ChatCompletionResponse

logger = logging.getLogger(__name__)

class VisualizationWorkflowService:
    """
    시각화 워크플로우를 처리하는 서비스입니다.
    """
    
    def __init__(
        self,
        llm_service: LLMService,
        visualization_service: VisualizationService
    ):
        """
        시각화 워크플로우 서비스를 초기화합니다.
        
        Args:
            llm_service (LLMService): LLM 서비스
            visualization_service (VisualizationService): 시각화 서비스
        """
        self.llm_service = llm_service
        self.visualization_service = visualization_service
        logger.info("시각화 워크플로우 서비스 초기화됨")
    
    async def process_visualization_request(
        self,
        meeting_content: str,
        query: str,
        chart_type: Optional[ChartType] = None
    ) -> Dict[str, Any]:
        """
        시각화 요청을 처리합니다.
        
        Args:
            meeting_content (str): 회의 내용
            query (str): 시각화 요청 쿼리
            chart_type (Optional[ChartType]): 차트 타입
            
        Returns:
            Dict[str, Any]: 시각화 결과
        """
        # 1. LLM을 사용하여 회의 내용에서 데이터 추출
        data = await self.extract_data_for_visualization(meeting_content, query, chart_type)
        
        # 2. 추출된 데이터로 시각화 생성
        result = await self.visualization_service.create_visualization(
            chart_type=data.get("chart_type", chart_type.value if chart_type else "pie"),
            data=data.get("data", {}),
            title=data.get("title", "시각화")
        )
        
        return result
    
    async def process_visualization_request_stream(
        self,
        meeting_content: str,
        query: str,
        chart_type: Optional[ChartType] = None
    ):
        """
        시각화 요청을 처리하고 스트리밍 응답으로 반환합니다.
        
        Args:
            meeting_content (str): 회의 내용
            query (str): 시각화 요청 쿼리
            chart_type (Optional[ChartType]): 차트 타입
            
        Returns:
            EventSourceResponse: 스트리밍 응답
        """
        async def event_generator():
            try:
                # 1. LLM을 사용하여 회의 내용에서 데이터 추출
                data = await self.extract_data_for_visualization(meeting_content, query, chart_type)
                
                # 2. 추출된 데이터로 시각화 생성 (스트림 모드)
                async for chunk in self.visualization_service.generate_visualization(
                    chart_type=data.get("chart_type", chart_type.value if chart_type else "pie"),
                    data=data.get("data", {}),
                    title=data.get("title", "시각화")
                ):
                    yield chunk
            except Exception as e:
                logger.error(f"시각화 워크플로우 오류: {str(e)}")
                yield {
                    "type": "error",
                    "data": {"message": f"시각화 생성 중 오류 발생: {str(e)}"}
                }
        
        return EventSourceResponse(event_generator())
    
    async def extract_data_for_visualization(
        self,
        meeting_content: str,
        query: str,
        chart_type: Optional[ChartType] = None
    ) -> Dict[str, Any]:
        """
        회의 내용에서 시각화에 필요한 데이터를 추출합니다.
        
        Args:
            meeting_content (str): 회의 내용
            query (str): 시각화 요청 쿼리
            chart_type (Optional[ChartType]): 차트 타입
            
        Returns:
            Dict[str, Any]: 추출된 데이터
        """
        # LLM 프롬프트 구성
        system_prompt = """
        당신은 회의 내용을 분석하여 시각화에 필요한 데이터를 추출하는 전문가입니다.
        사용자의 질문과 회의 내용을 분석하여, 요청된 시각화에 필요한 데이터를 JSON 형식으로 추출해주세요.
        
        응답은 다음 JSON 형식으로 작성해주세요:
        {
            "chart_type": "pie", // 적절한 차트 타입 (pie, bar, timeline 중 선택)
            "title": "차트 제목",
            "data": {
                // pie 차트의 경우
                "labels": ["항목1", "항목2", ...],
                "values": [100, 200, ...],
                
                // bar 차트의 경우
                "labels": ["항목1", "항목2", ...],
                "values": [100, 200, ...],
                "categories": ["카테고리1", "카테고리2", ...], // 선택 사항
                
                // timeline 차트의 경우
                "events": ["이벤트1", "이벤트2", ...],
                "dates": ["2023-01-01", "2023-02-01", ...],
                "descriptions": ["설명1", "설명2", ...] // 선택 사항
            }
        }
        
        회의 내용에서 직접적인 숫자나 데이터를 찾을 수 없는 경우, 맥락에서 합리적으로 추론하여 데이터를 생성해주세요.
        """
        
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=f"""
            회의 내용:
            ---
            {meeting_content}
            ---
            
            시각화 요청: {query}
            {f'차트 타입: {chart_type.value}' if chart_type else ''}
            """)
        ]
        
        # LLM 호출
        try:
            response = await self.llm_service.chat_completion(messages)
            
            if isinstance(response, ChatCompletionResponse):
                content = response.choices[0].message.content
            else:
                content = response
            
            # JSON 응답 파싱
            import json
            import re
            
            # JSON 블록 추출
            json_match = re.search(r'```json\n([\s\S]*?)\n```|{[\s\S]*}', content)
            if json_match:
                json_str = json_match.group(1) if json_match.group(1) else json_match.group(0)
                data = json.loads(json_str)
            else:
                # JSON 형식이 아닌 경우 기본값 설정
                data = {
                    "chart_type": chart_type.value if chart_type else "pie",
                    "title": "데이터 시각화",
                    "data": {
                        "labels": ["데이터 없음"],
                        "values": [100]
                    }
                }
            
            return data
        except Exception as e:
            logger.error(f"데이터 추출 오류: {str(e)}")
            # 오류 발생 시 기본 데이터 반환
            return {
                "chart_type": chart_type.value if chart_type else "pie",
                "title": "데이터 추출 오류",
                "data": {
                    "labels": ["오류 발생"],
                    "values": [100]
                }
            } 