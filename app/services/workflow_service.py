# app/services/workflow_service.py: 애플리케이션의 핵심 워크플로우를 관리하는 서비스
from app.schemas.chat import ChatRequest, LLMReasoningStep, RetrievedDocument, LLMResponseChunk, MessageType
from app.services import llm_service, mattermost_service as mm_service, db_service
from app.services.external_rag_service import ExternalRAGService
from app.services.chat_history_service import ChatHistoryService # 추가
from typing import List, Optional, Dict, Any, AsyncGenerator
import os # 파일 경로 등 임시 처리를 위해
import asyncio # 추가
import logging
from app.services.llm_service import LLMService
from app.core.config import settings
import re
import random
from datetime import datetime
from threading import Lock
import json # json 임포트 추가

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 단일 사용자를 위한 전역 대화 히스토리
global_conversation_history: List[Dict[str, str]] = []

class WorkflowService:
    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 서비스 초기화
        self.db_initialized = False
        # 비동기 초기화를 위한 플래그
        self.llm_service = LLMService() # LLMService 인스턴스화
        self.external_rag_service = ExternalRAGService() # ExternalRAGService 인스턴스화
        self.chat_history_service = ChatHistoryService() # ChatHistoryService 인스턴스화 추가
        self.conversation_history: Dict[str, List[Dict[str, Any]]] = {} # 세션별 대화 기록 (인메모리, 프로덕션에서는 Redis 등 고려)
        self.session_meeting_contexts: Dict[str, MeetingContext] = {} # 세션별 meeting_context 저장
        
    def _format_sse_chunk(self, session_id: str, type: MessageType, content: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> str:
        """
        Formats a message chunk for Server-Sent Events (SSE).
        """
        payload = {
            "session_id": session_id,
            "type": type.value, # Enum 값을 문자열로 사용
        }
        if content is not None:
            payload["content"] = content
        if data is not None:
            payload["data"] = data
        
        json_payload = json.dumps(payload, ensure_ascii=False)
        return f"data: {json_payload}\n\n"

    async def async_initialize_db(self):
        """
        DB 초기화 및 테스트 데이터 추가
        """
        try:
            # DB 초기화
            success = await db_service.initialize()
            if success:
                logger.info("DB 초기화 성공")
                self.db_initialized = True
                
                # 테스트 데이터가 없는지 확인
                users = await db_service.get_users(limit=1)
                if not users:
                    logger.info("테스트 데이터 추가 시작...")
                    # 테스트 데이터 추가
                    await db_service.add_test_data()
                    logger.info("테스트 데이터 추가 완료")
            else:
                logger.error("DB 초기화 실패")
                self.db_initialized = False
        except Exception as e:
            logger.error(f"DB 초기화 오류: {str(e)}")
            self.db_initialized = False

    async def process_chat_request_stream(self, request: ChatRequest, session_id: str) -> AsyncGenerator[str, None]:
        logger.info(f"[{session_id}] 스트리밍 채팅 요청 시작: {request.query}")

        # 세션 기반 meeting_context 관리
        current_meeting_context: Optional[MeetingContext] = None
        if request.meeting_context:
            logger.info(f"[{session_id}] 요청에 새로운 meeting_context가 포함되어 세션 정보를 업데이트합니다.")
            self.session_meeting_contexts[session_id] = request.meeting_context
            current_meeting_context = request.meeting_context
        elif session_id in self.session_meeting_contexts:
            logger.info(f"[{session_id}] 요청에 meeting_context가 없지만, 저장된 세션 정보가 있어 이를 사용합니다.")
            current_meeting_context = self.session_meeting_contexts[session_id]
        else:
            logger.info(f"[{session_id}] 요청 및 세션 저장소에 meeting_context 정보가 없습니다.")

        conversation_history = self.chat_history_service.get_history(session_id)
        conversation_history_for_llm = []
        for entry in conversation_history:
            conversation_history_for_llm.append({"role": entry["role"], "parts": [{"text": entry["content"]}]})

        user_message = request.query
        # 0. 사용자 메시지 로깅 및 세션 ID 확인
        logger.info(f"[{session_id}] 스트리밍 채팅 요청 시작: {user_message}")
        self.chat_history_service.add_message(session_id, "user", user_message)

        # 1. 사용자 의도 파악 (LLM 또는 키워드 기반)
        intent_data = await self.llm_service.classify_intent(user_message) # 변경: llm_service 사용, session_id 제거 (llm_service.classify_intent는 session_id를 받지 않음)
        intent = intent_data.get("intent", "unknown") # intent_data가 dict라고 가정
        entities = intent_data.get("entities", {})    # 추출된 엔티티

        yield self._format_sse_chunk(
            session_id=session_id, 
            type=MessageType.INTENT_CLASSIFIED, 
            content=None, 
            data={"intent": intent, "entities": entities, "description": f"사용자 의도를 '{intent}'로 파악했습니다."}
        )

        # 대화 기록 가져오기 (LLM 컨텍스트용)
        prompt_for_llm = user_message # LLM에 전달할 최종 프롬프트

        if intent == "qna":
            # RAG 활성화 여부는 ChatRequest에 명시적인 필드가 없으므로, 'qna' 의도 자체를 RAG 시도 조건으로 간주합니다.
            # thinking step을 위한 search_params 유사 정보 구성
            rag_params_for_thinking_step = {
                "search_in_meeting_documents_only": request.search_in_meeting_documents_only,
                "target_document_ids": request.target_document_ids
            }
            yield self._format_sse_chunk(
                session_id=session_id, 
                type=MessageType.THINKING, 
                content=None, 
                data={"step_description": "RAG 검색을 시작합니다.", "details": rag_params_for_thinking_step}
            )
            try:
                search_type_for_rag = "related" if request.search_in_meeting_documents_only else "general"
                documents_data = await self.external_rag_service.search_documents(
                    query=request.query,
                    search_type=search_type_for_rag, # ChatRequest 필드 기반으로 search_type 설정
                    document_ids=request.target_document_ids, # ChatRequest 필드 직접 사용
                    user_id=None # ChatRequest에 user_id 없으므로 None 전달 (필요시 추가)
                )
                    
                if documents_data:
                    yield self._format_sse_chunk(session_id=session_id, type=MessageType.THINKING, content=None, data={"step_description": f"RAG 검색 완료: {len(documents_data)}개 문서 수신", "details": {"doc_count": len(documents_data)}})
                        
                    # 점수 기반 필터링 (0.7 이상)
                    filtered_documents = [doc for doc in documents_data if doc.score >= 0.7]
                        
                    if not filtered_documents and documents_data:
                         yield self._format_sse_chunk(session_id=session_id, type=MessageType.THINKING, content=None, data={"step_description": "수신된 모든 문서의 관련도 점수가 0.7 미만입니다. LLM은 일반 답변을 시도합니다.", "details": {"original_doc_count": len(documents_data)}})
                    elif filtered_documents:
                        yield self._format_sse_chunk(session_id=session_id, type=MessageType.THINKING, content=None, data={"step_description": f"필터링 결과: {len(filtered_documents)}개 문서가 LLM 컨텍스트에 포함됩니다.", "details": {"filtered_doc_count": len(filtered_documents)}})
                        for doc in filtered_documents:
                            yield self._format_sse_chunk(session_id=session_id, type=MessageType.RETRIEVED_DOCUMENT, content=None, data=doc.model_dump())
                    retrieved_documents_for_llm = filtered_documents
                    # LLM에 전달할 프롬프트 구성 시, 검색된 문서 내용을 포함 (필터링 된 것만)
                    if retrieved_documents_for_llm:
                        context_for_llm = "\n\n--- 참고 문서 ---\n"
                        for i, doc_obj in enumerate(retrieved_documents_for_llm):
                            context_for_llm += f"문서 {i+1} (ID: {doc_obj.document_id}, 점수: {doc_obj.score:.2f}):\n{doc_obj.text}\n\n"
                        prompt_for_llm = f"{request.query}\n\n{context_for_llm}"
                    # else: prompt_for_llm은 원래 request.query 유지

                else: # documents_data is None or empty
                    yield self._format_sse_chunk(session_id=session_id, type=MessageType.THINKING, content=None, data={"step_description": "RAG 검색 결과, 관련된 문서를 찾지 못했습니다. LLM이 일반 답변을 시도합니다.", "details": {}})

            except Exception as e:
                logger.error(f"[{session_id}] RAG 검색 중 오류: {e}", exc_info=True)
                yield self._format_sse_chunk(session_id=session_id, type=MessageType.ERROR, content=None, data={"error_message": "RAG 문서 검색 중 오류가 발생했습니다.", "details": str(e)})

            # LLM 응답 스트리밍
            yield self._format_sse_chunk(session_id=session_id, type=MessageType.THINKING, content=None, data={"step_description": "LLM 모델에 응답 생성을 요청합니다.", "details": {"query": request.query, "rag_docs_count": len(retrieved_documents_for_llm)}})
            
            try:
                async for llm_text_chunk in self.llm_service.generate_response_stream(
                    prompt=prompt_for_llm, 
                    retrieved_chunks=[doc.text for doc in retrieved_documents_for_llm], # doc.text 사용
                    conversation_history=conversation_history_for_llm
                ):
                    if isinstance(llm_text_chunk, str):
                        if llm_text_chunk.startswith("LLM 오류:"):
                            error_detail = llm_text_chunk[len("LLM 오류:"):].strip()
                            yield self._format_sse_chunk(session_id=session_id, type=MessageType.ERROR, content=None, data={"error_message": "LLM 응답 생성 중 오류 발생", "details": error_detail})
                            # LLM 오류 시 여기서 스트림을 중단할 수 있습니다. 예: return
                        else:
                            yield self._format_sse_chunk(session_id=session_id, type=MessageType.CONTENT, content=None, data={"content": llm_text_chunk})
                            # LLM 응답을 대화 기록에 추가 (모델 응답 부분만)
                            # 주의: 스트리밍 중이라 완전한 응답이 아닐 수 있음. 마지막에 한번에 추가하거나, 토큰별로 누적 필요.
                            # 여기서는 매 청크마다 기록하지 않고, 완료 후 전체 응답을 기록하는 것을 권장 (별도 로직 필요)
                    else:
                        logger.warning(f"[{session_id}] LLM 서비스로부터 예상치 못한 타입의 데이터 수신: {type(llm_text_chunk)}")

                # LLM 응답 스트리밍 완료 후 대화 기록 저장 (예시, 실제 구현은 더 정교해야 함)
                # 이 시점에서는 llm_text_chunk가 마지막 조각일 뿐, 전체 응답이 아님.
                # 전체 응답을 누적했다가 저장하는 로직이 필요.
                # temp_full_response = "..." # 누적된 전체 응답
                # self.chat_history_service.add_message(session_id, "assistant", temp_full_response)

                yield self._format_sse_chunk(session_id=session_id, type=MessageType.THINKING, content=None, data={"step_description": "LLM 응답 생성이 완료되었습니다.", "details": {}})

            except Exception as e:
                logger.error(f"[{session_id}] LLM 스트리밍 처리 중 예외 발생: {e}", exc_info=True)
                yield self._format_sse_chunk(session_id=session_id, type=MessageType.ERROR, content=None, data={"error_message": "LLM 응답 스트리밍 처리 중 예외가 발생했습니다.", "details": str(e)})

        elif intent == "send_mattermost_minutes":
            yield self._format_sse_chunk(session_id=session_id, type=MessageType.THINKING, content=None, data={"step_description": "Mattermost 회의록 전송 처리를 시작합니다."})
            logger.info(f"[{session_id}] Intent: send_mattermost_minutes")

            try:  # Outer try for the entire send_mattermost_minutes intent (catches e_main)
                meeting_context_to_use = current_meeting_context # 세션에서 가져온 컨텍스트 사용
                
                minutes_s3_url: Optional[str] = None
                meeting_title: Optional[str] = None
                participant_names_for_db_query: List[str] = [] # DB 조회를 위한 이름 목록, 여기서 초기화
                meeting_id_for_logging = "N/A"

                # 1. meeting_context_to_use 에서 S3 URL, 회의 제목, 회의 ID 등 정보 추출
                if meeting_context_to_use:
                    logger.info(f"[{session_id}] Mattermost 전송을 위해 사용될 meeting_context: {meeting_context_to_use.model_dump_json(indent=2)}")
                    if meeting_context_to_use.hub_meeting_id:
                        meeting_id_for_logging = meeting_context_to_use.hub_meeting_id
                    if meeting_context_to_use.hub_minutes_s3_url:
                        minutes_s3_url = meeting_context_to_use.hub_minutes_s3_url
                    if meeting_context_to_use.hub_meeting_title:
                        meeting_title = meeting_context_to_use.hub_meeting_title
                else:
                    logger.info(f"[{session_id}] 사용 가능한 meeting_context가 없습니다. LLM 엔티티 및 다른 정보 소스를 확인합니다.")

                # 2. S3 URL은 필수 - 없으면 진행 불가
                if not minutes_s3_url:
                    logger.warning(f"[{session_id}] 회의록 S3 URL 정보가 없습니다. Mattermost 전송을 진행할 수 없습니다.")
                    yield self._format_sse_chunk(
                        session_id=session_id, 
                        type=MessageType.ERROR, 
                        content=None, 
                        data={"error_message": "회의록 URL 정보 없음", "details": "Mattermost로 전송할 회의록의 S3 URL 정보가 없습니다."}
                    )
                    return # 여기서 함수 종료

                # 3. 회의 제목 결정 (Context -> LLM 'document_name' -> Default)
                llm_doc_name = entities.get('document_name')
                if not meeting_title and llm_doc_name:
                    meeting_title = llm_doc_name
                    logger.info(f"[{session_id}] Context에 제목이 없고 LLM 추출 'document_name'을 회의 제목으로 사용: {meeting_title}")
                
                if not meeting_title: # 최종 제목 폴백
                    meeting_title = "제목 없는 회의"
                    logger.info(f"[{session_id}] 기본 회의 제목 사용: {meeting_title}")

                # 4. 수신자 결정 (LLM target_user_or_channel 우선, 없으면 Hub 참여자 전체)
                target_user_from_llm = entities.get("target_user_or_channel")

                if target_user_from_llm:
                    logger.info(f"[{session_id}] LLM이 추출한 대상 사용: '{target_user_from_llm}'. 해당 대상에게만 전송합니다.")
                    participant_names_for_db_query.append(target_user_from_llm)
                elif meeting_context_to_use and meeting_context_to_use.hub_participant_names:
                    logger.info(f"[{session_id}] LLM 추출 대상이 없고, Hub 제공 참여자 목록이 있어 전체 참여자에게 전송합니다.")
                    logger.info(f"[{session_id}] Hub 제공 참여자 이름 목록 (원본, from context): {meeting_context_to_use.hub_participant_names}")
                    for name_group_str in meeting_context_to_use.hub_participant_names:
                        if isinstance(name_group_str, str):
                            individual_names = [name.strip() for name in name_group_str.split(',') if name.strip()]
                            participant_names_for_db_query.extend(individual_names)
                    logger.info(f"[{session_id}] Hub 제공 참여자 이름 목록 (파싱됨, for DB query): {participant_names_for_db_query}")
                # else: 이 경우 participant_names_for_db_query는 비어있게 됨
                
                # 5. 최종 수신자 확인 - 없으면 진행 불가
                if not participant_names_for_db_query:
                    logger.warning(f"[{session_id}] Mattermost 전송 대상을 특정할 수 없습니다. (LLM 엔티티와 Hub 참여자 정보 모두 확인 후에도 대상 없음)")
                    yield self._format_sse_chunk(
                        session_id=session_id, 
                        type=MessageType.ERROR, 
                        content=None, 
                        data={"error_message": "수신자 정보 없음", "details": "회의록을 전송할 대상 사용자를 지정하거나, 회의 정보에 참여자가 포함되어야 합니다."}
                    )
                    return

                # 6. DB에서 Mattermost 사용자 ID 조회 및 메시지 전송 로직 (기존 코드 활용)
                final_target_user_ids: List[str] = []
                final_target_channel_ids: List[str] = []

                if participant_names_for_db_query:
                    logger.info(f"[{session_id}] DB에서 Mattermost ID 조회 시도 (참여자 이름: {participant_names_for_db_query})")
                    try:
                        # self.db_service.get_mattermost_user_ids_by_names 대신 db_service 모듈의 함수 직접 호출
                        mm_ids_from_db_dict = await db_service.get_mattermost_user_ids_by_names(participant_names_for_db_query)
                        
                        if mm_ids_from_db_dict:
                            logger.info(f"[{session_id}] DB 조회 결과 (이름 -> MM ID): {mm_ids_from_db_dict}")
                            # DB에서 성공적으로 조회된 ID들을 final_target_user_ids에 추가 (중복 회피)
                            for name, mm_id in mm_ids_from_db_dict.items():
                                if mm_id and mm_id not in final_target_user_ids:
                                    final_target_user_ids.append(mm_id)
                                elif not mm_id:
                                    logger.warning(f"[{session_id}] DB에서 '{name}'님의 Mattermost ID를 찾지 못했습니다.")
                        else:
                            logger.info(f"[{session_id}] DB에서 제공된 이름으로 조회된 Mattermost ID가 없습니다.")
                    except AttributeError as ae:
                        # get_mattermost_user_ids_by_names 함수가 db_service 모듈에 없는 경우
                        logger.error(f"[{session_id}] db_service 모듈에 get_mattermost_user_ids_by_names 함수가 정의되지 않았습니다: {ae}", exc_info=True)
                        yield self._format_sse_chunk(session_id=session_id, type=MessageType.ERROR, content=None, data={"error_message": "내부 설정 오류: DB 서비스 기능 누락", "details": "Mattermost 사용자 ID 조회 기능을 사용할 수 없습니다."})
                        # 이 경우, LLM이 추출한 ID만 사용하거나, 오류로 처리하고 중단할 수 있습니다.
                        # 여기서는 일단 LLM ID만으로 진행하도록 두거나, 혹은 바로 return하여 중단할 수 있습니다.
                    except Exception as e_db_query:
                        logger.error(f"[{session_id}] DB에서 Mattermost 사용자 ID 조회 중 예외 발생: {e_db_query}", exc_info=True)
                        yield self._format_sse_chunk(session_id=session_id, type=MessageType.ERROR, content=None, data={"error_message": "DB 조회 중 오류가 발생했습니다.", "details": str(e_db_query)})
                        # DB 오류 시, LLM이 추출한 ID만으로 진행할지, 아니면 전체 실패로 처리할지 결정 필요
                        # 여기서는 일단 LLM ID만으로 진행
                else:
                    logger.info(f"[{session_id}] 허브로부터 DB 조회를 위한 참여자 이름이 제공되지 않았습니다.")

                # 최종 전송 대상 Mattermost 사용자 ID 목록 로깅
                logger.info(f"[{session_id}] 최종 전송 대상 사용자 ID: {final_target_user_ids}")
                logger.info(f"[{session_id}] 최종 전송 대상 채널 ID: {final_target_channel_ids}")

                # 실제 메시지 전송 로직 (Inner Try)
                try: # Inner try for sending messages (catches e_send)
                    if not final_target_user_ids and not final_target_channel_ids:
                        logger.warning(f"[{session_id}] Mattermost 전송 대상 사용자 또는 채널이 지정되지 않았습니다. 테스트 사용자에게 전송 시도합니다.")
                        yield self._format_sse_chunk(session_id=session_id, type=MessageType.THINKING, content=None, data={"step_description": "전송 대상이 없어 테스트 사용자에게 전송 시도 중..."})
                        test_username = "@woorifisa1" # 메모리에서 가져온 테스트 사용자 이름
                        try:
                            test_user_id = await mm_service.find_mattermost_user_id(test_username)
                            if test_user_id:
                                final_target_user_ids.append(test_user_id)
                                logger.info(f"[{session_id}] 테스트 사용자 '{test_username}' (ID: {test_user_id})에게 전송합니다.")
                                yield self._format_sse_chunk(session_id=session_id, type=MessageType.INFO, content=f"테스트 사용자 '{test_username}'에게 회의록 링크를 전송합니다.")
                            else:
                                logger.error(f"[{session_id}] 테스트 사용자 '{test_username}'의 ID를 찾지 못했습니다.")
                                yield self._format_sse_chunk(session_id=session_id, type=MessageType.ERROR, content=f"테스트 사용자 '{test_username}'을 찾을 수 없어 전송에 실패했습니다.")
                                # return # 여기서 바로 리턴할 수도 있음
                        except Exception as e_find_test_user:
                            logger.error(f"[{session_id}] 테스트 사용자 ID 조회 중 오류: {e_find_test_user}", exc_info=True)
                            yield self._format_sse_chunk(session_id=session_id, type=MessageType.ERROR, content=f"테스트 사용자 조회 중 오류: {e_find_test_user}")
                            # return
                        
                    if not final_target_user_ids and not final_target_channel_ids:
                        logger.error(f"[{session_id}] 최종적으로 전송할 대상이 없습니다.")
                        yield self._format_sse_chunk(session_id=session_id, type=MessageType.ERROR, content="Mattermost에 회의록을 전송할 대상(사용자 또는 채널)을 찾을 수 없습니다.")
                        return # 전송 대상 없으면 여기서 종료

                    # 메시지 생성
                    message_content = f"안녕하세요. 요청하신 '{meeting_title}' 회의록 링크를 전달드립니다:\n{minutes_s3_url}"
                    logger.info(f"[{session_id}] 생성된 메시지 내용: {message_content}")

                    sent_to_users_count = 0
                    sent_to_channels_count = 0

                    # 사용자에게 메시지 전송
                    for user_id in final_target_user_ids:
                        try:
                            yield self._format_sse_chunk(session_id=session_id, type=MessageType.THINKING, content=None, data={"step_description": f"사용자 ID '{user_id}'에게 메시지 전송 중..."})
                            await mm_service.send_message_to_user(user_id=user_id, message=message_content)
                            logger.info(f"[{session_id}] 사용자 ID '{user_id}'에게 메시지 전송 성공")
                            sent_to_users_count += 1
                        except Exception as e_send_user:
                            logger.error(f"[{session_id}] 사용자 ID '{user_id}'에게 메시지 전송 실패: {e_send_user}", exc_info=True)
                            yield self._format_sse_chunk(session_id=session_id, type=MessageType.ERROR, content=f"사용자 ID '{user_id}'에게 메시지 전송 중 오류: {e_send_user}")
                        
                    # 채널에 메시지 전송
                    for channel_id in final_target_channel_ids:
                        try:
                            yield self._format_sse_chunk(session_id=session_id, type=MessageType.THINKING, content=None, data={"step_description": f"채널 ID '{channel_id}'에 메시지 전송 중..."})
                            await mm_service.send_message_to_channel(channel_id=channel_id, message=message_content)
                            logger.info(f"[{session_id}] 채널 ID '{channel_id}'에 메시지 전송 성공")
                            sent_to_channels_count += 1
                        except Exception as e_send_channel:
                            logger.error(f"[{session_id}] 채널 ID '{channel_id}'에 메시지 전송 실패: {e_send_channel}", exc_info=True)
                            yield self._format_sse_chunk(session_id=session_id, type=MessageType.ERROR, content=f"채널 ID '{channel_id}'에 메시지 전송 중 오류: {e_send_channel}")

                    if sent_to_users_count > 0 or sent_to_channels_count > 0:
                        success_message = f"'{meeting_title}' 회의록 링크를 {sent_to_users_count}명의 사용자와 {sent_to_channels_count}개의 채널에 성공적으로 전송했습니다."
                        if sent_to_users_count == 0 and sent_to_channels_count == 0: # 이 경우는 위에서 처리되지만, 방어적으로
                            success_message = "회의록 링크 전송을 시도했지만, 실제 전송된 대상이 없습니다."
                        
                        logger.info(f"[{session_id}] {success_message}")
                        yield self._format_sse_chunk(session_id=session_id, type=MessageType.RESULT, content=success_message, data={"meeting_title": meeting_title, "s3_link": minutes_s3_url, "users_sent": sent_to_users_count, "channels_sent": sent_to_channels_count})
                    else:
                        # 이 경우는 이미 위에서 처리되었어야 함 (no final_target_user_ids and not final_target_channel_ids)
                        # 하지만 만약 모든 전송 시도가 실패했다면
                        error_message = f"'{meeting_title}' 회의록 링크 전송에 실패했습니다. (대상: {len(final_target_user_ids)}명 사용자, {len(final_target_channel_ids)}개 채널)"
                        logger.error(f"[{session_id}] {error_message}")
                        yield self._format_sse_chunk(session_id=session_id, type=MessageType.ERROR, content=error_message)
                    
                    return # Inner try 성공 시 여기서 종료

                except Exception as e_send: # Inner try의 exception (메시지 전송 중 오류)
                    error_message = f"Mattermost 메시지 전송 중 예기치 않은 오류 발생 (회의: {meeting_title}): {e_send}"
                    logger.error(f"[{session_id}] {error_message}", exc_info=True)
                    yield self._format_sse_chunk(session_id=session_id, type=MessageType.ERROR, content=error_message)
                    return # Inner try 실패 시 여기서 종료

            except Exception as e_main: # Outer try의 exception (전체 인텐트 처리 중 오류)
                error_message = f"Mattermost 회의록 전송 처리 중 예기치 않은 오류 발생: {e_main}"
                logger.error(f"[{session_id}] {error_message}", exc_info=True)
                yield self._format_sse_chunk(session_id=session_id, type=MessageType.ERROR, content=error_message)
                return # Outer try 실패 시 여기서 종료
        
        elif intent == "create_calendar_event":
            # TODO: 캘린더 이벤트 생성 로직 구현
            pass
            yield self._format_sse_chunk(
                session_id=session_id, 
                type=MessageType.INFO,
                content=None, 
                data={"message": "캘린더 이벤트 생성을 시작합니다."}
            )

# WorkflowService 인스턴스 생성 (싱글톤 패턴 적용됨)
workflow_manager = WorkflowService()
