from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Generator, Optional

from app.core.config import settings
# 주요 서비스 모듈만 가져오기
from app.services.visualization.visualization_service import VisualizationService
from app.services.workflow.workflow_manager import workflow_manager

# 기존 의존성 함수들...
# ... existing code ...

def get_visualization_service() -> VisualizationService:
    """
    시각화 서비스 인스턴스를 제공하는 의존성 함수입니다.
    chat.py의 기존 기능에서 사용합니다.
    """
    return VisualizationService()

def get_workflow_manager():
    """
    워크플로우 매니저 인스턴스를 제공하는 의존성 함수입니다.
    chat.py의 기존 기능에서 사용합니다.
    """
    return workflow_manager 