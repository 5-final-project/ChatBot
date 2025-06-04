"""
Base schema module for common schema definitions
"""
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field

class BaseSchema(BaseModel):
    """
    Base schema class that all schema classes should inherit from
    Provides common functionality and configuration
    """
    
    class Config:
        """Pydantic config"""
        arbitrary_types_allowed = True
        json_encoders = {
            # Custom JSON encoders can be defined here
        }

class UserRequestBase(BaseSchema):
    """
    기본 사용자 요청 모델입니다.
    모든 사용자 요청 클래스가 상속받는 기본 클래스입니다.
    """
    query: str = Field(
        ..., 
        description="사용자 질의 (필수)",
        example="지난 주 회의에서 결정된 내용을 알려줘",
        min_length=1
    )
    session_id: Optional[str] = Field(
        None, 
        description="세션 ID (선택사항, 대화 맥락 유지에 사용)",
        example="sess_abc123"
    )
    document_ids: Optional[List[str]] = Field(
        None, 
        description="특정 문서 ID 리스트 (지정된 문서에서만 검색)",
        example=["doc_123", "doc_456"]
    ) 