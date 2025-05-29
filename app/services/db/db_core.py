"""
DB 코어 모듈
데이터베이스 연결 및 초기화를 담당합니다.
"""
import os
import traceback
import logging
import aiomysql
from typing import Optional
from app.core.config import settings

# 로깅 설정 --- 명시적 설정 추가
logger = logging.getLogger(__name__)
# 핸들러 및 포매터 설정 (이미 main에서 basicConfig로 설정되어 있다면 중복될 수 있으나, 독립성 확보 차원)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.DEBUG) # 디버그 레벨로 설정하여 상세 로그 확인

pool: Optional[aiomysql.Pool] = None

async def connect_db() -> Optional[aiomysql.Pool]:
    global pool
    logger.debug(f"connect_db CALLED. Current global pool (db_core.pool) before trying: {pool}")

    # 설정값 로드 확인
    db_host = settings.DB_HOST
    db_port = settings.DB_PORT
    db_user = settings.DB_USER
    db_password = settings.DB_PASSWORD
    db_name = settings.DB_NAME
    logger.debug(f"DB Settings at connect_db entry: HOST={db_host}, PORT={db_port}, USER={db_user}, DB_NAME={db_name}, HAS_PASSWORD={'YES' if db_password else 'NO'}")

    if pool is None or pool._closed: 
        logger.info("DB connection pool is None or closed. Attempting to create a new pool.")
        try:
            if not all([db_host, db_user, db_password, db_name]):
                logger.error("CRITICAL: DATABASE CONFIGURATION IS INCOMPLETE. Check .env file or config settings. Cannot create pool.")
                pool = None
                return None

            logger.info(f"Attempting to connect to DB with config: Host={db_host}, Port={db_port}, User={db_user}, DB={db_name}")
            
            current_pool = await aiomysql.create_pool(
                host=db_host,
                port=int(db_port), 
                user=db_user,
                password=db_password,
                db=db_name,
                charset=settings.DB_CHARSET,
                cursorclass=aiomysql.DictCursor,
                autocommit=True,
            )
            pool = current_pool 
            logger.info(f"DB connection pool CREATED successfully: {pool}")
        except Exception as e:
            logger.error(f"Failed to create DB connection pool: {e}", exc_info=True)
            pool = None 
    else:
        logger.info(f"DB connection pool ALREADY EXISTS and is open: {pool}")
    
    return pool

async def get_db_pool() -> Optional[aiomysql.Pool]:
    """데이터베이스 연결 풀을 반환합니다. 풀이 초기화되지 않았으면 초기화를 시도합니다."""
    global pool
    if pool is None or pool._closed:
        logger.warning("get_db_pool: Pool is None or closed. Attempting to (re)connect.")
        await connect_db() 
    return pool

async def create_tables_if_not_exist():
    """
    필요한 테이블이 없으면 생성합니다.
    
    Returns:
        bool: 테이블 생성 성공 여부
    """
    db_pool = await get_db_pool()
    if db_pool is None:
        logger.error("데이터베이스 풀이 초기화되지 않았습니다.")
        return False
    
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 사용자 테이블 생성 확인
                await cursor.execute('''
                SHOW TABLES LIKE 'users';
                ''')
                user_table_exists = bool(await cursor.fetchone())
                
                if not user_table_exists:
                    # 사용자 테이블 생성
                    await cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL COMMENT '사용자 이름',
                        email VARCHAR(100) NOT NULL COMMENT '이메일',
                        department VARCHAR(100) COMMENT '부서',
                        position VARCHAR(100) COMMENT '직급',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        UNIQUE KEY unique_email (email)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='사용자 정보 테이블';
                    ''')
                
                # 회의 테이블 생성 확인
                await cursor.execute('''
                SHOW TABLES LIKE 'meetings';
                ''')
                meeting_table_exists = bool(await cursor.fetchone())
                
                if not meeting_table_exists:
                    # 회의 테이블 생성
                    await cursor.execute('''
                    CREATE TABLE IF NOT EXISTS meetings (
                        meeting_id VARCHAR(36) PRIMARY KEY COMMENT '회의 ID',
                        title VARCHAR(200) NOT NULL COMMENT '회의 제목',
                        meeting_date DATE NOT NULL COMMENT '회의 날짜',
                        duration_minutes INT DEFAULT 0 COMMENT '회의 시간 (분)',
                        minutes_file_path VARCHAR(500) COMMENT '회의록 파일 경로',
                        stt_text LONGTEXT COMMENT 'STT 변환 텍스트',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        status ENUM('draft', 'stt_processing', 'stt_completed', 'minutes_created', 'published') 
                            DEFAULT 'draft' COMMENT '회의 상태'
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='회의 정보 테이블';
                    ''')
                
                # 회의 참석자 테이블 생성
                await cursor.execute('''
                CREATE TABLE IF NOT EXISTS meeting_attendees (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    meeting_id VARCHAR(36) NOT NULL COMMENT '회의 ID',
                    user_id INT NOT NULL COMMENT '사용자 ID',
                    attendance_status ENUM('confirmed', 'declined', 'tentative', 'attended', 'absent') 
                        DEFAULT 'confirmed' COMMENT '참석 상태',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_meeting_attendee (meeting_id, user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='회의 참석자 테이블';
                ''')
                
                # Mattermost 사용자 매핑 테이블 생성
                await cursor.execute('''
                CREATE TABLE IF NOT EXISTS mattermost_user_mappings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL COMMENT '사용자 ID',
                    mattermost_user_id VARCHAR(100) NOT NULL COMMENT 'Mattermost 사용자 ID',
                    mattermost_username VARCHAR(100) COMMENT 'Mattermost 사용자명',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_user_id (user_id),
                    UNIQUE KEY unique_mattermost_id (mattermost_user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Mattermost 사용자 매핑 테이블';
                ''')
                
                logger.info("필요한 테이블 생성 완료")
                return True
    except Exception as e:
        logger.error(f"테이블 생성 중 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
        return False

async def init_db():
    """
    데이터베이스 연결 풀 초기화 및 테이블 생성을 수행합니다.
    
    Returns:
        bool: 초기화 성공 여부
    """
    try:
        db_pool = await connect_db()
        if db_pool:
            # 테이블 존재 여부 확인 및 생성
            tables_created = await create_tables_if_not_exist()
            if tables_created:
                logger.info("데이터베이스 초기화 완료")
                return True
            else:
                logger.error("테이블 생성 실패")
                return False
        return False
    except Exception as e:
        logger.error(f"데이터베이스 초기화 실패: {str(e)}")
        logger.error(traceback.format_exc())
        return False

async def close_db():
    global pool
    if pool and not pool._closed:
        logger.info(f"Closing DB connection pool: {pool}")
        pool.close()
        await pool.wait_closed()
        logger.info("DB connection pool closed successfully.")
        pool = None
    else:
        logger.info("DB connection pool is already None or closed. No action taken for close_db.")
