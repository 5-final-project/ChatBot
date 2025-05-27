# app/services/db_service.py: SQL 데이터베이스 연결 및 쿼리 기능 제공
import os
import traceback
from typing import List, Dict, Any, Optional, Tuple
import asyncio
import aiomysql
from app.core.config import settings
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 데이터베이스 연결 설정
DB_CONFIG = {
    'host': settings.DB_HOST,
    'port': settings.DB_PORT,
    'user': settings.DB_USER,
    'password': settings.DB_PASSWORD,
    'db': settings.DB_NAME,
    'charset': settings.DB_CHARSET,
    'cursorclass': aiomysql.DictCursor,
    'autocommit': True,
}

# SSL 모드 설정 추가 (DISABLED인 경우)
if hasattr(settings, 'DB_SSL_MODE') and settings.DB_SSL_MODE == 'DISABLED':
    logger.info("SSL 모드가 비활성화되었습니다.")
    DB_CONFIG['ssl'] = None

# 연결 풀
pool = None

async def connect_db():
    """데이터베이스 연결 풀 초기화 (테이블 생성 없이)"""
    global pool
    try:
        pool = await aiomysql.create_pool(**DB_CONFIG)
        logger.info(f"데이터베이스 연결 풀 생성 성공: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
        return True
    except Exception as e:
        logger.error(f"데이터베이스 연결 실패: {str(e)}")
        logger.error(traceback.format_exc())
        return False

async def init_db():
    """데이터베이스 연결 풀 초기화 및 테이블 생성"""
    global pool
    try:
        success = await connect_db()
        if success:
            # 테이블 존재 여부 확인 및 생성
            await create_tables_if_not_exist()
            return True
        return False
    except Exception as e:
        logger.error(f"데이터베이스 초기화 실패: {str(e)}")
        logger.error(traceback.format_exc())
        return False

async def close_db():
    """데이터베이스 연결 풀 종료"""
    global pool
    if pool:
        pool.close()
        await pool.wait_closed()
        logger.info("데이터베이스 연결 풀 종료")

async def create_tables_if_not_exist():
    """필요한 테이블이 없으면 생성"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            # 기존 테이블 구조를 확인하고 추가 테이블만 생성
            
            # 1. 회의 참석자 테이블 생성 (외래 키는 meetings의 meeting_id를 참조)
            await cursor.execute('''
            CREATE TABLE IF NOT EXISTS meeting_attendees (
                id INT AUTO_INCREMENT PRIMARY KEY,
                meeting_id VARCHAR(36) NOT NULL COMMENT '회의 ID',
                user_id INT NOT NULL COMMENT '사용자 ID',
                attendance_status ENUM('confirmed', 'declined', 'tentative', 'attended', 'absent') DEFAULT 'confirmed' COMMENT '참석 상태',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE KEY unique_meeting_attendee (meeting_id, user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='회의 참석자 테이블';
            ''')
            
            # 2. Mattermost 사용자 매핑 테이블 생성
            await cursor.execute('''
            CREATE TABLE IF NOT EXISTS mattermost_user_mappings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL COMMENT '사용자 ID',
                mattermost_user_id VARCHAR(100) NOT NULL COMMENT 'Mattermost 사용자 ID',
                mattermost_username VARCHAR(100) COMMENT 'Mattermost 사용자명',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE KEY unique_user_id (user_id),
                UNIQUE KEY unique_mattermost_id (mattermost_user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Mattermost 사용자 매핑 테이블';
            ''')
            
            logger.info("필요한 테이블 생성 완료")

# 사용자 관련 함수들
async def get_users(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """모든 사용자 조회"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM users ORDER BY id LIMIT %s OFFSET %s", 
                (limit, offset)
            )
            return await cursor.fetchall()

async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """ID로 사용자 조회"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            return await cursor.fetchone()

async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """이메일로 사용자 조회"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            return await cursor.fetchone()

async def create_user(name: str, email: str, department: str = None, position: str = None) -> int:
    """새 사용자 생성"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO users (name, email, department, position) VALUES (%s, %s, %s, %s)",
                (name, email, department, position)
            )
            return cursor.lastrowid

async def update_user(user_id: int, name: str = None, email: str = None, 
                      department: str = None, position: str = None) -> bool:
    """사용자 정보 업데이트"""
    update_fields = []
    params = []
    
    if name:
        update_fields.append("name = %s")
        params.append(name)
    if email:
        update_fields.append("email = %s")
        params.append(email)
    if department:
        update_fields.append("department = %s")
        params.append(department)
    if position:
        update_fields.append("position = %s")
        params.append(position)
        
    if not update_fields:
        return False
    
    params.append(user_id)
    query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
    
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(query, params)
            return cursor.rowcount > 0

# Mattermost 사용자 매핑 관련 함수들
async def get_mattermost_mapping_by_user_id(user_id: int) -> Optional[Dict[str, Any]]:
    """사용자 ID로 Mattermost 매핑 정보 조회"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM mattermost_user_mappings WHERE user_id = %s", 
                (user_id,)
            )
            return await cursor.fetchone()

async def get_mattermost_mapping_by_mattermost_id(mattermost_user_id: str) -> Optional[Dict[str, Any]]:
    """Mattermost 사용자 ID로 매핑 정보 조회"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM mattermost_user_mappings WHERE mattermost_user_id = %s", 
                (mattermost_user_id,)
            )
            return await cursor.fetchone()

async def get_mattermost_mapping_by_username(mattermost_username: str) -> Optional[Dict[str, Any]]:
    """Mattermost 사용자명으로 매핑 정보 조회"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM mattermost_user_mappings WHERE mattermost_username = %s", 
                (mattermost_username,)
            )
            return await cursor.fetchone()

async def get_mattermost_user_ids_by_names(names: List[str]) -> Dict[str, Optional[str]]:
    """
    주어진 "성이름" 형식의 이름 목록을 기반으로 Mattermost 사용자 ID를 조회합니다.
    mattermost_user_mappings 테이블의 first_name과 last_name을 사용합니다.
    주의: 이 함수는 mattermost_user_mappings 테이블에 first_name, last_name 컬럼이 존재하고,
          mattermost_user_id 컬럼이 있음을 가정합니다 (사용자 제공 이미지 기반).
          db_service.py 내 DDL과 실제 DB 스키마가 일치하는지 확인이 필요합니다.
    """
    if not pool:
        logger.error("데이터베이스 연결 풀이 초기화되지 않았습니다.")
        return {name: None for name in names}

    results: Dict[str, Optional[str]] = {}
    logger.info(f"Mattermost 사용자 ID 조회 시작 (이름 목록: {names})")
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            for full_name in names:
                if not full_name or len(full_name) < 2: # 기본적인 이름 형식 검사 (최소 성1 + 이름1 = 2글자)
                    logger.warning(f"'{full_name}'은(는) 유효한 이름 형식이 아니거나 너무 짧습니다. 건너뜁니다.")
                    results[full_name] = None
                    continue

                # "성이름" 형식으로 가정하고 파싱 (예: "홍길동" -> 성:"홍", 이름:"길동")
                # 2글자 성씨 (예: 남궁, 황보)는 정확히 파싱되지 않을 수 있음
                last_name = full_name[0]
                first_name = full_name[1:]
                
                query = """
                    SELECT mattermost_user_id 
                    FROM mattermost_user_mappings 
                    WHERE first_name = %s AND last_name = %s
                """
                try:
                    await cursor.execute(query, (first_name, last_name))
                    record = await cursor.fetchone()
                    if record and 'mattermost_user_id' in record:
                        results[full_name] = record['mattermost_user_id']
                        logger.info(f"조회 성공: '{full_name}' -> Mattermost ID: {record['mattermost_user_id']}")
                    else:
                        results[full_name] = None
                        logger.warning(f"Mattermost ID를 찾을 수 없음: first_name='{first_name}', last_name='{last_name}' (원본 이름: '{full_name}')")
                except Exception as e:
                    logger.error(f"'{full_name}' (파싱된 이름: {first_name} {last_name})에 대한 Mattermost ID 조회 중 오류 발생: {e}", exc_info=True)
                    results[full_name] = None
    logger.info(f"Mattermost 사용자 ID 조회 완료 (결과: {results})")
    return results

async def create_mattermost_mapping(user_id: int, mattermost_user_id: str, 
                                   mattermost_username: str = None) -> int:
    """새로운 Mattermost 사용자 매핑 생성"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                """INSERT INTO mattermost_user_mappings 
                   (user_id, mattermost_user_id, mattermost_username) 
                   VALUES (%s, %s, %s)""",
                (user_id, mattermost_user_id, mattermost_username)
            )
            return cursor.lastrowid

async def update_mattermost_mapping(user_id: int, mattermost_user_id: str = None, 
                                   mattermost_username: str = None) -> bool:
    """Mattermost 사용자 매핑 정보 업데이트"""
    update_fields = []
    params = []
    
    if mattermost_user_id:
        update_fields.append("mattermost_user_id = %s")
        params.append(mattermost_user_id)
    if mattermost_username:
        update_fields.append("mattermost_username = %s")
        params.append(mattermost_username)
        
    if not update_fields:
        return False
    
    params.append(user_id)
    query = f"UPDATE mattermost_user_mappings SET {', '.join(update_fields)} WHERE user_id = %s"
    
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(query, params)
            return cursor.rowcount > 0

# 회의 관련 함수들
async def get_meeting_by_id(meeting_id: str):
    """ID로 회의 정보 조회 (외부 DB의 meetings 테이블은 meeting_id가 기본키)"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM meetings WHERE meeting_id = %s", (meeting_id,))
            return await cursor.fetchone()

async def create_meeting(title: str, meeting_date: str, duration_minutes: int = 0, stt_text: str = None, status: str = 'stt_completed') -> str:
    """새 회의 생성 (외부 DB 테이블 구조에 맞춤)"""
    import uuid
    
    # meeting_id가 없으면 UUID 생성
    meeting_id = str(uuid.uuid4())
        
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
            INSERT INTO meetings (meeting_id, title, meeting_date, duration_minutes, stt_text, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            """, (meeting_id, title, meeting_date, duration_minutes, stt_text, status))
            return meeting_id

async def update_meeting_minutes(meeting_id: str, minutes_file_path: str) -> bool:
    """회의록 파일 경로 업데이트"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE meetings SET document_file_path = %s WHERE meeting_id = %s",
                (minutes_file_path, meeting_id)
            )
            return cursor.rowcount > 0

# 회의 참석자 관련 함수들
async def add_meeting_attendee(meeting_id: str, user_id: int, 
                              status: str = 'confirmed') -> bool:
    """회의 참석자 추가 (meeting_id는 varchar(36))"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            try:
                await cursor.execute(
                    """INSERT INTO meeting_attendees (meeting_id, user_id, attendance_status) 
                       VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE attendance_status = %s""",
                    (meeting_id, user_id, status, status)
                )
                return True
            except Exception as e:
                logger.error(f"회의 참석자 추가 실패: {str(e)}")
                return False

async def get_meeting_attendees(meeting_id: str) -> List[Dict[str, Any]]:
    """회의 참석자 목록 조회"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT ma.*, u.name, u.email, u.department, u.position 
                FROM meeting_attendees ma
                JOIN users u ON ma.user_id = u.id
                WHERE ma.meeting_id = %s
                ORDER BY u.name
            """, (meeting_id,))
            return await cursor.fetchall()

async def get_meeting_attendees_with_mattermost_ids(meeting_id: str) -> List[Dict[str, Any]]:
    """회의 참석자 목록과 Mattermost ID 함께 조회 (meeting_id는 varchar(36))"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
            SELECT ma.*, u.name, u.email, mm.mattermost_user_id, mm.mattermost_username
            FROM meeting_attendees ma
            JOIN users u ON ma.user_id = u.id
            LEFT JOIN mattermost_user_mappings mm ON u.id = mm.user_id
            WHERE ma.meeting_id = %s
            """, (meeting_id,))
            return await cursor.fetchall()

# 회의록 전송 관련 유틸리티 함수
async def get_mattermost_ids_for_meeting_attendees(meeting_id: str) -> List[str]:
    """회의 참석자들의 Mattermost ID 목록 조회"""
    attendees_with_mattermost = await get_meeting_attendees_with_mattermost_ids(meeting_id)
    mattermost_ids = []
    
    for attendee in attendees_with_mattermost:
        if attendee.get('mattermost_user_id'):
            mattermost_ids.append(attendee['mattermost_user_id'])
    
    return mattermost_ids

# 테스트 데이터 추가 함수
async def add_test_data():
    """테스트용 데이터 추가"""
    try:
        # 사용자 추가
        user1_id = await create_user("홍길동", "hong@example.com", "개발팀", "팀장")
        user2_id = await create_user("김철수", "kim@example.com", "개발팀", "개발자")
        user3_id = await create_user("이영희", "lee@example.com", "기획팀", "기획자")
        user4_id = await create_user("Woorifisa Test1", "woorifisa5001@gmail.com", "교육팀", "교육생")
        user5_id = await create_user("Woorifisa Test2", "woorifisa5002@gmail.com", "교육팀", "교육생")
        
        # Mattermost 사용자 매핑 추가
        await create_mattermost_mapping(user1_id, "mattermost_id_1", "hong")
        await create_mattermost_mapping(user2_id, "mattermost_id_2", "kim")
        await create_mattermost_mapping(user3_id, "mattermost_id_3", "lee")
        await create_mattermost_mapping(user4_id, "4yfoj4jk9jdtugpem41exrx58h", "woorifisa1")
        await create_mattermost_mapping(user5_id, "api1pkkzwpnjxnqfc5pheimw4h", "woorifisa2")
        
        # 회의 추가
        meeting1_id = await create_meeting(
            title="주간 팀 회의", 
            meeting_date="2025-05-24 10:00:00", 
            duration_minutes=60, # 임의의 회의 시간 (분)
            stt_text="주간 업무 보고 및 계획 논의. 회의 장소: 회의실 A", # 회의 요약 및 장소를 stt_text에 포함
            # status는 기본값 'stt_completed' 사용
        )
        
        # 회의 참석자 추가
        await add_meeting_attendee(meeting1_id, user1_id, "confirmed")
        await add_meeting_attendee(meeting1_id, user2_id, "confirmed")
        await add_meeting_attendee(meeting1_id, user3_id, "confirmed")
        await add_meeting_attendee(meeting1_id, user4_id, "confirmed")
        await add_meeting_attendee(meeting1_id, user5_id, "confirmed")
        
        logger.info("테스트 데이터 추가 완료")
        return True
    except Exception as e:
        logger.error(f"테스트 데이터 추가 실패: {str(e)}")
        logger.error(traceback.format_exc())
        return False

# 기능 테스트 함수
async def test_db_functions():
    """DB 함수 테스트"""
    try:
        # 사용자 조회
        users = await get_users(limit=10)
        logger.info(f"사용자 수: {len(users)}")
        
        # Mattermost ID로 사용자 매핑 조회
        mapping = await get_mattermost_mapping_by_mattermost_id("4yfoj4jk9jdtugpem41exrx58h")
        if mapping:
            user = await get_user_by_id(mapping['user_id'])
            logger.info(f"Mattermost ID '4yfoj4jk9jdtugpem41exrx58h'에 매핑된 사용자: {user['name']} ({user['email']})")
        
        # 회의 참석자 Mattermost ID 조회
        meeting_id = 1  # 첫 번째 회의 ID
        mattermost_ids = await get_mattermost_ids_for_meeting_attendees(meeting_id)
        logger.info(f"회의 ID {meeting_id}의 참석자 Mattermost ID: {mattermost_ids}")
        
        return True
    except Exception as e:
        logger.error(f"DB 함수 테스트 실패: {str(e)}")
        logger.error(traceback.format_exc())
        return False

# 초기화 함수 (애플리케이션 시작 시 호출)
async def initialize():
    """DB 초기화 및 테스트 데이터 추가"""
    success = await init_db()
    if success:
        # 테스트 데이터 추가 (필요한 경우 주석 해제)
        # await add_test_data()
        # await test_db_functions()
        pass
    return success
