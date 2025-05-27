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
            description="RAG 파이프라인을 사용하여 사용자 질의에 대해 스트리밍 방식으로 답변합니다. 사용자는 질의 내용과 함께 검색 대상 문서(회의록 전용, 특정 문서 ID), 세션 ID, 회의 맥락 정보 등을 제공할 수 있습니다.",
            response_description="Server-Sent Events (SSE) 스트림. LLMResponseChunk 스키마를 따르며, 다양한 MessageType (예: content, retrieved_document, llm_reasoning_step, error 등)으로 구성된 JSON 객체들이 스트리밍됩니다.")
async def stream_rag_chat(request_data: ChatRequest = Body(..., examples={
    "simple_rag_query": {
        "summary": "간단한 RAG 질의 (회의록 대상)",
        "description": "가장 기본적인 RAG 질의 예시입니다. '지난 주 회의록 요약해줘'라는 질의를 회의 문서 내에서만 검색합니다.",
        "value": {
            "query": "지난 주 회의록 요약해줘", 
            "search_in_meeting_documents_only": True
            }
    },
    "specific_document_query_with_context": {
        "summary": "특정 문서 및 회의 맥락을 포함한 RAG 질의",
        "description": "특정 문서 ID('meeting_minutes_proj_alpha_v2')를 대상으로 검색하고, 현재 진행 중인 회의의 맥락 정보(ID, 제목, 참석자, 회의록 S3 URL)를 함께 제공하여 더욱 정확한 답변을 유도합니다.",
        "value": {
            "query": "프로젝트 알파의 다음 마일스톤은 무엇인가요?",
            "session_id": "user123_session_abc789",
            "search_in_meeting_documents_only": False, 
            "target_document_ids": ["meeting_minutes_proj_alpha_v2"],
            "meeting_context": {
                "hub_meeting_id": "hub_meeting_xyz789",
                "hub_meeting_title": "프로젝트 알파 주간 동기화 회의",
                "hub_participant_names": ["김팀장", "이개발", "박기획"],
                "hub_minutes_s3_url": "s3://my-company-bucket/minutes/project_alpha_weekly_sync.pdf"
            }
        }
    },
    "general_knowledge_query": {
        "summary": "일반 지식 질의 (전체 문서 대상)",
        "description": "특정 문서나 회의록에 국한되지 않는 일반적인 질의입니다. '우리 회사 복지 정책에 대해 알려줘'와 같이 전체 문서를 대상으로 검색합니다.",
        "value": {
            "query": "우리 회사 복지 정책에 대해 알려줘",
            "search_in_meeting_documents_only": False
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
