from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from enum import Enum

from app.schemas.base import BaseSchema
from app.schemas.llm import RetrievedDocument

class ChartType(str, Enum):
    """
    시각화 차트 유형을 정의합니다.
    """
    LINE = "line"            # 선 그래프
    BAR = "bar"              # 막대 그래프
    PIE = "pie"              # 파이 차트
    SCATTER = "scatter"      # 산점도
    TIMELINE = "timeline"    # 타임라인
    HEATMAP = "heatmap"
    RADAR = "radar"
    SUNBURST = "sunburst"

class MeetingDataPoint(BaseModel):
    """
    회의에서 추출된 데이터 포인트를 정의합니다.
    """
    label: str = Field(..., description="데이터 포인트의 레이블(이름)")
    value: Union[int, float] = Field(..., description="데이터 포인트의 값")
    timestamp: Optional[str] = Field(None, description="데이터 포인트의 시간 정보(선택사항)")
    category: Optional[str] = Field(None, description="데이터 포인트의 카테고리(선택사항)")
    color: Optional[str] = Field(None, description="색상 (자동 할당되지만 명시적으로 지정 가능)")
    additional_info: Optional[Dict[str, Any]] = Field(None, description="추가 정보")

class VisualizationRequest(BaseSchema):
    """
    시각화 요청 모델입니다.
    """
    query: str = Field(..., description="시각화할 데이터를 추출하기 위한 사용자 쿼리",
                       example="지난 분기 회의에서 언급된 프로젝트별 예산 배분을 그래프로 보여줘")
    chart_type: Optional[ChartType] = Field(None, description="원하는 차트 유형(지정하지 않으면 자동 선택)",
                                         example="pie")
    session_id: Optional[str] = Field(None, description="세션 ID(대화 맥락 유지에 사용)")
    top_k: int = Field(5, description="검색할 문서 수")
    target_document_ids: Optional[List[str]] = Field(None, description="특정 문서 ID 리스트(지정된 문서에서만 검색)")
    meeting_context: Optional[Dict[str, Any]] = Field(None, description="현재 회의 관련 컨텍스트 정보")
    is_financial_compliance_scenario: bool = Field(False, description="금융 규제 준수 시나리오 여부")

class VisualizationResponse(BaseSchema):
    """
    시각화 응답 모델입니다.
    """
    query: str = Field(..., description="원본 쿼리")
    chart_type: ChartType = Field(..., description="생성된 차트 유형")
    chart_title: str = Field(..., description="차트 제목")
    chart_image: str = Field(..., description="차트 이미지 (URL 또는 Base64 인코딩)")
    chart_data: Dict[str, Any] = Field(..., description="차트 데이터")
    explanation: str = Field(..., description="시각화 설명")
    thinking: str = Field(..., description="시각화 생성 사고 과정")
    retrieved_documents: List[RetrievedDocument] = Field([], description="검색된 문서 목록")
    is_financial_compliance_scenario: bool = Field(False, description="금융 규제 준수 시나리오 여부")

class VisualizationImageResponse(BaseModel):
    """
    이미지 형식의 시각화 응답 모델입니다.
    """
    chart_type: ChartType = Field(..., description="생성된 차트 유형")
    title: str = Field(..., description="차트 제목")
    image_path: str = Field(..., description="생성된 이미지 파일 경로")
    summary: Optional[str] = Field(None, description="시각화 데이터에 대한 요약 설명") 