"""
Mattermost 관리자 서비스
Mattermost 관련 모든 서비스를 통합 관리하는 클래스를 제공합니다.
"""
import logging
from typing import Optional, List, Dict, Any
from app.services.mattermost.mattermost_message_service import MessageService
from app.services.mattermost.mattermost_file_service import FileService
from app.services.mattermost.mattermost_user_service import UserService

logger = logging.getLogger(__name__)

class MattermostManager:
    """Mattermost 관련 모든 서비스를 통합 관리하는 클래스"""
    
    _instance = None
    
    def __new__(cls):
        """싱글톤 패턴 구현"""
        if cls._instance is None:
            cls._instance = super(MattermostManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Mattermost 서비스를 초기화합니다."""
        if self._initialized:
            return
        
        logger.info("MattermostManager 초기화 중...")
        self.message_service = MessageService()
        self.file_service = FileService()
        self.user_service = UserService()
        self._initialized = True
        logger.info("MattermostManager 초기화 완료")
    
    # 메시지 서비스 기능
    def send_message_to_user(self, user_id, message, file_ids=None, channel_id=None):
        """사용자에게 메시지 전송"""
        return self.message_service.send_message_to_user(
            message=message,
            user_id=user_id,
            file_ids=file_ids,
            channel_id=channel_id
        )
    
    def send_message_to_channel(self, channel_id, message, file_ids=None):
        """채널에 메시지 전송"""
        return self.message_service.send_message_to_channel(
            channel_id=channel_id,
            message=message,
            file_ids=file_ids
        )
    
    # 파일 서비스 기능
    def upload_file(self, channel_id, file_path):
        """파일 업로드"""
        return self.file_service.upload_file(
            channel_id=channel_id,
            file_path=file_path
        )
    
    # 사용자 서비스 기능
    def find_mattermost_user_id(self, username):
        """사용자 이름으로 ID 찾기"""
        return self.user_service.find_user_id_by_username(username)
    
    def find_channel_id_by_name(self, channel_name, team_id=None):
        """채널 이름으로 ID 찾기"""
        return self.user_service.find_channel_id_by_name(
            channel_name=channel_name,
            team_id=team_id
        )
    
    def list_mattermost_users(self):
        """사용자 목록 조회"""
        return self.user_service.list_users()
    
    # 회의록 전송 기능
    def send_meeting_minutes_to_participants(self, meeting_id, participants, user_message=None, channel_id=None):
        """
        회의 참여자들에게 회의록을 전송합니다.
        
        Args:
            meeting_id (str): 회의 ID
            participants (List[Dict]): 참여자 정보 목록
            user_message (str, optional): 추가 메시지
            channel_id (str, optional): 특정 채널 ID
            
        Returns:
            Dict[str, Any]: 전송 결과 정보
        """
        results = {
            "success": False,
            "message": "",
            "details": {
                "total_participants": len(participants),
                "success_count": 0,
                "failed_count": 0,
                "failed_details": []
            }
        }
        
        if not participants:
            results["message"] = "전송할 참여자가 없습니다."
            logger.warning(results["message"])
            return results
        
        # 미구현 상태 (실제 회의록 전송 기능 구현 필요)
        # TODO: 회의록 파일 경로 가져오기, 참여자별 전송 등 구현
        results["message"] = "회의록 전송 기능이 아직 구현되지 않았습니다."
        logger.warning(results["message"])
        return results
    
    def send_minutes_to_user(self, user_id, minutes_pdf_path, meeting_title):
        """
        회의록 PDF를 특정 사용자에게 전송합니다.
        
        Args:
            user_id (str): Mattermost 사용자 ID
            minutes_pdf_path (str): 회의록 PDF 파일 경로
            meeting_title (str): 회의 제목
            
        Returns:
            Dict[str, Any]: 전송 결과 정보
        """
        # 1. 임시 DM 채널 생성
        channel_result = self.message_service.send_message_to_user(
            message="회의록 파일을 전송 준비 중입니다...",
            user_id=user_id
        )
        
        if not channel_result["success"]:
            return {
                "success": False,
                "message": f"DM 채널 생성 실패: {channel_result['message']}",
                "details": channel_result
            }
        
        channel_id = channel_result["data"].get("channel_id") or channel_result["data"].get("id")
        
        # 2. 파일 업로드
        file_result = self.file_service.upload_file(
            channel_id=channel_id,
            file_path=minutes_pdf_path
        )
        
        if not file_result["success"]:
            return {
                "success": False,
                "message": f"파일 업로드 실패: {file_result['message']}",
                "details": file_result
            }
        
        file_id = file_result["file_id"]
        
        # 3. 회의록 메시지 전송
        message = f"📝 **{meeting_title}** 회의록을 공유합니다.\n\n"
        message += "회의 내용을 확인하시고 피드백이나 질문이 있으시면 알려주세요."
        
        send_result = self.message_service.send_message_to_user(
            message=message,
            user_id=user_id,
            file_ids=[file_id],
            channel_id=channel_id
        )
        
        if not send_result["success"]:
            return {
                "success": False,
                "message": f"메시지 전송 실패: {send_result['message']}",
                "details": {
                    "channel": channel_result,
                    "file": file_result,
                    "message": send_result
                }
            }
        
        return {
            "success": True,
            "message": f"회의록이 성공적으로 전송되었습니다: {meeting_title}",
            "details": {
                "channel_id": channel_id,
                "file_id": file_id,
                "user_id": user_id
            }
        }


# MattermostManager의 싱글톤 인스턴스 생성
mattermost_manager = MattermostManager()
