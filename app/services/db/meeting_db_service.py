"""
회의 DB 서비스 모듈
회의 정보 관련 데이터베이스 작업을 담당합니다.
"""
import logging
import uuid
from datetime import date
from typing import List, Dict, Any, Optional
import aiomysql
from app.services.db.db_core import pool

# 로깅 설정
logger = logging.getLogger(__name__)

async def get_meeting_by_id(meeting_id: str) -> Optional[Dict[str, Any]]:
    """
    회의 ID로 회의 정보를 조회합니다.
    
    Args:
        meeting_id: 회의 ID
        
    Returns:
        Optional[Dict[str, Any]]: 회의 정보
    """
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute('''
                SELECT meeting_id, title, meeting_date, duration_minutes, 
                       minutes_file_path, stt_text, created_at, 
                       updated_at, status
                FROM meetings
                WHERE meeting_id = %s
                ''', (meeting_id,))
                meeting = await cursor.fetchone()
                return meeting
    except Exception as e:
        logger.error(f"회의 조회 중 오류(ID: {meeting_id}): {str(e)}")
        return None

async def create_meeting(title: str, meeting_date: date, 
                        duration_minutes: int = 0,
                        status: str = 'draft') -> Optional[str]:
    """
    새 회의를 생성합니다.
    
    Args:
        title: 회의 제목
        meeting_date: 회의 날짜
        duration_minutes: 회의 시간(분)
        status: 회의 상태
        
    Returns:
        Optional[str]: 생성된 회의 ID
    """
    try:
        meeting_id = str(uuid.uuid4())
        
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute('''
                INSERT INTO meetings 
                (meeting_id, title, meeting_date, duration_minutes, status)
                VALUES (%s, %s, %s, %s, %s)
                ''', (meeting_id, title, meeting_date, duration_minutes, status))
                
                # 생성된 ID 반환
                return meeting_id
    except Exception as e:
        logger.error(f"회의 생성 중 오류({title}): {str(e)}")
        return None

async def update_meeting_minutes(meeting_id: str, 
                                minutes_file_path: Optional[str] = None,
                                stt_text: Optional[str] = None, 
                                status: Optional[str] = None) -> bool:
    """
    회의록 정보를 업데이트합니다.
    
    Args:
        meeting_id: 회의 ID
        minutes_file_path: 회의록 파일 경로
        stt_text: STT 변환 텍스트
        status: 회의 상태
        
    Returns:
        bool: 업데이트 성공 여부
    """
    try:
        # 업데이트할 필드 동적 생성
        update_fields = {}
        if minutes_file_path is not None:
            update_fields['minutes_file_path'] = minutes_file_path
        if stt_text is not None:
            update_fields['stt_text'] = stt_text
        if status is not None:
            update_fields['status'] = status
            
        if not update_fields:
            logger.warning(f"업데이트할 필드가 없습니다: 회의 ID {meeting_id}")
            return False
            
        # SQL 쿼리 동적 생성
        sql_parts = []
        values = []
        
        for field, value in update_fields.items():
            sql_parts.append(f"{field} = %s")
            values.append(value)
            
        # 회의 ID 추가
        values.append(meeting_id)
        
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f'''
                UPDATE meetings
                SET {", ".join(sql_parts)}
                WHERE meeting_id = %s
                ''', tuple(values))
                
                return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"회의록 업데이트 중 오류(ID: {meeting_id}): {str(e)}")
        return False

async def get_meeting_attendees(meeting_id: str) -> List[Dict[str, Any]]:
    """
    회의 참석자 목록을 조회합니다.
    
    Args:
        meeting_id: 회의 ID
        
    Returns:
        List[Dict[str, Any]]: 참석자 목록
    """
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute('''
                SELECT a.id, a.meeting_id, a.user_id, a.attendance_status,
                       u.name, u.email, u.department, u.position
                FROM meeting_attendees a
                JOIN users u ON a.user_id = u.id
                WHERE a.meeting_id = %s
                ORDER BY u.name ASC
                ''', (meeting_id,))
                attendees = await cursor.fetchall()
                return attendees
    except Exception as e:
        logger.error(f"회의 참석자 조회 중 오류(회의 ID: {meeting_id}): {str(e)}")
        return []

async def get_meeting_attendees_with_mattermost_ids(meeting_id: str) -> List[Dict[str, Any]]:
    """
    회의 참석자 목록을 Mattermost ID 정보와 함께 조회합니다.
    
    Args:
        meeting_id: 회의 ID
        
    Returns:
        List[Dict[str, Any]]: 참석자 및 Mattermost 정보
    """
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute('''
                SELECT a.id, a.meeting_id, a.user_id, a.attendance_status,
                       u.name, u.email, u.department, u.position,
                       m.mattermost_user_id, m.mattermost_username
                FROM meeting_attendees a
                JOIN users u ON a.user_id = u.id
                LEFT JOIN mattermost_user_mappings m ON u.id = m.user_id
                WHERE a.meeting_id = %s
                ORDER BY u.name ASC
                ''', (meeting_id,))
                attendees = await cursor.fetchall()
                return attendees
    except Exception as e:
        logger.error(f"회의 참석자 Mattermost 정보 조회 중 오류(회의 ID: {meeting_id}): {str(e)}")
        return []

async def add_meeting_attendee(meeting_id: str, user_id: int, 
                              attendance_status: str = 'confirmed') -> bool:
    """
    회의 참석자를 추가합니다.
    
    Args:
        meeting_id: 회의 ID
        user_id: 사용자 ID
        attendance_status: 참석 상태
        
    Returns:
        bool: 추가 성공 여부
    """
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 중복 확인
                await cursor.execute('''
                SELECT id FROM meeting_attendees
                WHERE meeting_id = %s AND user_id = %s
                ''', (meeting_id, user_id))
                
                existing = await cursor.fetchone()
                if existing:
                    # 상태 업데이트
                    await cursor.execute('''
                    UPDATE meeting_attendees
                    SET attendance_status = %s
                    WHERE meeting_id = %s AND user_id = %s
                    ''', (attendance_status, meeting_id, user_id))
                else:
                    # 새 참석자 추가
                    await cursor.execute('''
                    INSERT INTO meeting_attendees
                    (meeting_id, user_id, attendance_status)
                    VALUES (%s, %s, %s)
                    ''', (meeting_id, user_id, attendance_status))
                
                return True
    except Exception as e:
        logger.error(f"회의 참석자 추가 중 오류(회의 ID: {meeting_id}, 사용자 ID: {user_id}): {str(e)}")
        return False
