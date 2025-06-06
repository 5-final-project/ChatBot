from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from app.schemas.chat import ChatRequest, LLMResponseChunk, MessageType, LLMReasoningStep, RetrievedDocument
from app.services.workflow.workflow_manager import workflow_manager 
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
        "description": "특정 문서 ID('meeting_minutes_proj_alpha_v2')를 대상으로 검색하고, 현재 진행 중인 회의의 맥락 정보(제목, 참석자, 회의록 S3 URL)를 함께 제공하여 더욱 정확한 답변을 유도합니다.",
        "value": {
            "query": "프로젝트 알파의 다음 마일스톤은 무엇인가요?",
            "session_id": "user123_session_abc789",
            "search_in_meeting_documents_only": False, 
            "target_document_ids": ["meeting_minutes_proj_alpha_v2"],
            "meeting_context": {
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
    # 시각화 요청 감지 (3가지 특정 질문)
    query_lower = request_data.query.lower().strip()
    is_visualization_request = False
    
    # 1. 미갱신 고객 비율을 차트로 보여줘
    if query_lower == "미갱신 고객 비율을 차트로 보여줘" or (
        "미갱신" in query_lower and "고객" in query_lower and "비율" in query_lower and 
        ("차트" in query_lower or "그래프" in query_lower) and 
        ("보여" in query_lower or "그려" in query_lower)
    ):
        is_visualization_request = True
    
    # 2. STR 지연 건에 대한 그래프를 생성해줘
    elif query_lower == "str 지연 건에 대한 그래프를 생성해줘" or (
        "str" in query_lower and "지연" in query_lower and 
        ("그래프" in query_lower or "차트" in query_lower) and 
        ("생성" in query_lower or "만들어" in query_lower or "보여" in query_lower)
    ):
        is_visualization_request = True
    
    # 3. 규제 준수 일정을 타임라인으로 보여줘
    elif query_lower == "규제 준수 일정을 타임라인으로 보여줘" or (
        "규제" in query_lower and "준수" in query_lower and "일정" in query_lower and 
        ("타임라인" in query_lower or "시간표" in query_lower) and 
        ("보여" in query_lower or "그려" in query_lower)
    ):
        is_visualization_request = True
    
    # 시각화 요청인 경우 process_rag_stream 호출
    if is_visualization_request:
        session_id = request_data.session_id or f"sess_{int(time.time())}"
        logger.info(f"시각화 요청 감지됨: '{request_data.query}', 처리 방식: process_rag_stream")
        
        # 검색된 문서 목록 가져오기 (빈 딕셔너리 리스트로 초기화)
        retrieved_documents = [{"content_chunk": ""}]  # 적어도 빈 content_chunk를 포함한 딕셔너리
        
        # 커스텀 이벤트 생성기
        async def custom_event_generator():
            try:
                async for chunk in workflow_manager.process_rag_stream(
                    query=request_data.query,
                    retrieved_documents=retrieved_documents,
                    session_id=session_id
                ):
                    # JSON 직렬화
                    json_data = json.dumps(chunk, ensure_ascii=False)
                    # 표준 SSE 형식으로 변환 ('type' 대신 'event' 필드 사용)
                    yield f"data: {json_data}\n\n"
            except Exception as e:
                logger.error(f"SSE 스트리밍 오류: {str(e)}")
                error_data = json.dumps({"type": "error", "data": {"message": str(e)}}, ensure_ascii=False)
                yield f"data: {error_data}\n\n"
        
        # StreamingResponse 사용 (sse_starlette 대신)
        return StreamingResponse(
            custom_event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    # 일반 요청인 경우 기존 로직 사용
    async def event_generator():
        # LLM 추론 및 답변 관련 타입만 필터링하기 위한 집합
        allowed_types = {
            MessageType.LLM_REASONING_STEP.value,
            MessageType.CONTENT.value,
            MessageType.ERROR.value, # 오류 상황 전파
            MessageType.END.value, # 스트림 종료 전파
            MessageType.WARNING.value, # 경고 메시지
            MessageType.TASK_COMPLETE.value, # 작업 완료
            MessageType.RESULT.value, # 결과 메시지
            MessageType.VISUALIZATION.value, # 시각화 결과
            MessageType.THINKING.value, # 처리 중 상태
            MessageType.RETRIEVED_DOCUMENTS.value # 검색된 문서 정보
        }
        
        # 의도 분류 및 엔티티 추출 관련 메시지 필터링을 위한 불필요한 step_description 목록
        filtered_reasoning_steps = {
            "Intent classification and entity extraction prompt prepared",
            "LLM raw response for intent/entity",
            "LLM response parsed successfully"
        }
        
        # 마지막 end 이벤트만 전송하기 위한 플래그
        sent_end_event = False
        
        # 콘텐츠 축적을 위한 변수
        accumulated_content = ""
        last_content_time = time.time()
        CONTENT_CHUNK_SIZE = 30  # 적절한 크기로 조정 (문자 수, 공백 포함)
        CONTENT_MAX_DELAY = 0.3  # 최대 지연 시간 (초)
        
        # 응답 내용 존재 여부 추적
        received_any_content = False
        
        try:
            # 세션 ID가 없는 경우 기본값 설정
            session_id = request_data.session_id or f"sess_{int(time.time())}"
            logger.info(f"스트리밍 채팅 시작: session_id={session_id}, query='{request_data.query[:30]}...'")
            
            # process_chat_request_stream 메서드 호출 - 이미 포맷된 SSE 문자열을 반환함
            async for sse_chunk in workflow_manager.process_chat_request_stream(request_data, session_id):
                # ping 메시지 제거
                if not sse_chunk.startswith('data: '):
                    logger.debug(f"ping 메시지 스킵: {sse_chunk[:20]}...")
                    continue
                    
                # SSE 형식에서 데이터 부분만 추출
                json_str = sse_chunk[6:]  # 'data: ' 부분 제거
                try:
                    chunk_data = json.loads(json_str)
                    current_type = chunk_data.get('type')
                    
                    # 디버그 로깅
                    if current_type == MessageType.CONTENT.value:
                        content_preview = chunk_data.get('content', '')[:20]
                        logger.debug(f"CONTENT 청크 수신: '{content_preview}...'")
                        received_any_content = True
                    elif current_type == MessageType.LLM_REASONING_STEP.value:
                        logger.debug(f"LLM_REASONING_STEP 청크 수신")
                        received_any_content = True
                    else:
                        logger.debug(f"기타 청크 수신: type={current_type}")
                    
                    # END 이벤트 처리 - llm_streaming_service.py에서 보내는 이벤트 전달
                    if current_type == MessageType.END.value:
                        # 이미 END 이벤트를 보냈다면 중복 전송하지 않음
                        if sent_end_event:
                            logger.debug("중복 END 이벤트 스킵")
                            continue
                        
                        event_data = {
                            'type': current_type,
                            'data': chunk_data.get('data', {})
                        }
                        json_data = json.dumps(
                            event_data, 
                            ensure_ascii=False,
                            separators=(',', ':')
                        )
                        yield f"data: {json_data}\n\n"
                        sent_end_event = True
                        continue
                    
                    # LLM 추론 과정 메시지 필터링 (의도 분류 관련 불필요한 추론 단계 제거)
                    if (current_type == MessageType.LLM_REASONING_STEP.value and 
                        'step_description' in chunk_data.get('data', {}) and
                        chunk_data['data']['step_description'] in filtered_reasoning_steps):
                        continue
                    
                    # 사고 과정(THINKING) 타입 특별 처리
                    elif current_type == MessageType.THINKING.value:
                        logger.debug(f"사고 과정 데이터 수신")
                        # 한국어 thinking은 무시하고 영어 thinking만 처리
                        if isinstance(chunk_data.get('data', {}), dict) and "full_thinking" in chunk_data.get('data', {}):
                            # 영어 thinking에 <think> 태그 추가
                            thinking_text = f"<think>{chunk_data['data']['full_thinking']}\n\n\n</think>"
                            event_data = {
                                'type': MessageType.CONTENT.value,  # THINKING이 아닌 CONTENT 타입으로 전송
                                'data': {},
                                'content': thinking_text
                            }
                            
                            # 원본 데이터가 그대로 전달되도록 ensure_ascii=False 및 separators 옵션 설정
                            json_data = json.dumps(
                                event_data, 
                                ensure_ascii=False,
                                separators=(',', ':')
                            )
                            
                            # 즉시 yield - 원본 SSE 형식으로 전송
                            yield f"data: {json_data}\n\n"
                            continue
                        elif 'content' in chunk_data and isinstance(chunk_data['content'], str):
                            # 한국어 thinking 메시지는 무시 (출력하지 않음)
                            continue
                    
                    # 검색된 문서(RETRIEVED_DOCUMENTS) 타입은 무시
                    elif current_type == MessageType.RETRIEVED_DOCUMENTS.value:
                        # 검색된 문서는 표시하지 않고 건너뜀
                        continue
                    
                    # 일반 콘텐츠 처리 (CONTENT 타입)
                    elif current_type == MessageType.CONTENT.value:
                        content = chunk_data.get('content', '')
                        if not content:
                            content = chunk_data.get('data', {}).get('content', '')
                            if not content:
                                content = chunk_data.get('data', {}).get('text', '')
                        
                        # 내용이 없는 경우 스킵
                        if not content:
                            logger.debug("빈 콘텐츠 스킵")
                            continue
                        
                        # 추론 과정과 답변이 함께 들어있는 마지막 중복 출력 필터링
                        if content and (
                            # 추론 과정 시작/종료 태그가 모두 포함된 경우 (전체 요약 응답)
                            ("<think>" in content and "</think>" in content) or
                            # 또는 추론 과정과 최종 답변이 모두 포함된 매우 긴 텍스트인 경우
                            (len(content) > 1000 and "</think>" in content)
                        ):
                            logger.debug("추론과 답변이 함께 있는 중복 출력 필터링")
                            continue
                        
                        # 한 글자씩 스트리밍하도록 변경 - 축적하지 않고 즉시 전송
                        event_data = {
                            'type': current_type,
                            'data': {},
                            'content': content
                        }
                        
                        # 원본 데이터가 그대로 전달되도록 ensure_ascii=False 및 separators 옵션 설정
                        json_data = json.dumps(
                            event_data, 
                            ensure_ascii=False,
                            separators=(',', ':')
                        )
                        
                        # 즉시 yield - 원본 SSE 형식으로 전송
                        yield f"data: {json_data}\n\n"
                    
                    # LLM 추론 과정 메시지는 그대로 전달 (LLM_REASONING_STEP 타입)
                    elif current_type == MessageType.LLM_REASONING_STEP.value:
                        # 추론 과정은 그대로 전달 (타임스탬프 제거)
                        event_data = {
                            'type': current_type,
                            'data': {
                                'step_description': chunk_data.get('data', {}).get('step_description', ''),
                                'details': chunk_data.get('data', {}).get('details', {})
                            }
                        }
                        
                        # content 필드가 있으면 event_data에 포함
                        if 'content' in chunk_data and chunk_data['content']:
                            if chunk_data['content'].strip():
                                event_data['content'] = chunk_data['content']
                        
                        # 원본 데이터가 그대로 전달되도록 ensure_ascii=False 및 separators 옵션 설정
                        json_data = json.dumps(
                            event_data, 
                            ensure_ascii=False,
                            separators=(',', ':')
                        )
                        
                        # 즉시 yield - 원본 SSE 형식으로 전송
                        yield f"data: {json_data}\n\n"
                    
                    # 에러 메시지 등 다른 타입은 타임스탬프 없이 전달
                    elif current_type in allowed_types:
                        event_data = {
                            'type': current_type,
                            'data': chunk_data.get('data', {})
                        }
                        
                        # 타임스탬프 제거
                        if 'timestamp' in event_data['data']:
                            del event_data['data']['timestamp']
                        
                        # content 필드가 있으면 event_data에 포함
                        if 'content' in chunk_data and chunk_data['content']:
                            if chunk_data['content'].strip():
                                event_data['content'] = chunk_data['content']
                        
                        # 시각화 타입 특별 처리
                        if current_type == MessageType.VISUALIZATION.value:
                            # 시각화 데이터를 그대로 전달
                            logger.debug(f"시각화 데이터 수신 (크기: {len(str(chunk_data.get('data', {})))}바이트)")
                            # 시각화 데이터의 모든 필드 유지
                            event_data = chunk_data
                        
                        # 원본 데이터가 그대로 전달되도록 ensure_ascii=False 및 separators 옵션 설정
                        json_data = json.dumps(
                            event_data, 
                            ensure_ascii=False,
                            separators=(',', ':')
                        )
                        
                        # 즉시 yield - 원본 SSE 형식으로 전송
                        yield f"data: {json_data}\n\n"
                        
                except json.JSONDecodeError as e:
                    logger.error(f"JSON 파싱 오류: {e}, 원본 데이터: {json_str}")
                
            # 응답 체크
            if not received_any_content:
                logger.warning(f"세션 {session_id}에서 콘텐츠 응답이 생성되지 않았습니다.")
                default_message = "죄송합니다. 현재 응답을 생성할 수 없습니다. 다시 질문해 주세요."
                event_data = {
                    'type': MessageType.CONTENT.value,
                    'data': {},
                    'content': default_message
                }
                json_data = json.dumps(
                    event_data, 
                    ensure_ascii=False,
                    separators=(',', ':')
                )
                yield f"data: {json_data}\n\n"
                
        except Exception as e:
            logger.error(f"Error during chat streaming: {e}", exc_info=True)
            error_event = {
                'type': MessageType.ERROR.value,
                'data': {'message': str(e), 'is_final': True}
            }
            
            # 원본 데이터가 그대로 전달되도록 ensure_ascii=False 및 separators 옵션 설정
            json_data = json.dumps(
                error_event, 
                ensure_ascii=False,
                separators=(',', ':')
            )
            
            yield f"data: {json_data}\n\n"
        finally:
            # 남아있는 콘텐츠가 있으면 전송
            if accumulated_content:
                event_data = {
                    'type': MessageType.CONTENT.value,
                    'data': {},
                    'content': accumulated_content
                }
                
                # 원본 데이터가 그대로 전달되도록 ensure_ascii=False 및 separators 옵션 설정
                json_data = json.dumps(
                    event_data, 
                    ensure_ascii=False,
                    separators=(',', ':')
                )
                
                yield f"data: {json_data}\n\n"
            
            # 단 한 번의 end 이벤트만 전송
            if not sent_end_event:
                end_event = {
                    'type': MessageType.END.value,
                    'data': {'message': 'Stream ended', 'is_final': True}
                }
                
                # 원본 데이터가 그대로 전달되도록 ensure_ascii=False 및 separators 옵션 설정
                json_data = json.dumps(
                    end_event, 
                    ensure_ascii=False,
                    separators=(',', ':')
                )
                
                yield f"data: {json_data}\n\n"
                sent_end_event = True
                logger.info(f"스트리밍 응답 종료: session_id={session_id}")
    
    # sse_starlette 대신 직접 StreamingResponse 사용
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
