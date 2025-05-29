"""
Q&A 워크플로우 서비스 모듈
질의응답 처리를 담당하는 워크플로우 서비스를 제공합니다.
"""
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator
from app.schemas.chat import ChatRequest, LLMResponseChunk, MessageType, RetrievedDocument
from app.services.workflow.workflow_core import WorkflowCore
from app.services.external_rag_service import ExternalRAGService

logger = logging.getLogger(__name__)

class QnAWorkflowService:
    """질의응답 처리를 담당하는 워크플로우 서비스"""
    
    def __init__(self, core: WorkflowCore):
        """
        Q&A 워크플로우 서비스를 초기화합니다.
        
        Args:
            core (WorkflowCore): 워크플로우 코어 인스턴스
        """
        self.core = core
        self.llm_service = core.llm_service
        self.external_rag_service = core.external_rag_service
        self.chat_history_service = core.chat_history_service
    
    async def process_qna_request(
        self, 
        request: ChatRequest, 
        session_id: str,
        intent_result: Dict[str, Any]
    ) -> AsyncGenerator[LLMResponseChunk, None]:
        """
        Q&A 요청을 처리하고 응답을 스트리밍합니다.
        
        Args:
            request (ChatRequest): 채팅 요청 객체
            session_id (str): 세션 ID
            intent_result (Dict[str, Any]): 의도 분류 결과
            
        Yields:
            LLMResponseChunk: 응답 청크
        """
        logger.info(f"[{session_id}] Q&A 처리 시작: {request.query}")
        
        # RAG 검색 시작 알림
        rag_thinking_details = {
            "search_in_meeting_documents_only": request.search_in_meeting_documents_only,
            "target_document_ids": request.target_document_ids
        }
        logger.info(f"[{session_id}] THINKING (RAG 검색 시작) details: {rag_thinking_details}")
        
        yield LLMResponseChunk(
            session_id=session_id,
            type=MessageType.THINKING,
            data={"step_description": "RAG 검색을 시작합니다."}
        )
        
        # RAG 검색 수행
        retrieved_documents: List[RetrievedDocument] = []
        try:
            documents_data = await self.external_rag_service.search_documents(
                query=request.query,
                search_in_meeting_only=request.search_in_meeting_documents_only,
                document_ids=request.target_document_ids
            )
            
            doc_count = len(documents_data) if documents_data else 0
            logger.info(f"[{session_id}] THINKING (RAG 검색 완료) 문서 {doc_count}개 검색됨")
            
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.THINKING,
                data={"step_description": f"RAG 검색 완료: {doc_count}개 문서 수신"}
            )
            
            # 관련성 점수 기반 필터링 (예: 0.7 이상)
            if documents_data:
                relevant_documents = [doc for doc in documents_data if doc.score >= 0.7]
                
                if relevant_documents:
                    # 최대 5개 사용
                    retrieved_documents = relevant_documents[:5]
                    
                    # 검색 결과 정보
                    docs_info = {
                        "original_doc_count": len(documents_data),
                        "relevant_doc_count": len(relevant_documents),
                        "used_doc_count": len(retrieved_documents),
                        "scores": [doc.score for doc in retrieved_documents]
                    }
                    logger.info(f"[{session_id}] 검색된 문서 정보: {docs_info}")
                    
                    # 클라이언트에 검색된 문서 전송
                    for i, doc in enumerate(retrieved_documents):
                        yield LLMResponseChunk(
                            session_id=session_id,
                            type=MessageType.RETRIEVED_DOCUMENT,
                            data={
                                "document_id": doc.document_id or f"doc_{i+1}",
                                "content_chunk": doc.content_chunk,
                                "score": doc.score,
                                "metadata": doc.metadata
                            }
                        )
                else: # 점수 0.7 이상 문서 없음
                    logger.info(f"[{session_id}] 점수 0.7 이상인 관련 문서를 찾지 못했습니다. (원본 문서 수: {len(documents_data)})")
                    # retrieved_documents는 초기에 빈 리스트로 설정되어 있으므로, 이 경우에도 빈 리스트로 유지됩니다.
            
            else: # RAG 검색 결과 문서 없음
                logger.info(f"[{session_id}] RAG 검색 결과, 문서를 찾지 못했습니다.")
                # retrieved_documents는 초기에 빈 리스트로 설정되어 있으므로, 이 경우에도 빈 리스트로 유지됩니다.
        except Exception as e:
            logger.error(f"[{session_id}] RAG 검색 오류: {str(e)}")
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.ERROR,
                data={"error_message": "문서 검색 중 오류가 발생했습니다.", "details": str(e)}
            )
        
        # 대화 기록 가져오기
        conversation_history = self.chat_history_service.get_recent_history(session_id, k=10)
        conversation_history_for_llm = []
        
        for entry in conversation_history:
            # 빈 메시지 필터링
            if entry.get("content") and entry.get("content").strip():
                conversation_history_for_llm.append({
                    "role": entry["role"], 
                    "content": entry["content"]  # Gemini 형식에 맞게 수정
                })
            else:
                logger.warning(f"[{session_id}] 빈 메시지 필터링: {entry}")
        
        # 현재 쿼리를 대화 기록에 추가
        if request.query and request.query.strip():
            # 현재 쿼리를 대화 기록에 미리 추가 (이중 추가 방지 위해 여기서만 추가)
            self.chat_history_service.add_message(session_id, "user", request.query)
            logger.info(f"[{session_id}] 현재 쿼리를 대화 기록에 추가: {request.query[:50]}{'...' if len(request.query) > 50 else ''}")
        
        logger.info(f"[{session_id}] 대화 기록 {len(conversation_history_for_llm)}개 메시지 변환 완료")
        
        # LLM으로 응답 생성
        logger.info(f"[{session_id}] LLM 응답 생성 시작")
        
        try:
            # LLM 스트리밍 응답 생성
            current_content = ""
            received_any_content = False
            
            async for content_chunk in self.llm_service.generate_response_stream(
                prompt=request.query,
                conversation_history=conversation_history_for_llm,
                retrieved_documents=retrieved_documents
            ):
                # LLMReasoningStep 객체인 경우 추론 단계로 처리
                if isinstance(content_chunk, dict) and "step_description" in content_chunk:
                    # 즉시 추론 단계 내용 전달
                    yield LLMResponseChunk(
                        session_id=session_id,
                        type=MessageType.LLM_REASONING_STEP,
                        data=content_chunk
                    )
                    received_any_content = True
                # 문자열인 경우 일반 응답 내용으로 처리
                elif isinstance(content_chunk, str):
                    # 각 토큰이 의미 있는 내용을 가지고 있는지 확인 (빈 문자열 또는 공백/줄바꿈만 있는 경우 필터링)
                    if content_chunk.strip():
                        current_content += content_chunk
                        # 토큰별로 즉시 전달하여 실시간 스트리밍 효과
                        yield LLMResponseChunk(
                            session_id=session_id,
                            type=MessageType.CONTENT,
                            content=content_chunk
                        )
                        received_any_content = True
            
            # 응답이 없는 경우 기본 메시지 제공
            if not received_any_content:
                logger.warning(f"[{session_id}] LLM이 응답을 생성하지 않았습니다.")
                default_message = "죄송합니다. 현재 응답을 생성할 수 없습니다. 다시 질문해 주세요."
                current_content = default_message
                yield LLMResponseChunk(
                    session_id=session_id,
                    type=MessageType.CONTENT,
                    content=default_message
                )
            
            # 응답 대화 기록에 추가
            if current_content:
                self.chat_history_service.add_message(session_id, "assistant", current_content)
                
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.END,
                data={"message": "Q&A 응답 생성 완료"}
            )
            
        except Exception as e:
            logger.error(f"[{session_id}] LLM 응답 생성 오류: {str(e)}", exc_info=True)
            error_message = f"응답 생성 중 오류가 발생했습니다: {str(e)}"
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.ERROR,
                data={"error_message": error_message, "details": str(e)}
            )
            
            # 오류 메시지를 대화 기록에 추가
            self.chat_history_service.add_message(session_id, "assistant", error_message)
