"""
워크플로우 서비스 모듈
애플리케이션의 핵심 워크플로우를 관리하는 서비스를 제공합니다.
"""
from app.services.workflow.workflow_core import WorkflowCore
from app.services.workflow.qna_workflow_service import QnAWorkflowService
from app.services.workflow.mattermost_workflow_service import MattermostWorkflowService
from app.services.workflow.session_service import SessionService
from app.services.workflow.workflow_manager import WorkflowManager

# 싱글톤 인스턴스 생성 - 기존 workflow_manager와 동일한 방식으로 접근 가능
workflow_manager = WorkflowManager()

__all__ = [
    'WorkflowCore',
    'QnAWorkflowService',
    'MattermostWorkflowService',
    'SessionService',
    'WorkflowManager',
    'workflow_manager'
]
