"""
Mattermost 사용자 서비스
Mattermost 사용자 및 채널 관련 기능을 제공합니다.
"""
import logging
from typing import Optional, List, Dict, Any
import traceback
from app.services.mattermost.mattermost_core import mattermost_client, api_session

logger = logging.getLogger(__name__)

class UserService:
    """Mattermost 사용자 및 채널 관련 기능을 제공하는 클래스"""
    
    def __init__(self):
        """사용자 서비스를 초기화합니다."""
        self.client = mattermost_client
        self.api = api_session
    
    def find_user_id_by_username(self, username: str) -> Dict[str, Any]:
        """
        Mattermost 사용자 이름으로 사용자 ID를 찾습니다.
        
        Args:
            username (str): Mattermost 사용자명 (@ 기호 포함 가능)
            
        Returns:
            Dict[str, Any]: 검색 결과 및 사용자 ID 정보
        """
        result = {"success": False, "message": "", "user_id": None, "username": None}
        
        # @ 기호 제거
        if username.startswith('@'):
            username = username[1:]
        
        try:
            if self.client:
                # mattermostdriver를 사용하는 경우
                users = self.client.users.get_users_by_usernames([username])
                if users and len(users) > 0:
                    user_id = users[0].get('id')
                    found_username = users[0].get('username')
                    result["success"] = True
                    result["user_id"] = user_id
                    result["username"] = found_username
                    result["message"] = f"사용자 찾기 성공: {username} -> {user_id}"
                    logger.info(f"User found: {username} -> {user_id}")
                else:
                    result["message"] = f"사용자를 찾을 수 없습니다: {username}"
                    logger.warning(result["message"])
            else:
                # 직접 API 호출을 사용하는 경우
                session = self.api["session"]
                base_url = self.api["base_url"]
                url = f"{base_url}/api/v4/users/usernames"
                
                response = session.post(url, json=[username])
                if response.status_code < 400:
                    users = response.json()
                    if users and len(users) > 0:
                        user_id = users[0].get('id')
                        found_username = users[0].get('username')
                        result["success"] = True
                        result["user_id"] = user_id
                        result["username"] = found_username
                        result["message"] = f"사용자 찾기 성공: {username} -> {user_id}"
                        logger.info(f"User found: {username} -> {user_id}")
                    else:
                        result["message"] = f"사용자를 찾을 수 없습니다: {username}"
                        logger.warning(result["message"])
                else:
                    result["message"] = f"사용자 검색 API 호출 실패: {response.status_code} - {response.text}"
                    logger.error(result["message"])
            
            return result
            
        except Exception as e:
            error_msg = f"사용자 검색 중 오류 발생: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            result["message"] = error_msg
            return result
    
    def find_channel_id_by_name(
        self, 
        channel_name: str, 
        team_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mattermost 채널 이름으로 채널 ID를 찾습니다.
        
        Args:
            channel_name (str): Mattermost 채널 이름 (URL 친화적인 이름)
            team_id (str, optional): 채널이 속한 팀 ID
            
        Returns:
            Dict[str, Any]: 검색 결과 및 채널 ID 정보
        """
        result = {"success": False, "message": "", "channel_id": None, "display_name": None}
        
        try:
            # 팀 ID가 제공되지 않은 경우, 봇이 속한 모든 팀을 검색
            if not team_id and self.client:
                # 내 팀 목록 가져오기
                try:
                    my_teams = self.client.teams.get_user_teams('me')
                except Exception as e:
                    logger.error(f"내 팀 목록 가져오기 실패: {e}")
                    my_teams = []
                
                # 모든 팀에서 채널 검색
                for team in my_teams:
                    team_id = team.get('id')
                    try:
                        if self.client:
                            # mattermostdriver를 사용하는 경우
                            channels = self.client.channels.get_channels_for_user('me', team_id)
                            for channel in channels:
                                if channel.get('name') == channel_name:
                                    channel_id = channel.get('id')
                                    display_name = channel.get('display_name')
                                    result["success"] = True
                                    result["channel_id"] = channel_id
                                    result["display_name"] = display_name
                                    result["message"] = f"채널 찾기 성공: {channel_name} -> {channel_id} (팀: {team.get('name')})"
                                    logger.info(f"Channel found: {channel_name} -> {channel_id} (Team: {team.get('name')})")
                                    return result
                    except Exception as e:
                        logger.error(f"팀 {team.get('name')} 채널 검색 중 오류: {e}")
                        continue
                
                result["message"] = f"모든 팀에서 채널을 찾을 수 없습니다: {channel_name}"
                logger.warning(result["message"])
                return result
            
            # 특정 팀에서 채널 검색
            if team_id:
                if self.client:
                    # mattermostdriver를 사용하는 경우
                    channels = self.client.channels.get_channels_for_user('me', team_id)
                    for channel in channels:
                        if channel.get('name') == channel_name:
                            channel_id = channel.get('id')
                            display_name = channel.get('display_name')
                            result["success"] = True
                            result["channel_id"] = channel_id
                            result["display_name"] = display_name
                            result["message"] = f"채널 찾기 성공: {channel_name} -> {channel_id}"
                            logger.info(f"Channel found: {channel_name} -> {channel_id}")
                            return result
                else:
                    # 직접 API 호출을 사용하는 경우
                    session = self.api["session"]
                    base_url = self.api["base_url"]
                    url = f"{base_url}/api/v4/users/me/teams/{team_id}/channels"
                    
                    response = session.get(url)
                    if response.status_code < 400:
                        channels = response.json()
                        for channel in channels:
                            if channel.get('name') == channel_name:
                                channel_id = channel.get('id')
                                display_name = channel.get('display_name')
                                result["success"] = True
                                result["channel_id"] = channel_id
                                result["display_name"] = display_name
                                result["message"] = f"채널 찾기 성공: {channel_name} -> {channel_id}"
                                logger.info(f"Channel found: {channel_name} -> {channel_id}")
                                return result
                    else:
                        result["message"] = f"채널 검색 API 호출 실패: {response.status_code} - {response.text}"
                        logger.error(result["message"])
                        return result
            
            result["message"] = f"채널을 찾을 수 없습니다: {channel_name}"
            logger.warning(result["message"])
            return result
            
        except Exception as e:
            error_msg = f"채널 검색 중 오류 발생: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            result["message"] = error_msg
            return result
    
    def list_users(self, limit: int = 100) -> Dict[str, Any]:
        """
        Mattermost 사용자 목록을 가져옵니다.
        
        Args:
            limit (int): 가져올 최대 사용자 수
            
        Returns:
            Dict[str, Any]: 사용자 목록 정보
        """
        result = {"success": False, "message": "", "users": []}
        
        try:
            if self.client:
                # mattermostdriver를 사용하는 경우
                users = self.client.users.get_users(params={"per_page": limit})
                result["success"] = True
                result["users"] = users
                result["message"] = f"사용자 목록 가져오기 성공 ({len(users)} 명)"
                logger.info(f"User list retrieved: {len(users)} users")
            else:
                # 직접 API 호출을 사용하는 경우
                session = self.api["session"]
                base_url = self.api["base_url"]
                url = f"{base_url}/api/v4/users?per_page={limit}"
                
                response = session.get(url)
                if response.status_code < 400:
                    users = response.json()
                    result["success"] = True
                    result["users"] = users
                    result["message"] = f"사용자 목록 가져오기 성공 ({len(users)} 명)"
                    logger.info(f"User list retrieved: {len(users)} users")
                else:
                    result["message"] = f"사용자 목록 API 호출 실패: {response.status_code} - {response.text}"
                    logger.error(result["message"])
            
            return result
            
        except Exception as e:
            error_msg = f"사용자 목록 가져오기 중 오류 발생: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            result["message"] = error_msg
            return result
