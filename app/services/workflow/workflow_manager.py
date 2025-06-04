"""
워크플로우 관리자 서비스
워크플로우 관련 모든 서비스를 통합 관리하는 클래스를 제공합니다.
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional, AsyncGenerator
from app.schemas.chat import ChatRequest, LLMResponseChunk, MessageType, RetrievedDocument
from app.schemas.visualization import VisualizationRequest
from app.schemas.base import UserRequestBase
from app.services.workflow.workflow_core import WorkflowCore
from app.services.workflow.qna_workflow_service import QnAWorkflowService
from app.services.workflow.mattermost_workflow_service import MattermostWorkflowService
from app.services.workflow.session_service import SessionService
from app.services.visualization.visualization_workflow_service import VisualizationWorkflowService
import re
import time
import random

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
        
        # 시각화 관련 서비스 초기화
        from app.services.visualization.visualization_service import VisualizationService
        from app.services.thinking.thinking_service import ThinkingService
        from app.services.retrieval.rag_service import RAGService
        
        self.visualization_service_instance = VisualizationService()
        self.thinking_service_instance = ThinkingService()
        self.rag_service_instance = RAGService()
        
        self.visualization_service = VisualizationWorkflowService(
            self.rag_service_instance,
            self.visualization_service_instance,
            self.thinking_service_instance
        )
        
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
                    
            elif intent == "visualize_data":
                # 시각화 처리 - 회의 내용 시각화 요청
                logger.info(f"[{session_id}] 시각화 요청 처리: {request.query}")
                
                # ChatRequest를 VisualizationRequest로 변환
                visualization_request = VisualizationRequest(
                    query=request.query,
                    session_id=session_id,
                    target_document_ids=request.target_document_ids,
                    meeting_context=request.meeting_context.dict() if request.meeting_context else None
                )
                
                # 시각화 워크플로우 처리 - 스트리밍 방식으로 수정
                async for chunk in self.visualization_service.process_visualization_request(
                    request=visualization_request,
                    session_id=session_id
                ):
                    # LLMResponseChunk를 SSE 형식으로 변환
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
    
    async def process_visualization_request_stream(
        self, 
        request: VisualizationRequest, 
        session_id: str
    ) -> AsyncGenerator[str, None]:
        """
        시각화 요청을 처리하고 SSE 형식의 응답을 스트리밍합니다.
        
        Args:
            request (VisualizationRequest): 시각화 요청 객체
            session_id (str): 세션 ID
            
        Yields:
            str: SSE 형식의 응답 청크
        """
        logger.info(f"[{session_id}] 시각화 요청 처리 시작: {request.query}")
        
        # SSE 시작 메시지
        yield self.core._format_sse_chunk(
            session_id=session_id, 
            type=MessageType.START, 
            data={"session_id": session_id}
        )
        
        # 사용자 메시지 대화 기록에 추가
        self.session_service.add_user_message(session_id, request.query)
        
        try:
            # 시각화 워크플로우 처리
            async for chunk in self.visualization_service.process_visualization_request(
                request=request,
                session_id=session_id
            ):
                yield self.core._format_sse_chunk(
                    session_id=session_id,
                    type=chunk.type,
                    content=chunk.content,
                    data=chunk.data
                )
                
        except Exception as e:
            logger.error(f"[{session_id}] 시각화 처리 오류: {str(e)}")
            yield self.core._format_sse_chunk(
                session_id=session_id,
                type=MessageType.ERROR,
                data={
                    "error_message": "시각화 요청 처리 중 오류가 발생했습니다.", 
                    "details": str(e)
                }
            )
        
        # SSE 종료 메시지
        yield self.core._format_sse_chunk(
            session_id=session_id,
            type=MessageType.END,
            data={"message": "시각화 스트리밍 응답 종료"}
        )
    
    async def initialize_db(self):
        """DB 초기화 및 테스트 데이터 추가"""
        return await self.core.async_initialize_db() if hasattr(self.core, 'async_initialize_db') else False
        
    async def async_initialize_db(self):
        """DB 초기화 및 테스트 데이터 추가 (main.py 호환용)"""
        # 기존의 initialize_db 메서드를 호출합니다
        return await self.initialize_db()

    async def _classify_user_intent(self, query: str, context: Dict[str, Any] = None) -> str:
        """
        사용자 의도를 분류합니다.
        
        Args:
            query (str): 사용자 쿼리
            context (Dict[str, Any], optional): 컨텍스트 정보
            
        Returns:
            str: 분류된 의도 (workflow_type)
        """
        # 간단한 규칙 기반 의도 분류 (실제로는 LLM 기반 분류기를 사용할 수 있음)
        query_lower = query.lower()
        
        # 테스트 시나리오: 금융 규제 준수 관련 시각화 요청 감지
        financial_compliance_keywords = ["금감원", "kyc", "str", "의심거래", "준수", "규제", "로드맵", "일정"]
        visualization_keywords = ["그래프", "차트", "시각화", "보여줘", "그려줘", "데이터"]
        
        # 금융 규제 준수 시나리오의 시각화 요청 감지
        if any(kw in query_lower for kw in financial_compliance_keywords) and any(kw in query_lower for kw in visualization_keywords):
            logger.info(f"금융 규제 준수 관련 시각화 요청 감지: {query}")
            return "visualize_data"
        
        # 일반 시각화 요청 감지
        if any(kw in query_lower for kw in ["시각화", "그래프", "차트", "보여줘", "그려"]):
            return "visualize_data"
        
        # 기본적으로 일반 질의응답 처리
        return "query_docs"

    async def handle_user_request(
        self, 
        request: UserRequestBase, 
        session_id: str
    ) -> AsyncGenerator[LLMResponseChunk, None]:
        """
        사용자 요청을 처리하고 응답을 생성합니다.
        
        Args:
            request (UserRequestBase): 사용자 요청 객체
            session_id (str): 세션 ID
            
        Yields:
            LLMResponseChunk: 응답 청크
        """
        logger.info(f"[{session_id}] 사용자 요청 처리 시작: {request.query}")
        
        # 시스템 초기화 확인
        if not self.is_initialized:
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.ERROR,
                data={"error_message": "시스템이 초기화되지 않았습니다. 잠시 후 다시 시도해주세요."}
            )
            return
        
        try:
            # 요청 유형 분류 (실제 구현에서는 LLM 기반 분류기 사용 가능)
            workflow_type = await self._classify_user_intent(request.query)
            logger.info(f"[{session_id}] 분류된 요청 유형: {workflow_type}")
            
            # 금융 규제 준수 시나리오 감지
            financial_compliance_scenario = False
            query_lower = request.query.lower()
            if any(kw in query_lower for kw in ["금감원", "kyc", "str", "의심거래", "준수", "규제"]):
                financial_compliance_scenario = True
                logger.info(f"[{session_id}] 금융 규제 준수 시나리오 감지")
            
            # 요청 유형에 따라 적절한 워크플로우 실행
            if workflow_type == "visualize_data":
                try:
                    # 시각화 워크플로우 처리
                    visualization_request = VisualizationRequest(
                        query=request.query,
                        chart_type=None,  # 자동 결정
                        top_k=5,
                        target_document_ids=request.document_ids if hasattr(request, 'document_ids') else None
                    )
                    
                    # 시각화 처리 시작 알림
                    yield LLMResponseChunk(
                        session_id=session_id,
                        type=MessageType.THINKING,
                        data={"step_description": "데이터 시각화를 시작합니다..."}
                    )
                    
                    # 데이터 포인트 추출 - visualization_service_instance를 사용
                    # Dict 형태의 retrieved_documents를 처리하기 위해 content_chunk 접근 방식 변경
                    modified_documents = []
                    for doc in request.target_document_ids:
                        if isinstance(doc, dict):
                            # dict인 경우 RetrievedDocument 객체로 변환
                            modified_doc = RetrievedDocument(
                                source_document_id=doc.get("source_document_id", "unknown"),
                                content_chunk=doc.get("content_chunk", ""),
                                score=doc.get("score"),
                                metadata=doc.get("metadata", {})
                            )
                            modified_documents.append(modified_doc)
                        else:
                            # 이미 객체인 경우 그대로 사용
                            modified_documents.append(doc)

                    data_points, chart_type_enum, title = await self.visualization_service_instance.extract_data_from_meeting(
                        query=request.query,
                        retrieved_documents=modified_documents
                    )
                    
                    # 상세 사고과정 생성 - visualization_service_instance를 사용
                    thinking_steps = self.visualization_service_instance._generate_detailed_thinking_process(
                        query=request.query,
                        chart_type=chart_type_enum.value,
                        title=title,
                        data_points=data_points
                    )
                    
                    # 사고과정 시작 태그 전송
                    yield {
                        "type": "content",
                        "data": {},
                        "content": "<think>"
                    }
                    
                    # 각 사고과정 단계를 순차적으로 전송 (지연 시간 추가)
                    for step in thinking_steps:
                        # 각 청크 사이에 짧은 지연 시간 추가 (0.8초)
                        await asyncio.sleep(0.8)
                        
                        yield {
                            "type": "content",
                            "data": {},
                            "content": f"{step['title']}\n\n{step['content']}\n\n\n"
                        }
                    
                    # 짧은 지연 후 사고과정 종료 태그 전송
                    await asyncio.sleep(0.8)
                    yield {
                        "type": "content",
                        "data": {},
                        "content": "</think>"
                    }
                    
                    # 시각화 생성 - visualization_service_instance를 사용
                    img_base64, chart_data = await self.visualization_service_instance.create_visualization(
                        data_points=data_points,
                        chart_type=chart_type_enum,
                        title=title
                    )
                    
                    # 시각화 결과 전송
                    yield {
                        "session_id": session_id,
                        "type": "visualization",
                        "data": {
                            "chart_type": chart_type_enum.value,
                            "chart_title": title,
                            "chart_base64": img_base64,
                            "chart_data": chart_data
                        }
                    }
                    
                    # 응답 완료
                    await asyncio.sleep(0.5)
                    yield {
                        "type": "task_complete",
                        "data": {"message": "시각화 처리 완료"}
                    }
                    
                    await asyncio.sleep(0.3)
                    yield {
                        "type": "end",
                        "data": {"message": "스트리밍 응답 종료"}
                    }
                except Exception as e:
                    logger.error(f"[{session_id}] 시각화 처리 중 오류 발생: {str(e)}", exc_info=True)
                    
                    # 오류 메시지 전송
                    yield LLMResponseChunk(
                        session_id=session_id,
                        type=MessageType.ERROR,
                        data={"error_message": f"시각화 생성 중 오류가 발생했습니다: {str(e)}"}
                    )
                    
                    # 스트리밍 종료
                    yield LLMResponseChunk(
                        session_id=session_id,
                        type=MessageType.END,
                        data={"message": "오류로 인한 스트리밍 응답 종료"}
                    )
                
            else:
                # 기본 질의응답 워크플로우 처리
                # (이 부분은 기존 질의응답 로직을 유지)
                pass
                
        except Exception as e:
            logger.error(f"[{session_id}] 사용자 요청 처리 중 오류: {str(e)}", exc_info=True)
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.ERROR,
                data={"error_message": "요청 처리 중 오류가 발생했습니다.", "details": str(e)}
            )
        
        logger.info(f"[{session_id}] 사용자 요청 처리 완료")

    async def process_rag_stream(
        self,
        query: str,
        retrieved_documents: List[Dict[str, Any]],
        session_id: str,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        RAG 처리 결과를 스트림으로 반환합니다.
        
        Args:
            query (str): 사용자 쿼리
            retrieved_documents (List[Dict[str, Any]]): 검색된 문서 목록
            session_id (str): 세션 ID
            **kwargs: 추가 매개변수
            
        Yields:
            Dict[str, Any]: 스트림 응답 청크
        """
        import asyncio  # 상단 import에 추가되어야 하지만, 여기서는 지역적으로 import
        import random  # 랜덤 지연 시간을 위한 모듈 추가
        
        logger.info(f"RAG 스트림 처리 시작: session_id={session_id}, query='{query[:30]}...'")
        
        # 시각화 요청 감지
        is_visualization_request, chart_type, visualization_query = self._detect_visualization_request(query)
        
        if is_visualization_request and self.visualization_service:
            logger.info(f"시각화 요청 감지됨: chart_type={chart_type}, query='{visualization_query}'")
            
            try:
                # 데이터 포인트 추출 - visualization_service_instance를 사용
                # Dict 형태의 retrieved_documents를 처리하기 위해 content_chunk 접근 방식 변경
                modified_documents = []
                for doc in retrieved_documents:
                    if isinstance(doc, dict):
                        # dict인 경우 RetrievedDocument 객체로 변환
                        modified_doc = RetrievedDocument(
                            source_document_id=doc.get("source_document_id", "unknown"),
                            content_chunk=doc.get("content_chunk", ""),
                            score=doc.get("score"),
                            metadata=doc.get("metadata", {})
                        )
                        modified_documents.append(modified_doc)
                    else:
                        # 이미 객체인 경우 그대로 사용
                        modified_documents.append(doc)

                data_points, chart_type_enum, title = await self.visualization_service_instance.extract_data_from_meeting(
                    query=visualization_query,
                    retrieved_documents=modified_documents
                )
                
                # 상세 사고과정 생성 - visualization_service_instance를 사용
                thinking_steps = self.visualization_service_instance._generate_detailed_thinking_process(
                    query=visualization_query,
                    chart_type=chart_type_enum.value,
                    title=title,
                    data_points=data_points
                )
                
                # 사고과정 시작 태그 전송
                yield {
                    "type": "content",
                    "data": {},
                    "content": "<think>"
                }
                
                # 각 사고과정 단계를 더 작은 청크로 나누어 전송 (딜레이 2배 + 랜덤성 추가)
                for step in thinking_steps:
                    # 단계별 제목 전송
                    await asyncio.sleep(random.uniform(0.8, 1.5))  # 랜덤 딜레이
                    yield {
                        "type": "content",
                        "data": {},
                        "content": f"{step['title']}\n\n"
                    }
                    
                    # 내용을 더 작은 청크로 나누어 전송
                    content = step['content']
                    chunks = []
                    
                    # 약 30자 단위로 분리 (문장 구조 존중)
                    words = content.split(' ')
                    current_chunk = ""
                    
                    for word in words:
                        if len(current_chunk) + len(word) + 1 <= 30:
                            if current_chunk:
                                current_chunk += " " + word
                            else:
                                current_chunk = word
                        else:
                            chunks.append(current_chunk)
                            current_chunk = word
                    
                    if current_chunk:
                        chunks.append(current_chunk)
                    
                    # 청크별로 전송 (비균일 딜레이 적용)
                    for chunk in chunks:
                        # 1.6초 기본 + 0.1~0.8초 랜덤 딜레이 (기존 0.8초의 2배 + 랜덤성)
                        delay = 1.6 + random.uniform(0.1, 0.8)
                        await asyncio.sleep(delay)
                        
                        yield {
                            "type": "content",
                            "data": {},
                            "content": chunk
                        }
                    
                    # 단계 종료 후 추가 줄바꿈
                    await asyncio.sleep(random.uniform(0.5, 1.0))
                    yield {
                        "type": "content",
                        "data": {},
                        "content": "\n\n"
                    }
                
                # 사고과정 종료 태그 전송 (약간 더 긴 딜레이)
                await asyncio.sleep(random.uniform(1.5, 2.2))
                yield {
                    "type": "content",
                    "data": {},
                    "content": "</think>"
                }
                
                # 시각화 생성 - visualization_service_instance를 사용
                img_base64, chart_data = await self.visualization_service_instance.create_visualization(
                    data_points=data_points,
                    chart_type=chart_type_enum,
                    title=title
                )
                
                # 시각화 결과 전송
                yield {
                    "session_id": session_id,
                    "type": "visualization",
                    "data": {
                        "chart_type": chart_type_enum.value,
                        "chart_title": title,
                        "chart_base64": img_base64,
                        "chart_data": chart_data
                    }
                }
                
                # 응답 완료
                await asyncio.sleep(0.5)
                yield {
                    "type": "task_complete",
                    "data": {"message": "시각화 처리 완료"}
                }
                
                await asyncio.sleep(0.3)
                yield {
                    "type": "end",
                    "data": {"message": "스트리밍 응답 종료"}
                }
                
            except Exception as e:
                logger.error(f"시각화 처리 중 오류 발생: {str(e)}", exc_info=True)
                # 오류 메시지 전송
                yield {
                    "type": "error",
                    "data": {"message": f"시각화 생성 중 오류가 발생했습니다: {str(e)}"}
                }
                # 스트리밍 종료
                yield {
                    "type": "end",
                    "data": {"message": "오류로 인한 스트리밍 응답 종료"}
                }
        else:
            # 일반 RAG 처리 로직
            logger.info("일반 RAG 처리 진행")
            
            # ... 기존 RAG 처리 로직 ...
            
            # 임시 구현: 간단한 응답 반환
            yield {
                "type": "content",
                "data": {},
                "content": f"RAG 응답: 질문 '{query}'에 대한 답변입니다."
            }
            
            await asyncio.sleep(0.3)
            yield {
                "type": "end",
                "data": {"message": "RAG 처리 완료"}
            }
    
    def _detect_visualization_request(self, query: str) -> tuple[bool, str, str]:
        """
        사용자 쿼리에서 시각화 요청을 감지합니다.
        
        다음 3가지 특정 시각화 요청만 처리합니다:
        1. "미갱신 고객 비율을 차트로 보여줘" (pie chart)
        2. "STR 지연 건에 대한 그래프를 생성해줘" (bar chart)
        3. "규제 준수 일정을 타임라인으로 보여줘" (timeline chart)
        
        Args:
            query (str): 사용자 쿼리
            
        Returns:
            tuple[bool, str, str]: (시각화 요청 여부, 차트 타입, 시각화 쿼리)
        """
        query_lower = query.lower().strip()
        
        # 1. "미갱신 고객 비율을 차트로 보여줘" - 파이 차트
        if "미갱신 고객 비율" in query_lower or (
            "미갱신" in query_lower and "고객" in query_lower and "비율" in query_lower and 
            ("차트" in query_lower or "그래프" in query_lower) and 
            ("보여" in query_lower or "그려" in query_lower)
        ):
            return True, "pie", "미갱신 고객 비율을 차트로 보여줘"
            
        # 2. "STR 지연 건에 대한 그래프를 생성해줘" - 막대 차트  
        elif "str 지연" in query_lower or (
            "str" in query_lower and ("지연" in query_lower or "보고" in query_lower) and 
            ("그래프" in query_lower or "차트" in query_lower) and 
            ("생성" in query_lower or "만들어" in query_lower or "보여" in query_lower)
        ):
            return True, "bar", "STR 지연 건에 대한 그래프를 생성해줘"
            
        # 3. "규제 준수 일정을 타임라인으로 보여줘" - 타임라인 차트
        elif ("규제 준수 일정" in query_lower or "규제 준수 로드맵" in query_lower) or (
            "규제" in query_lower and "준수" in query_lower and "일정" in query_lower and 
            ("타임라인" in query_lower or "시간표" in query_lower or "로드맵" in query_lower) and 
            ("보여" in query_lower or "그려" in query_lower)
        ):
            return True, "timeline", "규제 준수 일정을 타임라인으로 보여줘"
            
        # 다른 질문은 시각화 요청으로 처리하지 않음
        return False, "", query
    
    def _split_text(self, text: str) -> List[str]:
        """
        텍스트를 작은 청크로 나눕니다.
        
        Args:
            text (str): 나눌 텍스트
            
        Returns:
            List[str]: 텍스트 청크 목록
        """
        # 문장 단위로 나누기
        sentences = text.split('. ')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if sentence and not sentence.endswith('.'):
                sentence += '.'
            
            if len(current_chunk) + len(sentence) + 1 > 100:  # 적절한 청크 크기 설정
                chunks.append(current_chunk)
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += ' ' + sentence
                else:
                    current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks

# WorkflowManager의 싱글톤 인스턴스 생성
workflow_manager = WorkflowManager()
