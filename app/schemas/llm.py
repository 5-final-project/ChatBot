"""
LLM related schemas for the application
"""
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum
from app.schemas.base import BaseSchema

class MessageType(str, Enum):
    """Message type enumeration for different response chunks"""
    START = "start"
    THINKING = "thinking"
    CONTENT = "content"
    ERROR = "error"
    TASK_COMPLETE = "task_complete"
    END = "end"
    INTENT_CLASSIFIED = "intent_classified"
    LLM_REASONING_STEP = "llm_reasoning_step"
    RETRIEVED_DOCUMENT = "retrieved_document"
    VISUALIZATION = "visualization"

class RetrievedDocument(BaseModel):
    """Schema for a retrieved document from the search"""
    document_id: Optional[str] = Field(None, description="Document ID")
    content_chunk: str = Field(..., description="Content chunk of the document")
    score: float = Field(..., description="Relevance score of the document")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Document metadata")

class LLMResponse(BaseSchema):
    """Schema for LLM response"""
    response_text: str = Field(..., description="Response text from LLM")
    reasoning_steps: Optional[List[str]] = Field(None, description="Reasoning steps")
    intent: Optional[str] = Field(None, description="Detected intent")
    entities: Optional[Dict[str, Any]] = Field(None, description="Extracted entities")
    confidence: Optional[float] = Field(None, description="Confidence score")

class LLMResponseChunk(BaseModel):
    """Schema for LLM response chunk"""
    session_id: str = Field(..., description="Session ID")
    type: MessageType = Field(..., description="Message type")
    content: Optional[str] = Field(None, description="Text content")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data") 