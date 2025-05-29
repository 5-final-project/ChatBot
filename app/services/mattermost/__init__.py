"""
Mattermost 서비스 모듈
Mattermost 통합에 필요한 다양한 서비스를 제공합니다.
"""
from app.services.mattermost.mattermost_core import mattermost_client
from app.services.mattermost.mattermost_message_service import MessageService
from app.services.mattermost.mattermost_file_service import FileService
from app.services.mattermost.mattermost_user_service import UserService
from app.services.mattermost.mattermost_manager import MattermostManager

# 싱글톤 인스턴스 생성 - 기존 mattermost_manager와 동일한 방식으로 접근 가능
mattermost_manager = MattermostManager()

__all__ = [
    'mattermost_client',
    'MessageService',
    'FileService', 
    'UserService',
    'MattermostManager',
    'mattermost_manager'
]
