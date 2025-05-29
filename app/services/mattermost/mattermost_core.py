"""
Mattermost 코어 모듈
Mattermost API와의 기본 연결 설정 및 클라이언트 생성을 담당합니다.
"""
import os
import json
import traceback
import logging
import socket
from urllib.parse import urlparse
import requests
from requests.exceptions import RequestException
from mattermostdriver import Driver
from app.core.config import settings

# 로깅 설정
logger = logging.getLogger(__name__)

# Mattermost 설정 정보
MATTERMOST_URL = settings.MATTERMOST_URL
MATTERMOST_TOKEN = settings.MATTERMOST_BOT_TOKEN

# URL 파싱 및 연결 설정
def parse_mattermost_url():
    """Mattermost URL을 파싱하여 연결 정보를 추출합니다."""
    try:
        parsed_url = urlparse(MATTERMOST_URL)
        
        scheme = parsed_url.scheme
        netloc = parsed_url.netloc
        
        # 도메인이 비어있는지 확인 (스키마만 있는 경우 등)
        if not netloc and parsed_url.path:
            netloc = parsed_url.path  # path에 도메인이 들어간 경우
            logger.info(f"Using path as netloc: {netloc}")
        
        # 포트가 있는지 확인
        if ':' in netloc:
            hostname, port_str = netloc.split(':')
            port = int(port_str)
        else:
            hostname = netloc
            port = 443 if scheme == 'https' else 80
            
        return {
            'scheme': scheme,
            'hostname': hostname,
            'port': port,
            'base_url': f"{scheme}://{hostname}:{port}"
        }
    except Exception as e:
        logger.error(f"Mattermost URL 파싱 오류: {e}")
        return None

# 연결 테스트 함수
def test_mattermost_connection():
    """Mattermost 서버 연결 및 인증을 테스트합니다."""
    connection_info = parse_mattermost_url()
    if not connection_info:
        return {"success": False, "message": "URL 파싱 실패"}
    
    hostname = connection_info['hostname']
    scheme = connection_info['scheme']
    port = connection_info['port']
    base_url = connection_info['base_url']
    
    test_results = {
        "dns_resolution": {"success": False, "message": ""},
        "server_connection": {"success": False, "message": ""},
        "api_token": {"success": False, "message": ""},
        "overall": {"success": False, "message": ""}
    }
    
    # 1. DNS 해석 테스트
    try:
        logger.info(f"Testing DNS resolution for: {hostname}")
        socket.gethostbyname(hostname)
        test_results["dns_resolution"] = {"success": True, "message": f"DNS resolution successful for: {hostname}"}
    except socket.gaierror as e:
        error_msg = f"DNS resolution failed for {hostname}: {e}"
        logger.error(error_msg)
        test_results["dns_resolution"] = {"success": False, "message": error_msg}
        test_results["overall"] = {"success": False, "message": "DNS resolution failed"}
        return test_results
    
    # 2. 서버 연결 테스트
    try:
        test_url = f"{base_url}/api/v4/system/ping"
        logger.info(f"Testing server connection: {test_url}")
        response = requests.get(test_url, verify=False, timeout=5)
        test_results["server_connection"] = {
            "success": response.status_code < 400,
            "message": f"Server response: {response.status_code} - {response.text[:100]}"
        }
        if response.status_code >= 400:
            test_results["overall"] = {"success": False, "message": "Server connection failed"}
            return test_results
    except RequestException as e:
        error_msg = f"Server connection test failed: {e}"
        logger.error(error_msg)
        test_results["server_connection"] = {"success": False, "message": error_msg}
        test_results["overall"] = {"success": False, "message": "Server connection failed"}
        return test_results
    
    # 3. API 토큰 테스트
    try:
        auth_test_url = f"{base_url}/api/v4/users/me"
        headers = {"Authorization": f"Bearer {MATTERMOST_TOKEN}"}
        logger.info(f"Testing API token with direct request...")
        auth_response = requests.get(auth_test_url, headers=headers, verify=False, timeout=5)
        
        if auth_response.status_code == 200:
            user_data = auth_response.json()
            test_results["api_token"] = {
                "success": True,
                "message": f"Successfully authenticated as: {user_data.get('username', 'Unknown')}"
            }
        else:
            error_msg = f"API token test failed: HTTP {auth_response.status_code}"
            logger.error(error_msg)
            test_results["api_token"] = {"success": False, "message": error_msg}
            test_results["overall"] = {"success": False, "message": "API token authentication failed"}
            return test_results
    except Exception as e:
        error_msg = f"API token test error: {e}"
        logger.error(error_msg)
        test_results["api_token"] = {"success": False, "message": error_msg}
        test_results["overall"] = {"success": False, "message": "API token test error"}
        return test_results
    
    # 모든 테스트 통과
    test_results["overall"] = {"success": True, "message": "All Mattermost connection tests passed"}
    return test_results

# Mattermost 클라이언트 초기화
def initialize_mattermost_client():
    """Mattermost API 클라이언트를 초기화하고 반환합니다."""
    connection_info = parse_mattermost_url()
    if not connection_info:
        logger.error("Mattermost 클라이언트 초기화 실패: URL 파싱 오류")
        return None
    
    hostname = connection_info['hostname']
    scheme = connection_info['scheme']
    port = connection_info['port']
    
    # Driver 옵션 설정
    driver_options = {
        'url': hostname,
        'token': MATTERMOST_TOKEN,
        'scheme': scheme,
        'port': port,
        'verify': False,  # 개발 환경에서는 SSL 검증 비활성화
        'timeout': 30  # 타임아웃 값 증가
    }
    
    logger.info(f"Initializing Mattermost driver with: {scheme}://{hostname}:{port}")
    
    try:
        client = Driver(options=driver_options)
        client.login()
        logger.info("Mattermost driver login successful")
        return client
    except Exception as e:
        logger.error(f"Mattermost driver login failed: {e}")
        logger.error(traceback.format_exc())
        return None

# 초기화 시도
mattermost_client = initialize_mattermost_client()

# 기본 세션 객체 (직접 API 호출용)
def create_api_session():
    """직접 API 호출을 위한 세션 객체를 생성합니다."""
    connection_info = parse_mattermost_url()
    if not connection_info:
        return None
    
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "Authorization": f"Bearer {MATTERMOST_TOKEN}",
        "Content-Type": "application/json"
    })
    
    return {
        "session": session,
        "base_url": connection_info['base_url']
    }

# API 세션 생성
api_session = create_api_session()
