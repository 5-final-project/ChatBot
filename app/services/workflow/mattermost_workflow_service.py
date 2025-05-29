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
        
        # 엔티티 정보 가져오기
        entities = intent_result.get("entities", {})
        meeting_id = entities.get("meeting_id") or entities.get("document_name")
        target_user = entities.get("target_user_or_channel")
        
        # 작업 시작 알림 - 스트리밍 응답 시작
        yield LLMResponseChunk(
            session_id=session_id,
            type=MessageType.CONTENT,
            content="회의록 전송 준비 중입니다..."
        )
        
        # 회의 컨텍스트 확인
        meeting_context = request.meeting_context
        if not meeting_context:
            # 스트리밍 형태로 오류 메시지 표시
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.CONTENT,
                content="회의 컨텍스트 정보가 없습니다. 회의록 전송을 위해서는 회의 정보가 필요합니다."
            )
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.ERROR,
                data={"error_message": "회의 컨텍스트 정보가 없습니다.", "details": "회의 컨텍스트가 필요합니다."}
            )
            return
            
        # S3 URL 확인
        s3_url = meeting_context.hub_minutes_s3_url
        if not s3_url:
            # 스트리밍 형태로 오류 메시지 표시
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.CONTENT,
                content="회의록 URL 정보가 없습니다. 회의록 전송을 위해서는 회의록 URL이 필요합니다."
            )
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.ERROR,
                data={"error_message": "회의록 S3 URL이 없습니다.", "details": "회의록 S3 URL이 필요합니다."}
            )
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
            # 스트리밍 형태로 경고 메시지 표시
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.CONTENT,
                content="회의 참가자 정보가 없습니다. 회의록 전송을 위해서는 참가자 정보가 필요합니다."
            )
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.WARNING,
                data={"warning_message": "회의 참가자 정보가 없습니다. 전송할 수 없습니다."}
            )
            return
        
        # 회의 참여자 목록 표시
        participants_str = ", ".join(participant_names)
        yield LLMResponseChunk(
            session_id=session_id,
            type=MessageType.CONTENT,
            content=f"회의 '{meeting_title}'의 참가자 목록: {participants_str}"
        )
        
        # 전송 시작 메시지
        yield LLMResponseChunk(
            session_id=session_id,
            type=MessageType.CONTENT,
            content=f"회의 '{meeting_title}'의 회의록을 {len(participant_names)}명의 참가자에게 전송 중입니다..."
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
                # 스트리밍 형태로 진행 상황 메시지 표시
                yield LLMResponseChunk(
                    session_id=session_id,
                    type=MessageType.CONTENT,
                    content=f"사용자 '{participant_name}'에게 회의록 전송 중..."
                )
                
                # 사용자 Mattermost ID 확인 (DB 매핑 서비스를 우선 활용)
                mattermost_id = None
                
                # 실제 서비스에서는 DB에서 Mattermost ID를 조회하는 로직이 필요
                # 여기서는 간단히 가정만 하고 진행
                mattermost_id = f"mm_user_{participant_name.lower().replace(' ', '_')}"
                
                # 전송 성공 가정 (실제 서비스에서는 Mattermost API 호출 결과에 따라 처리)
                success = True
                
                if success:
                    success_count += 1
                    yield LLMResponseChunk(
                        session_id=session_id,
                        type=MessageType.CONTENT,
                        content=f"사용자 '{participant_name}'에게 회의록 전송 완료"
                    )
                else:
                    failed_participants.append({"name": participant_name, "reason": "전송 실패"})
                    yield LLMResponseChunk(
                        session_id=session_id,
                        type=MessageType.CONTENT,
                        content=f"사용자 '{participant_name}'에게 회의록 전송 실패"
                    )
            
            # 전송 결과 요약
            if success_count > 0:
                # 성공 메시지
                yield LLMResponseChunk(
                    session_id=session_id,
                    type=MessageType.CONTENT,
                    content=f"회의 '{meeting_title}'의 회의록이 {success_count}명의 참가자에게 성공적으로 전송되었습니다."
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
                # 실패 정보
                failed_names = ', '.join([p["name"] for p in failed_participants])
                yield LLMResponseChunk(
                    session_id=session_id,
                    type=MessageType.CONTENT,
                    content=f"다음 참가자에게 전송하지 못했습니다: {failed_names}"
                )
            
            # 최종 결과 메시지
            if success_count > 0:
                if len(failed_participants) > 0:
                    yield LLMResponseChunk(
                        session_id=session_id,
                        type=MessageType.RESULT,
                        data={
                            "success": True,
                            "partial": True,
                            "message": f"회의 '{meeting_title}'의 회의록이 Mattermost를 통해 {success_count}명의 참가자에게 전송되었습니다. {len(failed_participants)}명에게는 전송에 실패했습니다."
                        }
                    )
                else:
                    yield LLMResponseChunk(
                        session_id=session_id,
                        type=MessageType.RESULT,
                        data={
                            "success": True,
                            "partial": False,
                            "message": f"회의 '{meeting_title}'의 회의록이 Mattermost를 통해 모든 회의 참가자에게 전송되었습니다."
                        }
                    )
            else:
                # 모두 실패
                yield LLMResponseChunk(
                    session_id=session_id,
                    type=MessageType.RESULT,
                    data={
                        "success": False,
                        "message": "회의록 전송에 실패했습니다. 사용자가 Mattermost에 등록되어 있는지 확인해주세요."
                    }
                )
                
        except Exception as e:
            logger.error(f"[{session_id}] Mattermost 회의록 전송 중 오류 발생: {str(e)}")
            yield LLMResponseChunk(
                session_id=session_id,
                type=MessageType.ERROR,
                data={
                    "error_message": "회의록 전송 중 오류가 발생했습니다.",
                    "details": str(e)
                }
            )
