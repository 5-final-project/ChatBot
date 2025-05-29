"""
사용자 DB 서비스 모듈
사용자 정보 관련 데이터베이스 작업을 담당합니다.
"""
import logging
from typing import List, Dict, Any, Optional
import aiomysql
from app.services.db.db_core import pool

# 로깅 설정
logger = logging.getLogger(__name__)

async def get_users() -> List[Dict[str, Any]]:
    """
    모든 사용자 목록을 조회합니다.
    
    Returns:
        List[Dict[str, Any]]: 사용자 목록
    """
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute('''
                SELECT id, name, email, department, position, 
                       created_at, updated_at
                FROM users
                ORDER BY name ASC
                ''')
                users = await cursor.fetchall()
                return users
    except Exception as e:
        logger.error(f"사용자 목록 조회 중 오류: {str(e)}")
        return []

async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """
    ID로 사용자를 조회합니다.
    
    Args:
        user_id: 사용자 ID
        
    Returns:
        Optional[Dict[str, Any]]: 사용자 정보
    """
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute('''
                SELECT id, name, email, department, position, 
                       created_at, updated_at
                FROM users
                WHERE id = %s
                ''', (user_id,))
                user = await cursor.fetchone()
                return user
    except Exception as e:
        logger.error(f"사용자 조회(ID: {user_id}) 중 오류: {str(e)}")
        return None

async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    이메일로 사용자를 조회합니다.
    
    Args:
        email: 사용자 이메일
        
    Returns:
        Optional[Dict[str, Any]]: 사용자 정보
    """
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute('''
                SELECT id, name, email, department, position, 
                       created_at, updated_at
                FROM users
                WHERE email = %s
                ''', (email,))
                user = await cursor.fetchone()
                return user
    except Exception as e:
        logger.error(f"사용자 조회(이메일: {email}) 중 오류: {str(e)}")
        return None

async def create_user(name: str, email: str, department: Optional[str] = None, 
                     position: Optional[str] = None) -> Optional[int]:
    """
    새 사용자를 생성합니다.
    
    Args:
        name: 사용자 이름
        email: 이메일
        department: 부서
        position: 직급
        
    Returns:
        Optional[int]: 생성된 사용자 ID
    """
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 이미 존재하는지 확인
                await cursor.execute('''
                SELECT id FROM users WHERE email = %s
                ''', (email,))
                existing = await cursor.fetchone()
                
                if existing:
                    logger.warning(f"중복된 이메일로 사용자 생성 시도: {email}")
                    return existing['id']
                
                # 새 사용자 추가
                await cursor.execute('''
                INSERT INTO users (name, email, department, position)
                VALUES (%s, %s, %s, %s)
                ''', (name, email, department, position))
                
                # 생성된 ID 반환
                return cursor.lastrowid
    except Exception as e:
        logger.error(f"사용자 생성 중 오류({name}, {email}): {str(e)}")
        return None

async def update_user(user_id: int, name: Optional[str] = None, 
                     email: Optional[str] = None, department: Optional[str] = None, 
                     position: Optional[str] = None) -> bool:
    """
    사용자 정보를 업데이트합니다.
    
    Args:
        user_id: 사용자 ID
        name: 사용자 이름
        email: 이메일
        department: 부서
        position: 직급
        
    Returns:
        bool: 업데이트 성공 여부
    """
    try:
        # 업데이트할 필드 동적 생성
        update_fields = {}
        if name is not None:
            update_fields['name'] = name
        if email is not None:
            update_fields['email'] = email
        if department is not None:
            update_fields['department'] = department
        if position is not None:
            update_fields['position'] = position
            
        if not update_fields:
            logger.warning(f"업데이트할 필드가 없습니다: 사용자 ID {user_id}")
            return False
            
        # SQL 쿼리 동적 생성
        sql_parts = []
        values = []
        
        for field, value in update_fields.items():
            sql_parts.append(f"{field} = %s")
            values.append(value)
            
        # 사용자 ID 추가
        values.append(user_id)
        
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f'''
                UPDATE users
                SET {", ".join(sql_parts)}
                WHERE id = %s
                ''', tuple(values))
                
                return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"사용자 업데이트 중 오류(ID: {user_id}): {str(e)}")
        return False
