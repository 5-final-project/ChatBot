"""
테스트 데이터 서비스 모듈
개발 및 테스트를 위한 샘플 데이터를 제공합니다.
"""
import logging
import datetime
from typing import List, Dict, Any, Tuple
from app.services.db.db_core import pool
from app.services.db.user_db_service import create_user, get_users
from app.services.db.meeting_db_service import create_meeting, add_meeting_attendee
from app.services.db.mattermost_mapping_db_service import create_mattermost_mapping

# 로깅 설정
logger = logging.getLogger(__name__)

async def add_test_data() -> bool:
    """
    테스트용 샘플 데이터를 추가합니다.
    
    Returns:
        bool: 데이터 추가 성공 여부
    """
    try:
        # 1. 테스트 사용자 추가
        test_users = [
            {
                'name': '김영희',
                'email': 'yhkim@example.com',
                'department': '개발팀',
                'position': '선임개발자'
            },
            {
                'name': '이철수',
                'email': 'cslee@example.com',
                'department': '기획팀',
                'position': '팀장'
            },
            {
                'name': '박지민',
                'email': 'jmpark@example.com',
                'department': '디자인팀',
                'position': '디자이너'
            },
            {
                'name': '우리피사',
                'email': 'woorifisa5001@gmail.com',
                'department': 'AI팀',
                'position': '연구원'
            }
        ]
        
        user_ids = []
        for user in test_users:
            user_id = await create_user(
                name=user['name'],
                email=user['email'],
                department=user['department'],
                position=user['position']
            )
            if user_id:
                user_ids.append(user_id)
                logger.info(f"테스트 사용자 추가됨: {user['name']} (ID: {user_id})")
                
        if not user_ids:
            logger.error("테스트 사용자 추가 실패")
            return False
            
        # 2. Mattermost 사용자 매핑 추가
        # 우리피사 사용자를 실제 Mattermost 테스트 계정과 매핑
        woorifisa_user_id = None
        users = await get_users()
        for user in users:
            if user['email'] == 'woorifisa5001@gmail.com':
                woorifisa_user_id = user['id']
                break
                
        if woorifisa_user_id:
            # 실제 Mattermost 테스트 계정 ID 사용
            mattermost_test_id = "abasd123456789"  # 실제 ID로 교체 필요
            mapping_success = await create_mattermost_mapping(
                user_id=woorifisa_user_id,
                mattermost_user_id=mattermost_test_id,
                mattermost_username="woorifisa1"
            )
            
            if mapping_success:
                logger.info(f"테스트 Mattermost 매핑 추가됨: 우리피사 -> {mattermost_test_id}")
            else:
                logger.warning("테스트 Mattermost 매핑 추가 실패")
        
        # 3. 테스트 회의 추가
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        tomorrow = today + datetime.timedelta(days=1)
        
        test_meetings = [
            {
                'title': '프로젝트 킥오프 미팅',
                'date': yesterday,
                'duration': 60,
                'status': 'minutes_created'
            },
            {
                'title': '주간 개발 회의',
                'date': today,
                'duration': 30,
                'status': 'draft'
            },
            {
                'title': '디자인 검토 회의',
                'date': tomorrow,
                'duration': 45,
                'status': 'draft'
            }
        ]
        
        meeting_ids = []
        for meeting in test_meetings:
            meeting_id = await create_meeting(
                title=meeting['title'],
                meeting_date=meeting['date'],
                duration_minutes=meeting['duration'],
                status=meeting['status']
            )
            
            if meeting_id:
                meeting_ids.append(meeting_id)
                logger.info(f"테스트 회의 추가됨: {meeting['title']} (ID: {meeting_id})")
                
                # 회의 참석자 추가
                for user_id in user_ids:
                    await add_meeting_attendee(
                        meeting_id=meeting_id,
                        user_id=user_id,
                        attendance_status='confirmed'
                    )
        
        if not meeting_ids:
            logger.error("테스트 회의 추가 실패")
            return False
            
        logger.info("테스트 데이터 추가 완료")
        return True
    except Exception as e:
        logger.error(f"테스트 데이터 추가 중 오류 발생: {str(e)}")
        return False

async def test_db_functions() -> Tuple[bool, List[str]]:
    """
    데이터베이스 함수가 정상적으로 동작하는지 테스트합니다.
    
    Returns:
        Tuple[bool, List[str]]: 테스트 성공 여부와 결과 메시지 목록
    """
    results = []
    success = True
    
    try:
        # 1. 사용자 조회 테스트
        users = await get_users()
        if users:
            results.append(f"사용자 조회 성공: {len(users)}명의 사용자 조회됨")
        else:
            results.append("사용자 조회 실패 또는 사용자가 없음")
            success = False
            
        # Mattermost 사용자 매핑 테스트는 생략 (실제 매핑이 없을 수 있음)
        
        # 기타 테스트는 필요에 따라 추가
        
        return success, results
    except Exception as e:
        logger.error(f"DB 테스트 중 오류 발생: {str(e)}")
        return False, [f"테스트 중 오류 발생: {str(e)}"]
