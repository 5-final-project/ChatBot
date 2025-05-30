"""
워크플로우 관리자 서비스
워크플로우 관련 모든 서비스를 통합 관리하는 클래스를 제공합니다.
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional, AsyncGenerator
from app.schemas.chat import ChatRequest, LLMResponseChunk, MessageType
from app.services.workflow.workflow_core import WorkflowCore
from app.services.workflow.qna_workflow_service import QnAWorkflowService
from app.services.workflow.mattermost_workflow_service import MattermostWorkflowService
from app.services.workflow.session_service import SessionService

logger = logging.getLogger(__name__)

class WorkflowManager:
    """워크플로우 관련 모든 서비스를 통합 관리하는 클래스"""
    
    _instance = None
    
    def __new__(cls):
        """싱글톤 패턴 구현"""
        if cls._instance is None:
            cls._instance = super(WorkflowManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """워크플로우 관리자를 초기화합니다."""
        if self._initialized:
            return
        
        logger.info("WorkflowManager 초기화 중...")
        self.core = WorkflowCore()
        self.qna_service = QnAWorkflowService(self.core)
        self.mattermost_service = MattermostWorkflowService(self.core)
        self.session_service = SessionService()
        self._initialized = True
        logger.info("WorkflowManager 초기화 완료")

    async def async_initialize_db(self):
        """데이터베이스 연결을 비동기적으로 초기화합니다."""
        from app.services.db.db_core import connect_db, get_db_pool 
        
        logger.info("데이터베이스 연결 초기화 시도...")
        initialized_pool = await connect_db()
        
        if initialized_pool:
            logger.info(f"데이터베이스 연결 풀이 성공적으로 초기화/확인되었습니다. Pool: {initialized_pool}")
            current_global_pool = await get_db_pool()
            logger.info(f"현재 전역 db_core.pool 상태 (get_db_pool 통해 확인): {current_global_pool}")
        else:
            logger.error("데이터베이스 연결 풀 초기화/확인 실패. connect_db()가 None을 반환했습니다.")
        return initialized_pool is not None
    
    async def process_chat_request_stream(
        self, 
        request: ChatRequest, 
        session_id: str
    ) -> AsyncGenerator[str, None]:
        """
        채팅 요청을 처리하고 SSE 형식의 응답을 스트리밍합니다.
        
        Args:
            request (ChatRequest): 채팅 요청 객체
            session_id (str): 세션 ID
            
        Yields:
            str: SSE 형식의 응답 청크
        """
        logger.info(f"[{session_id}] 스트리밍 채팅 요청 시작: {request.query}")
        
        # SSE 시작 메시지
        yield self.core._format_sse_chunk(
            session_id=session_id, 
            type=MessageType.START, 
            data={"session_id": session_id}
        )
        
        # 회의 컨텍스트 관리
        if request.meeting_context:
            self.session_service.set_meeting_context(session_id, request.meeting_context)
        
        # 사용자 메시지 대화 기록에 추가
        self.session_service.add_user_message(session_id, request.query)
        
        # 회의록 전송 요청 키워드 빠른 감지 (스트리밍 응답 개선)
        is_send_minutes_request = False
        if "회의" in request.query and "참여" in request.query and "사람" in request.query and ("회의록" in request.query or "문서" in request.query) and ("보내" in request.query or "전송" in request.query or "공유" in request.query):
            is_send_minutes_request = True
            
        # 회의록 전송 요청이 명확한 경우 즉시 스트리밍 시작
        if is_send_minutes_request and request.meeting_context and (
            request.meeting_context.hub_participant_names or 
            request.meeting_context.hub_meeting_title
        ):
            # 빠른 응답을 위한 초기 스트리밍 메시지
            yield self.core._format_sse_chunk(
                session_id=session_id,
                type=MessageType.CONTENT,
                content="회의록 전송 요청을 처리 중입니다..."
            )
        
        # 사용자 의도 파악
        try:
            intent_result = await self.core.llm_service.classify_intent(request.query)
            intent = intent_result.get("intent", "unknown")
            entities = intent_result.get("entities", {})
            
            # 의도 분류 결과 전송
            yield self.core._format_sse_chunk(
                session_id=session_id,
                type=MessageType.INTENT_CLASSIFIED,
                data={
                    "intent": intent, 
                    "entities": entities, 
                    "description": f"사용자 의도를 '{intent}'로 파악했습니다."
                }
            )
            
            # 의도 분류의 추론 과정 전송 (일반 사용자에게는 불필요하므로 생략 가능)
            # 회의록 전송 요청인 경우 추론 과정 스킵하여 응답 속도 개선
            if "reasoning_steps" in intent_result and intent_result["reasoning_steps"] and not is_send_minutes_request:
                for step in intent_result["reasoning_steps"]:
                    yield self.core._format_sse_chunk(
                        session_id=session_id,
                        type=MessageType.LLM_REASONING_STEP,
                        data=step
                    )
            
            # 의도에 따라 적절한 서비스로 라우팅
            if intent == "qna":
                # Q&A 처리
                async for chunk in self.qna_service.process_qna_request(
                    request=request,
                    session_id=session_id,
                    intent_result=intent_result
                ):
                    yield self.core._format_sse_chunk(
                        session_id=session_id,
                        type=chunk.type,
                        content=chunk.content,
                        data=chunk.data
                    )
                    
            elif intent == "send_mattermost_minutes":
                # 회의록 전송 처리 - 모든 응답을 스트리밍 형태로 표시
                async for chunk in self.mattermost_service.process_mattermost_minutes_request(
                    request=request,
                    session_id=session_id,
                    intent_result=intent_result
                ):
                    # 스트리밍 형태로 모든 타입의 응답 전달
                    yield self.core._format_sse_chunk(
                        session_id=session_id,
                        type=chunk.type,
                        content=chunk.content,
                        data=chunk.data
                    )
                    
            elif intent == "unsupported":
                # 지원하지 않는 의도
                logger.info(f"[{session_id}] 지원하지 않는 intent 요청: {request.query}")
                yield self.core._format_sse_chunk(
                    session_id=session_id,
                    type=MessageType.ERROR,
                    data={
                        "error_message": "지원하지 않는 요청입니다.", 
                        "details": "현재 시스템이 지원하지 않는 기능입니다."
                    }
                )
                
            else:
                # 알 수 없는 의도 - 기본 Q&A로 처리
                logger.warning(f"[{session_id}] 알 수 없는 intent: {intent}, Q&A로 처리")
                async for chunk in self.qna_service.process_qna_request(
                    request=request,
                    session_id=session_id,
                    intent_result=intent_result
                ):
                    yield self.core._format_sse_chunk(
                        session_id=session_id,
                        type=chunk.type,
                        content=chunk.content,
                        data=chunk.data
                    )
                
        except Exception as e:
            logger.error(f"[{session_id}] 채팅 처리 오류: {str(e)}")
            yield self.core._format_sse_chunk(
                session_id=session_id,
                type=MessageType.ERROR,
                data={
                    "error_message": "요청 처리 중 오류가 발생했습니다.", 
                    "details": str(e)
                }
            )
        
        # SSE 종료 메시지
        yield self.core._format_sse_chunk(
            session_id=session_id,
            type=MessageType.END,
            data={"message": "스트리밍 응답 종료"}
        )
    
    async def initialize_db(self):
        """DB 초기화 및 테스트 데이터 추가"""
        return await self.core.async_initialize_db() if hasattr(self.core, 'async_initialize_db') else False
        
    async def async_initialize_db(self):
        """DB 초기화 및 테스트 데이터 추가 (main.py 호환용)"""
        # 기존의 initialize_db 메서드를 호출합니다
        return await self.initialize_db()


# WorkflowManager의 싱글톤 인스턴스 생성
workflow_manager = WorkflowManager()
