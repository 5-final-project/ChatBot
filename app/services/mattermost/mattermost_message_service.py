"""
Mattermost 메시지 서비스
Mattermost 채널과 사용자에게 메시지를 전송하는 기능을 제공합니다.
"""
import logging
import json
from typing import Optional, List, Dict, Any
import traceback
import requests
from app.services.mattermost.mattermost_core import mattermost_client, api_session, initialize_mattermost_client, MATTERMOST_URL, MATTERMOST_TOKEN

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # DEBUG 레벨로 설정

# 사용자 ID와 채널 ID 매핑 테이블
USER_CHANNEL_MAPPING = {
    # 사용자ID: 채널ID 매핑
    "hsk3kfeg1fbhprzha8y5fjznt": "wubqb3dh13fbieskw8mp6mjwqr",  # 김경훈
    "zep68zadnfnfba9jzwit4btj": "4drb8h34oif6ucpfj6upjik9or",  # 김다희
    "qrfanemf7yo7dq8jui8yorc1y": "5rptt34petncbc7u9x77ocipqy",  # 박재우
    "374deoeaw3butxr4mybebxpgga": "ntanqift4tdsbkn6jmo7frkkyo",  # 윤웅상
    "5qffg6wq33bgfn7uszgm6bfbo": "t3x11ds4gfb3ue1if6mda1einh",  # 오상우
}

# 기본 채널 ID (Town Square 등)
DEFAULT_CHANNEL_ID = "town-square"

class MessageService:
    """Mattermost 메시지 전송 기능을 제공하는 클래스"""
    
    def __init__(self, test_mode=False):
        """
        메시지 서비스를 초기화합니다.
        
        Args:
            test_mode (bool): 테스트 모드 여부. True이면 실제 API 호출 없이 성공 응답 반환
        """
        self.client = mattermost_client
        self.api = api_session
        self.test_mode = test_mode
    
    def send_message_to_user(
        self, 
        message: str,
        user_id: Optional[str] = None, 
        file_ids: Optional[List[str]] = None,
        channel_id: Optional[str] = None 
    ) -> Dict[str, Any]:
        """
        Mattermost 사용자에게 메시지를 전송합니다.
        
        Args:
            message (str): 전송할 메시지 내용
            user_id (str, optional): Mattermost 사용자 ID
            file_ids (List[str], optional): 첨부할 파일 ID 목록
            channel_id (str, optional): 기존 채널 ID (제공되면 채널 조회 건너뜀)
            
        Returns:
            Dict[str, Any]: 전송 결과 및 관련 정보
        """
        result = {"success": False, "message": "", "data": {}}
        
        try:
            if self.test_mode:
                result["success"] = True
                result["message"] = "테스트 모드: 메시지가 성공적으로 전송된 것으로 처리됨"
                return result
                
            # 채널 ID가 없으면 매핑 테이블에서 조회
            if not channel_id and user_id:
                channel_id = self._create_or_get_direct_message_channel(user_id)
                
                if not channel_id:
                    result["message"] = "채널 ID 조회 실패"
                    return result
            
            if not channel_id:
                result["message"] = "메시지 전송 실패: 채널 ID 또는 사용자 ID가 필요합니다."
                logger.error(result["message"])
                return result
            
            # 사용자 멘션 추가 (필요한 경우)
            if user_id and DEFAULT_CHANNEL_ID == channel_id:
                # 공용 채널일 경우 멘션 추가
                if not message.startswith(f"@"):
                    message = f"@{user_id} {message}"
            
            # 메시지 전송
            message_data = {
                "channel_id": channel_id,
                "message": message
            }
            
            if file_ids:
                message_data["file_ids"] = file_ids
            
            if self.client:
                # mattermostdriver를 사용하는 경우
                post_result = self.client.posts.create_post(options=message_data)
                result["success"] = True
                result["data"] = post_result
            else:
                # 직접 API 호출을 사용하는 경우
                post_url = f"{MATTERMOST_URL}/api/v4/posts"
                headers = {
                    'Authorization': f'Bearer {MATTERMOST_TOKEN}',
                    'Content-Type': 'application/json'
                }
                
                response_post = requests.post(
                    post_url, 
                    headers=headers, 
                    data=json.dumps(message_data), 
                    verify=False
                )
                
                if response_post.status_code in [200, 201]:
                    result["success"] = True
                    result["data"] = response_post.json()
                else:
                    raise Exception(f"메시지 전송 실패: {response_post.status_code} - {response_post.text}")
            
            result["message"] = "메시지가 성공적으로 전송되었습니다."
            logger.info(f"Message sent to channel_id: {channel_id}")
            return result
            
        except Exception as e:
            error_msg = f"메시지 전송 중 오류 발생: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            result["message"] = error_msg
            return result
            
    def _create_or_get_direct_message_channel(self, user_id: str) -> Optional[str]:
        """
        봇과 사용자 간의 DM 채널을 가져옵니다.
        
        Args:
            user_id (str): 대화할 사용자의 Mattermost ID
            
        Returns:
            Optional[str]: 채널 ID 또는 None (실패 시)
        """
        try:
            logger.info(f"Getting DM channel for user: {user_id}")
            
            # 매핑 테이블에서 채널 ID 확인
            if user_id in USER_CHANNEL_MAPPING:
                channel_id = USER_CHANNEL_MAPPING[user_id]
                logger.info(f"Found channel ID in mapping table: {channel_id}")
                return channel_id
            
            # 매핑 테이블에 없는 경우, 오류 로그 출력 후 None 반환
            logger.error(f"사용자 ID {user_id}에 대한 매핑된 채널을 찾을 수 없습니다.")
            return None
                
        except Exception as e:
            logger.error(f"채널 ID 조회 중 오류 발생: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    def send_message_to_channel(
        self, 
        channel_id: str, 
        message: str, 
        file_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        지정된 Mattermost 채널에 메시지를 전송합니다.
        
        Args:
            channel_id (str): Mattermost 채널 ID
            message (str): 전송할 메시지 내용
            file_ids (List[str], optional): 첨부할 파일 ID 목록
            
        Returns:
            Dict[str, Any]: 전송 결과 및 관련 정보
        """
        result = {"success": False, "message": "", "data": {}}
        
        try:
            if self.test_mode:
                result["success"] = True
                result["message"] = "테스트 모드: 메시지가 성공적으로 전송된 것으로 처리됨"
                return result
                
            # 메시지 데이터 준비
            message_data = {
                "channel_id": channel_id,
                "message": message
            }
            
            if file_ids:
                message_data["file_ids"] = file_ids
            
            if self.client:
                # mattermostdriver를 사용하는 경우
                post_result = self.client.posts.create_post(options=message_data)
                result["success"] = True
                result["data"] = post_result
            else:
                # 직접 API 호출을 사용하는 경우
                post_url = f"{MATTERMOST_URL}/api/v4/posts"
                headers = {
                    'Authorization': f'Bearer {MATTERMOST_TOKEN}',
                    'Content-Type': 'application/json'
                }
                
                response = requests.post(
                    post_url, 
                    headers=headers, 
                    data=json.dumps(message_data), 
                    verify=False
                )
                
                if response.status_code in [200, 201]:
                    result["success"] = True
                    result["data"] = response.json()
                else:
                    raise Exception(f"메시지 전송 실패: {response.status_code} - {response.text}")
            
            result["message"] = "메시지가 성공적으로 전송되었습니다."
            logger.info(f"Message sent to channel_id: {channel_id}")
            return result
            
        except Exception as e:
            error_msg = f"채널 메시지 전송 중 오류 발생: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            result["message"] = error_msg
            return result
    
    def send_minutes_to_user(
        self, 
        user_id: str, 
        minutes_file_id: str, 
        meeting_title: str
    ) -> Dict[str, Any]:
        """
        회의록 파일을 특정 사용자에게 전송합니다.
        
        Args:
            user_id (str): Mattermost 사용자 ID
            minutes_file_id (str): 첨부할 회의록 파일 ID
            meeting_title (str): 회의 제목
            
        Returns:
            Dict[str, Any]: 전송 결과 및 관련 정보
        """
        # 회의록 전송 메시지 생성
        message = f"📝 **{meeting_title}** 회의록을 공유합니다.\n\n"
        message += "회의 내용을 확인하시고 피드백이나 질문이 있으시면 알려주세요."
        
        # 첨부 파일 ID 목록
        file_ids = [minutes_file_id] if minutes_file_id else []
        
        # 메시지 전송
        return self.send_message_to_user(
            message=message,
            user_id=user_id,
            file_ids=file_ids
        )
