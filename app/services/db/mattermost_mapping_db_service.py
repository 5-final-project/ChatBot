"""
Mattermost 사용자 매핑 DB 서비스 모듈
내부 사용자와 Mattermost 사용자 ID 간의 매핑을 관리합니다.
"""
import logging
from typing import List, Dict, Any, Optional
import aiomysql
from app.services.db.db_core import get_db_pool

# 로깅 설정
logger = logging.getLogger(__name__)

async def get_mattermost_mapping_by_user_id(user_id: int) -> Optional[Dict[str, Any]]:
    """
    내부 사용자 ID로 Mattermost 매핑 정보를 조회합니다.
    
    Args:
        user_id: 내부 사용자 ID
        
    Returns:
        Optional[Dict[str, Any]]: Mattermost 매핑 정보
    """
    db_pool = await get_db_pool()
    if not db_pool:
        logger.error(f"DB pool unavailable for get_mattermost_mapping_by_user_id (user_id: {user_id})")
        return None
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute('''
                SELECT id, user_id, mattermost_user_id, mattermost_username, 
                       created_at, updated_at
                FROM mattermost_user_mappings
                WHERE user_id = %s
                ''', (user_id,))
                mapping = await cursor.fetchone()
                return mapping
    except Exception as e:
        logger.error(f"Mattermost 매핑 조회 중 오류(사용자 ID: {user_id}): {str(e)}", exc_info=True)
        return None

async def get_mattermost_mapping_by_mattermost_id(mattermost_user_id: str) -> Optional[Dict[str, Any]]:
    """
    Mattermost 사용자 ID로 매핑 정보를 조회합니다.
    
    Args:
        mattermost_user_id: Mattermost 사용자 ID
        
    Returns:
        Optional[Dict[str, Any]]: Mattermost 매핑 정보
    """
    db_pool = await get_db_pool()
    if not db_pool:
        logger.error(f"DB pool unavailable for get_mattermost_mapping_by_mattermost_id (mattermost_id: {mattermost_user_id})")
        return None
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute('''
                SELECT m.id, m.user_id, m.mattermost_user_id, m.mattermost_username, 
                       m.created_at, m.updated_at,
                       u.name, u.email, u.department, u.position
                FROM mattermost_user_mappings m
                JOIN users u ON m.user_id = u.id
                WHERE m.mattermost_user_id = %s
                ''', (mattermost_user_id,))
                mapping = await cursor.fetchone()
                return mapping
    except Exception as e:
        logger.error(f"Mattermost 매핑 조회 중 오류(Mattermost ID: {mattermost_user_id}): {str(e)}", exc_info=True)
        return None

async def get_mattermost_mapping_by_username(mattermost_username: str) -> Optional[Dict[str, Any]]:
    """
    Mattermost 사용자명으로 매핑 정보를 조회합니다.
    
    Args:
        mattermost_username: Mattermost 사용자명
        
    Returns:
        Optional[Dict[str, Any]]: Mattermost 매핑 정보
    """
    db_pool = await get_db_pool()
    if not db_pool:
        logger.error(f"DB pool unavailable for get_mattermost_mapping_by_username (username: {mattermost_username})")
        return None
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute('''
                SELECT m.id, m.user_id, m.mattermost_user_id, m.mattermost_username, 
                       m.created_at, m.updated_at,
                       u.name, u.email, u.department, u.position
                FROM mattermost_user_mappings m
                JOIN users u ON m.user_id = u.id
                WHERE m.mattermost_username = %s
                ''', (mattermost_username,))
                mapping = await cursor.fetchone()
                return mapping
    except Exception as e:
        logger.error(f"Mattermost 매핑 조회 중 오류(사용자명: {mattermost_username}): {str(e)}", exc_info=True)
        return None

async def create_mattermost_mapping(user_id: int, mattermost_user_id: str, 
                                   mattermost_username: Optional[str] = None) -> bool:
    """
    새 Mattermost 사용자 매핑을 생성합니다.
    
    Args:
        user_id: 내부 사용자 ID
        mattermost_user_id: Mattermost 사용자 ID
        mattermost_username: Mattermost 사용자명
        
    Returns:
        bool: 생성 성공 여부
    """
    db_pool = await get_db_pool()
    if not db_pool:
        logger.error(f"DB pool unavailable for create_mattermost_mapping (user_id: {user_id})")
        return False
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 이미 존재하는지 확인
                await cursor.execute('''
                SELECT id FROM mattermost_user_mappings 
                WHERE user_id = %s OR mattermost_user_id = %s
                ''', (user_id, mattermost_user_id))
                
                existing = await cursor.fetchone()
                if existing:
                    logger.warning(f"중복된 Mattermost 매핑 생성 시도: 사용자 ID {user_id}, Mattermost ID {mattermost_user_id}")
                    return False
                
                # 새 매핑 추가
                await cursor.execute('''
                INSERT INTO mattermost_user_mappings 
                (user_id, mattermost_user_id, mattermost_username)
                VALUES (%s, %s, %s)
                ''', (user_id, mattermost_user_id, mattermost_username))
                
                return True
    except Exception as e:
        logger.error(f"Mattermost 매핑 생성 중 오류(사용자 ID: {user_id}): {str(e)}", exc_info=True)
        return False

async def update_mattermost_mapping(user_id: int, 
                                   mattermost_user_id: Optional[str] = None,
                                   mattermost_username: Optional[str] = None) -> bool:
    """
    Mattermost 사용자 매핑을 업데이트합니다.
    
    Args:
        user_id: 내부 사용자 ID
        mattermost_user_id: Mattermost 사용자 ID
        mattermost_username: Mattermost 사용자명
        
    Returns:
        bool: 업데이트 성공 여부
    """
    db_pool = await get_db_pool()
    if not db_pool:
        logger.error(f"DB pool unavailable for update_mattermost_mapping (user_id: {user_id})")
        return False
    try:
        # 업데이트할 필드 동적 생성
        update_fields = {}
        if mattermost_user_id is not None:
            update_fields['mattermost_user_id'] = mattermost_user_id
        if mattermost_username is not None:
            update_fields['mattermost_username'] = mattermost_username
            
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
        
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f'''
                UPDATE mattermost_user_mappings
                SET {", ".join(sql_parts)}
                WHERE user_id = %s
                ''', tuple(values))
                
                return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Mattermost 매핑 업데이트 중 오류(사용자 ID: {user_id}): {str(e)}", exc_info=True)
        return False

async def get_mattermost_user_ids_by_names(names: List[str]) -> Dict[str, str]:
    """
    이름 목록으로 Mattermost 사용자 ID를 조회합니다.
    
    Args:
        names: 사용자 이름 목록
        
    Returns:
        Dict[str, str]: {이름: Mattermost 사용자 ID} 형태의 매핑 딕셔너리
    """
    logger.debug(f"get_mattermost_user_ids_by_names called with names: {names}")
    if not names:
        return {}

    db_pool = await get_db_pool()
    if not db_pool:
        logger.error("DB pool unavailable for get_mattermost_user_ids_by_names. Returning empty dict.")
        # 모든 이름에 대해 찾을 수 없음으로 처리하고 반환 (또는 예외 발생)
        # 여기서는 빈 딕셔너리를 반환하여, 호출 측에서 일부 사용자를 찾지 못한 것으로 간주하도록 합니다.
        return {name: "<DB_ERROR>" for name in names} # 또는 빈 딕셔너리 {}

    results: Dict[str, str] = {}
    # 이름 목록을 적절한 크기로 분할하여 처리 (예: 100개씩)
    # 여기서는 간단하게 전체 목록을 한 번에 처리
    placeholders = ', '.join(['%s'] * len(names))
    sql = f'''
    SELECT CONCAT(last_name, first_name) as name, mattermost_user_id
    FROM mattermost_user_mappings
    WHERE CONCAT(last_name, first_name) IN ({placeholders})
    '''
    
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor: # DictCursor 사용 명시
                await cursor.execute(sql, tuple(names))
                rows = await cursor.fetchall()
                for row in rows:
                    results[row['name']] = row['mattermost_user_id']
                
                # 찾지 못한 이름에 대한 처리 (선택 사항)
                # for name in names:
                #     if name not in results:
                #         results[name] = "<NOT_FOUND>"

    except Exception as e:
        logger.error(f"Error fetching Mattermost user IDs by names: {e}", exc_info=True)
        # 오류 발생 시 모든 요청된 이름에 대해 오류 표시자 반환
        return {name: "<DB_QUERY_ERROR>" for name in names}

    logger.debug(f"Returning Mattermost user IDs: {results}")
    return results
