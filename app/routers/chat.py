from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from app.schemas.chat import ChatRequest, LLMResponseChunk, MessageType, LLMReasoningStep, RetrievedDocument
from app.services.workflow_service import workflow_manager 
from app.core.config import settings
import json
import logging
import time

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

@router.post("/rag/stream", 
            summary="RAG 스트리밍 채팅 Q&A",
            description="RAG 파이프라인을 사용하여 사용자 질의에 대해 스트리밍 방식으로 답변합니다.",
            response_description="Server-Sent Events (SSE) 스트림. LLMResponseChunk 스키마를 따릅니다.")
async def stream_rag_chat(request_data: ChatRequest = Body(..., examples={
    "rag_query": {
        "summary": "RAG 질의",
        "value": {
            "query": "지난 주 회의록 요약해줘", 
            "search_in_meeting_documents_only": True
            }
    }
})):
    async def event_generator():
        session_id = request_data.session_id or "default_session"
        try:
            async for chunk_str in workflow_manager.process_chat_request_stream(request_data, session_id):
                # workflow_service가 이미 SSE 형식의 문자열을 반환한다고 가정
                yield chunk_str
        except Exception as e:
            logger.error(f"Error in RAG streaming: {str(e)}", exc_info=True)
            # 오류 발생 시에도 SSE 형식으로 오류 메시지 전송
            error_response_chunk = LLMResponseChunk(
                session_id=session_id,
                type=MessageType.ERROR,
                data={"error_message": f"스트리밍 중 내부 서버 오류 발생: {str(e)}", "details": traceback.format_exc() if settings.DEBUG else str(e)}
            )
            yield f"data: {error_response_chunk.model_dump_json(exclude_none=True)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
