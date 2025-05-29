"""
Mattermost 메시지 서비스
Mattermost 채널과 사용자에게 메시지를 전송하는 기능을 제공합니다.
"""
import logging
from typing import Optional, List, Dict, Any
import json
import traceback
from app.services.mattermost.mattermost_core import mattermost_client, api_session

logger = logging.getLogger(__name__)

class MessageService:
    """Mattermost 메시지 전송 기능을 제공하는 클래스"""
    
    def __init__(self):
        """메시지 서비스를 초기화합니다."""
        self.client = mattermost_client
        self.api = api_session
    
    def send_message_to_user(
        self, 
        message: str,
        user_id: Optional[str] = None, 
        file_ids: Optional[List[str]] = None,
        channel_id: Optional[str] = None 
    ) -> Dict[str, Any]:
        """
        Mattermost 사용자에게 개인 메시지(DM)를 전송합니다.
        
        Args:
            message (str): 전송할 메시지 내용
            user_id (str, optional): Mattermost 사용자 ID
            file_ids (List[str], optional): 첨부할 파일 ID 목록
            channel_id (str, optional): 기존 DM 채널 ID (제공되면 새 채널 생성 건너뜀)
            
        Returns:
            Dict[str, Any]: 전송 결과 및 관련 정보
        """
        result = {"success": False, "message": "", "data": {}}
        
        try:
            # 채널 ID가 없으면 DM 채널을 생성
            if not channel_id and user_id:
                try:
                    # 봇과 사용자 간의 DM 채널 생성
                    logger.info(f"Creating DM channel with user: {user_id}")
                    
                    if self.client:
                        # mattermostdriver를 사용하는 경우
                        try:
                            # API 메소드 변경: create_direct_channel -> create_direct_message_channel
                            # 올바른 payload 형식으로 변경
                            logger.info(f"Creating direct message channel with payload format 1")
                            # user_id 경우에 따라 다르게 호출
                            if user_id:
                                try:
                                    # 봇 ID 가져오기
                                    bot_info = self.client.users.get_user('me')
                                    bot_id = bot_info.get('id')
                                    
                                    if bot_id:
                                        # 올바른 형식으로 페이로드 전송
                                        channel_data = self.client.channels.create_direct_message_channel([bot_id, user_id])
                                        channel_id = channel_data.get('id')
                                    else:
                                        raise Exception("봇 ID를 가져오는데 실패했습니다.")
                                except Exception as e:
                                    logger.warning(f"Direct message channel creation failed with format 1: {str(e)}")
                                    raise
                            else:
                                raise ValueError("사용자 ID가 없습니다.")
                        except (AttributeError, Exception) as e:
                            logger.warning(f"Direct message channel error: {str(e)}")
                            
                            # 다른 API 메소드 시도 (API 버전에 따라 다를 수 있음)
                            try:
                                logger.info(f"Trying alternative API method for DM channel creation")
                                channel_data = self.client.channels.create_direct_channel(user_id)
                                channel_id = channel_data.get('id')
                            except AttributeError:
                                # 대체 방법: API 직접 호출
                                logger.warning(f"Using fallback API direct call for DM channel creation")
                                # 먼저 봇 ID 가져오기
                                bot_info = self.client.users.get_user('me')
                                bot_id = bot_info.get('id')
                                if not bot_id:
                                    raise Exception("봇 ID를 가져올 수 없습니다.")
                                    
                                # mattermostdriver 공식 문서에 따라 직접 HTTP API 호출 사용
                                try:
                                    import requests
                                    
                                    # API 연결 정보 사용
                                    if not hasattr(self, 'base_url'):
                                        # 한 번만 초기화
                                        from app.core.config import settings
                                        self.base_url = settings.MATTERMOST_URL
                                        self.token = settings.MATTERMOST_BOT_TOKEN
                                    
                                    # API 엔드포인트 URL 구성
                                    url = f"{self.base_url}/api/v4/channels/direct"
                                    
                                    # 헤더 설정
                                    headers = {
                                        'Authorization': f'Bearer {self.token}',
                                        'Content-Type': 'application/json'
                                    }
                                    
                                    # 요청 본문 - 사용자 ID 배열
                                    payload = json.dumps([bot_id, user_id])
                                    
                                    # POST 요청 실행
                                    logger.info(f"DM 채널 생성 요청: {url} - {bot_id}, {user_id}")
                                    response = requests.post(url, headers=headers, data=payload, verify=False)
                                    response.raise_for_status()
                                    
                                    # 응답에서 채널 ID 추출
                                    result = response.json()
                                    channel_id = result.get('id')
                                    logger.info(f"DM 채널이 성공적으로 생성됨: {channel_id}")
                                except Exception as e:
                                    logger.error(f"DM 채널 생성 실패 (직접 API 호출): {str(e)}")
                                    raise
                    else:
                        # 직접 API 호출을 사용하는 경우
                        session = self.api["session"]
                        base_url = self.api["base_url"]
                        url = f"{base_url}/api/v4/channels/direct"
                        
                        # 봇 ID 가져오기
                        bot_response = session.get(f"{base_url}/api/v4/users/me")
                        bot_id = bot_response.json().get('id')
                        
                        # DM 채널 생성 (2인 채널)
                        response = session.post(url, json=[bot_id, user_id])
                        if response.status_code < 400:
                            channel_data = response.json()
                            channel_id = channel_data.get('id')
                        else:
                            raise Exception(f"DM 채널 생성 실패: {response.status_code} - {response.text}")
                    
                    logger.info(f"DM channel created with ID: {channel_id}")
                except Exception as e:
                    error_msg = f"DM 채널 생성 실패: {str(e)}"
                    logger.error(error_msg)
                    logger.error(traceback.format_exc())
                    result["message"] = error_msg
                    return result
            
            if not channel_id:
                result["message"] = "메시지 전송 실패: 채널 ID 또는 사용자 ID가 필요합니다."
                return result
            
            # 메시지 전송
            message_data = {
                "channel_id": channel_id,
                "message": message
            }
            
            if file_ids:
                message_data["file_ids"] = file_ids
            
            if self.client:
                # mattermostdriver를 사용하는 경우
                post_result = self.client.posts.create_post(message_data)
                result["success"] = True
                result["data"] = post_result
            else:
                # 직접 API 호출을 사용하는 경우
                session = self.api["session"]
                base_url = self.api["base_url"]
                url = f"{base_url}/api/v4/posts"
                
                response = session.post(url, json=message_data)
                if response.status_code < 400:
                    result["success"] = True
                    result["data"] = response.json()
                else:
                    raise Exception(f"메시지 전송 실패: {response.status_code} - {response.text}")
            
            result["message"] = "메시지가 성공적으로 전송되었습니다."
            logger.info(f"Message sent to channel_id: {channel_id}")
            return result
            
        except Exception as e:
            error_msg = f"메시지 전송 중 오류 발생: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            result["message"] = error_msg
            return result
    
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
            # 메시지 데이터 준비
            message_data = {
                "channel_id": channel_id,
                "message": message
            }
            
            if file_ids:
                message_data["file_ids"] = file_ids
            
            if self.client:
                # mattermostdriver를 사용하는 경우
                post_result = self.client.posts.create_post(message_data)
                result["success"] = True
                result["data"] = post_result
            else:
                # 직접 API 호출을 사용하는 경우
                session = self.api["session"]
                base_url = self.api["base_url"]
                url = f"{base_url}/api/v4/posts"
                
                response = session.post(url, json=message_data)
                if response.status_code < 400:
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
