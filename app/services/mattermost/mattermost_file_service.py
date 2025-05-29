"""
Mattermost 파일 서비스
Mattermost에 파일을 업로드하고 관리하는 기능을 제공합니다.
"""
import os
import logging
from typing import Optional, Dict, Any
import traceback
from app.services.mattermost.mattermost_core import mattermost_client, api_session

logger = logging.getLogger(__name__)

class FileService:
    """Mattermost 파일 업로드 및 관리 기능을 제공하는 클래스"""
    
    def __init__(self):
        """파일 서비스를 초기화합니다."""
        self.client = mattermost_client
        self.api = api_session
    
    def upload_file(self, channel_id: str, file_path: str) -> Dict[str, Any]:
        """
        파일을 Mattermost 채널에 업로드합니다.
        
        Args:
            channel_id (str): 파일을 업로드할 채널 ID
            file_path (str): 업로드할 로컬 파일 경로
            
        Returns:
            Dict[str, Any]: 업로드 결과 및 파일 ID 정보
        """
        result = {"success": False, "message": "", "file_id": None}
        
        # 파일 존재 여부 확인
        if not os.path.exists(file_path):
            result["message"] = f"파일이 존재하지 않습니다: {file_path}"
            logger.error(result["message"])
            return result
        
        try:
            file_name = os.path.basename(file_path)
            
            if self.client:
                # mattermostdriver를 사용하는 경우
                with open(file_path, 'rb') as file:
                    file_upload_response = self.client.files.upload_file(
                        channel_id=channel_id,
                        files={'files': (file_name, file)}
                    )
                
                file_infos = file_upload_response.get('file_infos', [])
                if file_infos and len(file_infos) > 0:
                    file_id = file_infos[0].get('id')
                    result["success"] = True
                    result["file_id"] = file_id
                    result["message"] = f"파일이 성공적으로 업로드되었습니다. 파일 ID: {file_id}"
                    logger.info(f"File uploaded successfully to channel_id: {channel_id}, file_id: {file_id}")
                else:
                    result["message"] = "파일 업로드 응답에서 file_infos를 찾을 수 없습니다."
                    logger.error(result["message"])
            else:
                # 직접 API 호출을 사용하는 경우
                session = self.api["session"]
                base_url = self.api["base_url"]
                url = f"{base_url}/api/v4/files"
                
                with open(file_path, 'rb') as file:
                    # Content-Type 헤더 제거 (multipart/form-data로 자동 설정)
                    headers = session.headers.copy()
                    if 'Content-Type' in headers:
                        del headers['Content-Type']
                    
                    files = {
                        'files': (file_name, file),
                        'channel_id': (None, channel_id)
                    }
                    
                    response = session.post(url, headers=headers, files=files)
                    
                    if response.status_code < 400:
                        file_upload_data = response.json()
                        file_infos = file_upload_data.get('file_infos', [])
                        
                        if file_infos and len(file_infos) > 0:
                            file_id = file_infos[0].get('id')
                            result["success"] = True
                            result["file_id"] = file_id
                            result["message"] = f"파일이 성공적으로 업로드되었습니다. 파일 ID: {file_id}"
                            logger.info(f"File uploaded successfully to channel_id: {channel_id}, file_id: {file_id}")
                        else:
                            result["message"] = "파일 업로드 응답에서 file_infos를 찾을 수 없습니다."
                            logger.error(result["message"])
                    else:
                        raise Exception(f"파일 업로드 실패: {response.status_code} - {response.text}")
                
            return result
            
        except Exception as e:
            error_msg = f"파일 업로드 중 오류 발생: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            result["message"] = error_msg
            return result
    
    def upload_minutes_file(self, channel_id: str, minutes_pdf_path: str) -> Dict[str, Any]:
        """
        회의록 PDF 파일을 Mattermost 채널에 업로드합니다.
        
        Args:
            channel_id (str): 파일을 업로드할 채널 ID
            minutes_pdf_path (str): 업로드할 회의록 PDF 파일 경로
            
        Returns:
            Dict[str, Any]: 업로드 결과 및 파일 ID 정보
        """
        # 파일 확장자 확인
        if not minutes_pdf_path.lower().endswith('.pdf'):
            result = {
                "success": False,
                "message": "회의록 파일은 PDF 형식이어야 합니다.",
                "file_id": None
            }
            logger.warning(result["message"])
            return result
        
        # 파일 업로드 함수 호출
        return self.upload_file(channel_id, minutes_pdf_path)
