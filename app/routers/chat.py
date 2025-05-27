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
        session_id = request_data.session_id or f"sess_{int(time.time())}" 
        try:
            async for chunk_obj in workflow_manager.process_chat_request_stream(request_data, session_id): 
                if isinstance(chunk_obj, LLMResponseChunk):
                    sse_event = f"data: {chunk_obj.model_dump_json(exclude_none=True)}\n\n"
                    yield sse_event
                else:
                    logger.warning(f"Unexpected chunk type from workflow: {type(chunk_obj)}. Attempting to serialize as string.")
                    try:
                        unknown_data = {"type": "unknown", "content": str(chunk_obj)}
                        sse_event = f"data: {json.dumps(unknown_data)}\n\n"
                        yield sse_event
                    except Exception as serialization_error:
                        logger.error(f"Could not serialize unknown chunk: {serialization_error}")
                        error_response_chunk = LLMResponseChunk(
                            session_id=session_id,
                            type=MessageType.ERROR,
                            data={"error": f"스트리밍 중 예기치 않은 데이터 타입 직렬화 오류: {serialization_error}"}
                        )
                        yield f"data: {error_response_chunk.model_dump_json(exclude_none=True)}\n\n"

        except Exception as e:
            logger.error(f"Error in RAG streaming (session: {session_id}): {str(e)}", exc_info=True)
            error_response_chunk = LLMResponseChunk(
                session_id=session_id,
                type=MessageType.ERROR,
                data={"error": f"스트리밍 중 내부 서버 오류 발생: {str(e)}"}
            )
            yield f"data: {error_response_chunk.model_dump_json(exclude_none=True)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
