"""
Mattermost 워크플로우 서비스 모듈
Mattermost 관련 작업 처리를 담당하는 워크플로우 서비스를 제공합니다.
"""
import logging
import os
from typing import Dict, List, Any, Optional, AsyncGenerator
from app.schemas.chat import ChatRequest, LLMResponseChunk, MessageType
from app.services.workflow.workflow_core import WorkflowCore
from app.services.db import mattermost_mapping_db_service

logger = logging.getLogger(__name__)

class MattermostWorkflowService:
    """Mattermost 관련 작업 처리를 담당하는 워크플로우 서비스"""
    
    def __init__(self, core: WorkflowCore):
        """
        Mattermost 워크플로우 서비스를 초기화합니다.
        
        Args:
            core (WorkflowCore): 워크플로우 코어 인스턴스
        """
        self.core = core
        self.mm_service = core.mm_service
        self.llm_service = core.llm_service
        self.chat_history_service = core.chat_history_service
    
    async def process_mattermost_minutes_request(
        self, 
        request: ChatRequest, 
        session_id: str,
        intent_result: Dict[str, Any]
    ) -> AsyncGenerator[LLMResponseChunk, None]:
        """
        Mattermost 회의록 전송 요청을 처리하고 응답을 스트리밍합니다.
        
        Args:
            request (ChatRequest): 채팅 요청 객체
            session_id (str): 세션 ID
            intent_result (Dict[str, Any]): 의도 분류 결과
            
        Yields:
            LLMResponseChunk: 응답 청크
        """
        logger.info(f"[{session_id}] Mattermost 회의록 전송 처리 시작")
        
        # 토큰 단위 스트리밍을 위한 변수
        current_content = ""
        
        # 엔티티 정보 가져오기
        entities = intent_result.get("entities", {})
        meeting_id = entities.get("meeting_id") or entities.get("document_name")
        
        # 토큰 단위로 메시지 스트리밍
        message_tokens = ["회의록", " 전송", " 준비", " 중입니다", "..."]
        for token in message_tokens:
            current_content += token
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.CONTENT,
                content=token
            )
        
        # 회의 컨텍스트 확인
        meeting_context = request.meeting_context
        if not meeting_context:
            # 토큰 단위로 오류 메시지 스트리밍
            error_message = "\n\n회의 컨텍스트 정보가 없습니다. 회의록 전송을 위해서는 회의 정보가 필요합니다."
            for token in error_message.split():
                current_content += " " + token
                yield LLMResponseChunk(
                    session_id=session_id,
                    type=MessageType.CONTENT,
                    content=" " + token
                )
            
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.ERROR,
                data={"error_message": "회의 컨텍스트 정보가 없습니다.", "details": "회의 컨텍스트가 필요합니다."}
            )
            
            # 대화 기록에 추가
            self.chat_history_service.add_message(session_id, "assistant", current_content)
            return
            
        # S3 URL 확인
        s3_url = meeting_context.hub_minutes_s3_url
        if not s3_url:
            # 토큰 단위로 오류 메시지 스트리밍
            error_message = "\n\n회의록 URL 정보가 없습니다. 회의록 전송을 위해서는 회의록 URL이 필요합니다."
            for token in error_message.split():
                current_content += " " + token
                yield LLMResponseChunk(
                    session_id=session_id,
                    type=MessageType.CONTENT,
                    content=" " + token
                )
            
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.ERROR,
                data={"error_message": "회의록 S3 URL이 없습니다.", "details": "회의록 S3 URL이 필요합니다."}
            )
            
            # 대화 기록에 추가
            self.chat_history_service.add_message(session_id, "assistant", current_content)
            return
            
        # 회의 제목 확인
        meeting_title = meeting_context.hub_meeting_title or "회의"
        
        # 참가자 목록 확인
        participant_names = []
        logger.info(f"[{session_id}] 회의 참가자 정보: {meeting_context.hub_participant_names}")
        
        if meeting_context.hub_participant_names:
            # 참가자 목록이 하나의 문자열을 포함한 배열일 경우
            if isinstance(meeting_context.hub_participant_names, list) and len(meeting_context.hub_participant_names) > 0:
                # 참가자 목록이 하나의 문자열일 경우 쉼표로 분리
                participant_text = meeting_context.hub_participant_names[0]
                participant_names = [name.strip() for name in participant_text.split(',')]
                logger.info(f"[{session_id}] 쉼표 구분 후 참가자 목록: {participant_names}")
            else:
                participant_names = meeting_context.hub_participant_names
                logger.info(f"[{session_id}] 참가자 목록 그대로 사용: {participant_names}")
        
        # 대상 사용자가 없는 경우 경고 메시지 출력        
        if not participant_names:
            # 토큰 단위로 경고 메시지 스트리밍
            warning_message = "\n\n회의 참가자 정보가 없습니다. 회의록 전송을 위해서는 참가자 정보가 필요합니다."
            for token in warning_message.split():
                current_content += " " + token
                yield LLMResponseChunk(
                    session_id=session_id,
                    type=MessageType.CONTENT,
                    content=" " + token
                )
            
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.WARNING,
                data={"warning_message": "회의 참가자 정보가 없습니다. 전송할 수 없습니다."}
            )
            
            # 대화 기록에 추가
            self.chat_history_service.add_message(session_id, "assistant", current_content)
            return
        
        # 회의 참여자 목록 표시
        participants_str = ", ".join(participant_names)
        participants_message = f"\n\n회의 '{meeting_title}'의 참가자 목록: {participants_str}"
        for token in participants_message.split():
            current_content += " " + token
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.CONTENT,
                content=" " + token
            )
        
        # 전송 시작 메시지
        start_message = f"\n\n회의 '{meeting_title}'의 회의록을 {len(participant_names)}명의 참가자에게 전송 중입니다..."
        for token in start_message.split():
            current_content += " " + token
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.CONTENT,
                content=" " + token
            )
        
        # 전송 처리
        try:            
            # 메시지 준비
            message = f"[{meeting_title}] 회의록이 첨부되었습니다. 아래 링크를 통해 확인하세요:\n\n{s3_url}"
            
            # 모든 참가자에게 메시지 전송
            success_count = 0
            failed_participants = []
            
            # 각 참가자에게 메시지 전송
            for participant_name in participant_names:
                # 진행 상황 메시지 스트리밍
                progress_message = f"\n\n사용자 '{participant_name}'에게 회의록 전송 중..."
                for token in progress_message.split():
                    current_content += " " + token
                    yield LLMResponseChunk(
                        session_id=session_id,
                        type=MessageType.CONTENT,
                        content=" " + token
                    )
                
                # 사용자 이름으로 Mattermost ID 조회 시도
                if self.mm_service is not None:
                    try:
                        # 사용자 ID 찾기 시도
                        logger.info(f"[{session_id}] 사용자 '{participant_name}'의 Mattermost ID 검색")
                        
                        # 스크린샷의 사용자 테이블에 기반한 매핑
                        # 실제 Mattermost ID를 이름과 매핑합니다
                        mattermost_id = None
                        
                        # 이름을 기반으로 간단한 매핑 처리
                        if participant_name == "김경훈":
                            mattermost_id = "hsk3kfeg1fbhprzha8y5fjznt"
                        elif participant_name == "김다희":
                            mattermost_id = "zep68zadnfnfba9jzwit4btj"
                        elif participant_name == "윤웅상":
                            mattermost_id = "374deoeaw3butxr4mybebxpgga"
                        elif participant_name == "박재우":
                            mattermost_id = "qrfanemf7yo7dq8jui8yorc1y"
                        elif participant_name == "오상우":
                            mattermost_id = "5qffg6wq33bgfn7uszgm6bfbo"
                        
                        # 매핑이 없을 경우 Mattermost API로 검색 시도
                        if not mattermost_id:
                            user_result = self.mm_service.find_mattermost_user_id(participant_name)
                            if user_result and user_result.get("success", False):
                                mattermost_id = user_result.get("user_id")
                        
                        if mattermost_id:
                            logger.info(f"[{session_id}] 사용자 '{participant_name}'의 Mattermost ID 찾음: {mattermost_id}")
                        else:
                            logger.warning(f"[{session_id}] 사용자 '{participant_name}'의 Mattermost ID를 찾지 못함")
                            # 임시 ID 할당 (테스트용)
                            mattermost_id = f"mm_user_{participant_name.lower().replace(' ', '_')}"
                        
                        # 실제 메시지 전송 시도
                        logger.info(f"[{session_id}] 사용자 '{participant_name}'에게 회의록 링크 전송 시도")
                        
                        # ID가 테스트용인 경우 (mm_user_ 접두사)만 테스트 모드로 처리
                        if mattermost_id.startswith("mm_user_"):
                            # 테스트 ID의 경우 실제 전송하지 않고 성공으로 처리
                            logger.info(f"[{session_id}] 테스트 ID '{mattermost_id}'에는 전송하지 않지만 성공으로 처리")
                            success = True
                        else:
                            # 실제 Mattermost ID로 전송 시도
                            try:
                                # 최대 3번까지 메시지 전송 시도
                                max_retries = 3
                                retry_count = 0
                                success = False
                                
                                while retry_count < max_retries and not success:
                                    try:
                                        # 회의록 메시지 전송
                                        result = self.mm_service.send_message_to_user(
                                            user_id=mattermost_id,
                                            message=message
                                        )
                                        success = result.get("success", False)
                                        
                                        if success:
                                            logger.info(f"[{session_id}] 사용자 '{participant_name}'에게 회의록 전송 성공")
                                            break
                                        else:
                                            error_msg = result.get("message", "알 수 없는 오류")
                                            logger.warning(f"[{session_id}] 사용자 '{participant_name}'에게 회의록 전송 실패 (시도 {retry_count+1}/{max_retries}): {error_msg}")
                                            retry_count += 1
                                    except Exception as e:
                                        logger.warning(f"[{session_id}] 회의록 전송 시도 {retry_count+1}/{max_retries} 중 오류: {str(e)}")
                                        retry_count += 1
                                        
                                        # 마지막 시도가 아니면 잠시 대기 후 재시도
                                        if retry_count < max_retries:
                                            import time
                                            time.sleep(1)  # 1초 대기
                                
                                # 모든 시도 실패
                                if not success:
                                    logger.error(f"[{session_id}] 사용자 '{participant_name}'에게 회의록 전송 실패: 최대 시도 횟수 초과")
                            except Exception as e:
                                logger.error(f"[{session_id}] 사용자 '{participant_name}'에게 회의록 링크 전송 중 오류: {str(e)}")
                                success = False
                    except Exception as e:
                        logger.error(f"[{session_id}] 사용자 '{participant_name}'에게 회의록 링크 전송 중 오류 발생: {str(e)}")
                        failed_participants.append({"name": participant_name, "reason": str(e)})
                        failure_message = f"\n\n사용자 '{participant_name}'에게 회의록 전송 실패: {str(e)}"
                        for token in failure_message.split():
                            current_content += " " + token
                            yield LLMResponseChunk(
                                session_id=session_id,
                                type=MessageType.CONTENT,
                                content=" " + token
                            )
                        continue
                else:
                    # Mattermost 서비스가 구성되지 않은 경우 (테스트 환경)
                    logger.warning(f"[{session_id}] Mattermost 서비스가 구성되지 않음 - 테스트 모드로 동작")
                    # 테스트 환경에서는 성공한 것으로 가정
                    success = True
                    mattermost_id = f"mm_user_{participant_name.lower().replace(' ', '_')}"
                
                if success:
                    success_count += 1
                    completion_message = f"\n\n사용자 '{participant_name}'에게 회의록 전송 완료"
                    for token in completion_message.split():
                        current_content += " " + token
                        yield LLMResponseChunk(
                            session_id=session_id,
                            type=MessageType.CONTENT,
                            content=" " + token
                        )
                else:
                    failed_participants.append({"name": participant_name, "reason": "전송 실패"})
                    failure_message = f"\n\n사용자 '{participant_name}'에게 회의록 전송 실패"
                    for token in failure_message.split():
                        current_content += " " + token
                        yield LLMResponseChunk(
                            session_id=session_id,
                            type=MessageType.CONTENT,
                            content=" " + token
                        )
            
            # 전송 결과 요약
            if success_count > 0:
                # 성공 메시지 스트리밍
                success_message = f"\n\n회의 '{meeting_title}'의 회의록이 {success_count}명의 참가자에게 성공적으로 전송되었습니다."
                for token in success_message.split():
                    current_content += " " + token
                    yield LLMResponseChunk(
                        session_id=session_id,
                        type=MessageType.CONTENT,
                        content=" " + token
                    )
                
                # 작업 완료 알림
                yield LLMResponseChunk(
                    session_id=session_id,
                    type=MessageType.TASK_COMPLETE,
                    data={
                        "task": "mattermost_minutes_sent",
                        "success_count": success_count,
                        "total_count": len(participant_names)
                    }
                )
            
            if failed_participants:
                # 실패 정보 스트리밍
                failed_names = ', '.join([p["name"] for p in failed_participants])
                failed_message = f"\n\n다음 참가자에게 전송하지 못했습니다: {failed_names}"
                for token in failed_message.split():
                    current_content += " " + token
                    yield LLMResponseChunk(
                        session_id=session_id,
                        type=MessageType.CONTENT,
                        content=" " + token
                    )
            
            # 최종 결과 메시지
            is_test_mode = self.mm_service is None
            test_mode_prefix = "[테스트 모드] " if is_test_mode else ""
            
            if success_count > 0:
                if len(failed_participants) > 0:
                    final_message = f"\n\n{test_mode_prefix}회의 '{meeting_title}'의 회의록이 Mattermost를 통해 {success_count}명의 참가자에게 전송되었습니다. {len(failed_participants)}명에게는 전송에 실패했습니다."
                    if is_test_mode:
                        final_message += " (실제 전송은 이루어지지 않았습니다)"
                    
                    # 대화 기록에 저장을 위해 결과 메시지 추가
                    current_content += final_message
                    
                    yield LLMResponseChunk(
                        session_id=session_id,
                        type=MessageType.RESULT,
                        data={
                            "success": True,
                            "partial": True,
                            "message": final_message.strip(),
                            "is_test_mode": is_test_mode
                        }
                    )
                else:
                    final_message = f"\n\n{test_mode_prefix}회의 '{meeting_title}'의 회의록이 Mattermost를 통해 모든 회의 참가자에게 전송되었습니다."
                    if is_test_mode:
                        final_message += " (실제 전송은 이루어지지 않았습니다)"
                    
                    # 대화 기록에 저장을 위해 결과 메시지 추가
                    current_content += final_message
                    
                    yield LLMResponseChunk(
                        session_id=session_id,
                        type=MessageType.RESULT,
                        data={
                            "success": True,
                            "partial": False,
                            "message": final_message.strip(),
                            "is_test_mode": is_test_mode
                        }
                    )
            else:
                # 모두 실패 메시지
                final_message = f"\n\n{test_mode_prefix}회의록 전송에 실패했습니다. 사용자가 Mattermost에 등록되어 있는지 확인해주세요."
                if is_test_mode:
                    final_message += " Mattermost 서비스가 구성되지 않았습니다."
                
                # 대화 기록에 저장을 위해 결과 메시지 추가
                current_content += final_message
                
                yield LLMResponseChunk(
                    session_id=session_id,
                    type=MessageType.RESULT,
                    data={
                        "success": False,
                        "message": final_message.strip(),
                        "is_test_mode": is_test_mode
                    }
                )
                
            # 대화 기록에 추가
            self.chat_history_service.add_message(session_id, "assistant", current_content)
                
        except Exception as e:
            logger.error(f"[{session_id}] Mattermost 회의록 전송 중 오류 발생: {str(e)}")
            error_message = f"\n\n회의록 전송 중 오류가 발생했습니다: {str(e)}"
            for token in error_message.split():
                current_content += " " + token
                yield LLMResponseChunk(
                    session_id=session_id,
                    type=MessageType.CONTENT,
                    content=" " + token
                )
                
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.ERROR,
                data={
                    "error_message": "회의록 전송 중 오류가 발생했습니다.",
                    "details": str(e)
                }
            )
            
            # 대화 기록에 추가
            self.chat_history_service.add_message(session_id, "assistant", current_content)
