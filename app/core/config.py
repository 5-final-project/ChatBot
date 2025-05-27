# app/core/config.py: 애플리케이션 설정 관리
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

class Settings(BaseSettings):
    """
    애플리케이션 설정을 관리하는 클래스.
    .env 파일 또는 환경 변수에서 값을 로드합니다.
    """
    # Google Gemini API
    GOOGLE_API_KEY: str

    # Mattermost Configuration
    MATTERMOST_URL: Optional[str] = os.getenv("MATTERMOST_URL", "http://localhost:8065")
    MATTERMOST_BOT_TOKEN: Optional[str] = os.getenv("MATTERMOST_BOT_TOKEN")
    MATTERMOST_TEAM_ID: Optional[str] = os.getenv("MATTERMOST_TEAM_ID") # 필요시 팀 ID 추가

    # Database Configuration
    DB_TYPE: str
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    DB_CHARSET: str = "utf8mb4"
    DB_SSL_MODE: Optional[str] = None

    # Application Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Agentic Chatbot API"

    # 외부 RAG 서비스 URL
    EXTERNAL_RAG_SERVICE_URL: Optional[str] = os.getenv("EXTERNAL_RAG_SERVICE_URL", "https://wxy6ptclkd.ap") # 기본 URL 업데이트

    # 애플리케이션 디버깅 설정
    DEBUG: bool = False

    # .env 파일 경로 설정
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

# 설정 객체 인스턴스화
settings = Settings()
