"""
데이터베이스 서비스 모듈
SQL 데이터베이스 연결 및 쿼리 기능을 제공합니다.
"""
from app.services.db.db_core import connect_db, close_db, init_db, pool
from app.services.db.user_db_service import get_users, get_user_by_id, get_user_by_email, create_user, update_user
from app.services.db.meeting_db_service import (
    get_meeting_by_id, create_meeting, update_meeting_minutes,
    get_meeting_attendees, get_meeting_attendees_with_mattermost_ids
)
from app.services.db.mattermost_mapping_db_service import (
    get_mattermost_mapping_by_user_id, get_mattermost_mapping_by_mattermost_id,
    get_mattermost_mapping_by_username, create_mattermost_mapping,
    update_mattermost_mapping, get_mattermost_user_ids_by_names
)
from app.services.db.test_data_service import add_test_data, test_db_functions

# 초기화 함수
async def initialize():
    """DB 초기화 및 테스트 데이터 추가"""
    return await init_db()

__all__ = [
    'connect_db', 'close_db', 'init_db', 'pool', 'initialize',
    'get_users', 'get_user_by_id', 'get_user_by_email', 'create_user', 'update_user',
    'get_meeting_by_id', 'create_meeting', 'update_meeting_minutes',
    'get_meeting_attendees', 'get_meeting_attendees_with_mattermost_ids',
    'get_mattermost_mapping_by_user_id', 'get_mattermost_mapping_by_mattermost_id',
    'get_mattermost_mapping_by_username', 'create_mattermost_mapping',
    'update_mattermost_mapping', 'get_mattermost_user_ids_by_names',
    'add_test_data', 'test_db_functions'
]
