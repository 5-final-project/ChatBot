# app/services/mattermost_service.py: Mattermost API와의 상호작용을 담당하는 서비스
from mattermostdriver import Driver
from app.core.config import settings
from typing import Optional, List, Dict, Any
import os
import json
import traceback
import logging

logger = logging.getLogger(__name__)

# Mattermost 드라이버 초기화
try:
    import socket
    from urllib.parse import urlparse
    import requests
    from requests.exceptions import RequestException
    
    # Mattermost URL 설정 - 환경 변수에서 가져오기
    # 하드코딩 값 제거하고 설정에서 로드
    mattermost_url = settings.MATTERMOST_URL
    print(f"Mattermost URL from settings: {mattermost_url}")
    
    # 토큰 정보 확인 (비밀번호는 일부만 표시)
    token = settings.MATTERMOST_BOT_TOKEN
    print(f"Using Mattermost token: {token[:5]}...{token[-5:]} (length: {len(token)})")
    
    # URL 구분 분석
    parsed_url = urlparse(mattermost_url)
    
    scheme = parsed_url.scheme
    netloc = parsed_url.netloc
    
    # 도메인이 비어있는지 확인 (스키마만 있는 경우 등)
    if not netloc and parsed_url.path:
        netloc = parsed_url.path  # path에 도메인이 들어간 경우
        print(f"Using path as netloc: {netloc}")
    
    # 포트가 있는지 확인
    if ':' in netloc:
        hostname, port_str = netloc.split(':')
        port = int(port_str)
    else:
        hostname = netloc
        port = 443 if scheme == 'https' else 80
    
    # 네트워크 연결 테스트 - 도메인 해석 가능 확인
    try:
        print(f"Testing DNS resolution for: {hostname}")
        socket.gethostbyname(hostname)
        print(f"DNS resolution successful for: {hostname}")
        
        # 서버 연결 테스트
        test_url = f"{scheme}://{hostname}:{port}/api/v4/system/ping"
        print(f"Testing server connection: {test_url}")
        response = requests.get(test_url, verify=False, timeout=5)
        print(f"Server response: {response.status_code} - {response.text[:100]}")
        
        # 인증 테스트 - 추가
        auth_test_url = f"{scheme}://{hostname}:{port}/api/v4/users/me"
        headers = {"Authorization": f"Bearer {token}"}
        print(f"Testing API token with direct request...")
        auth_response = requests.get(auth_test_url, headers=headers, verify=False, timeout=5)
        print(f"Auth test response: {auth_response.status_code}")
        
        if auth_response.status_code == 200:
            user_data = auth_response.json()
            print(f"Successfully authenticated as: {user_data.get('username', 'Unknown')}")
        else:
            print(f"API token test failed: HTTP {auth_response.status_code} - {auth_response.text[:200]}")
    except socket.gaierror as e:
        print(f"DNS resolution failed for {hostname}: {e}")
    except RequestException as e:
        print(f"Server connection test failed: {e}")
    except Exception as e:
        print(f"General connection test error: {e}")
        print(traceback.format_exc())
    
    print(f"Initializing Mattermost driver with: {scheme}://{hostname}:{port}")
    
    # Driver 옵션 설정
    driver_options = {
        'url': f"{hostname}",
        'token': token,
        'scheme': scheme,
        'port': port,
        'verify': False,  # 개발 환경에서는 SSL 검증 비활성화
        'timeout': 30  # 타임아웃 값 증가
    }
    
    print(f"Driver options: {json.dumps({k: v if k != 'token' else f'{v[:5]}...{v[-5:]}' for k, v in driver_options.items()}, indent=2)}")
    
    # 대체 인증 방식 사용 시도
    use_alternative_auth = True
    mm = None
    mattermost_configured = False
    
    if not use_alternative_auth:
        try:
            mm = Driver(options=driver_options)
            print("Attempting to login via mattermostdriver...")
            mm.login()
            print("Login successful!")
            mattermost_configured = True
        except Exception as e:
            print(f"Login failed via mattermostdriver: {e}")
            print(traceback.format_exc())
            mm = None
            mattermost_configured = False
    
    # 대체 인증 방식 (직접 API 호출)
    if use_alternative_auth or not mattermost_configured:
        try:
            print("Using alternative direct API method...")
            
            # 대체 MM 객체 생성 (API만 사용)
            class SimpleMattermostAPI:
                def __init__(self, base_url, token):
                    self.base_url = base_url
                    self.headers = {"Authorization": f"Bearer {token}"}
                    self.session = requests.Session()
                    self.session.verify = False
                    
                def make_request(self, method, endpoint, data=None, files=None):
                    url = f"{self.base_url}/api/v4/{endpoint.lstrip('/')}"
                    print(f"API Request: {method} {url}")
                    if data:
                        print(f"Request data: {data}")
                    
                    try:
                        # 특별한 경우 처리: 직접 메시지 채널 생성
                        if endpoint == '/channels/direct':
                            # Mattermost API는 채널 생성 시 특정 형식을 요구합니다        
                            print(f"Special handling for direct channel creation with users: {data}", flush=True)
                            
                            # 먼저 사용자 ID들이 유효한지 확인
                            try:
                                # 봇 정보 가져오기
                                bot_info = self.get_user_info('me')
                                bot_id = bot_info['id']
                                print(f"Bot ID for direct channel: {bot_id}", flush=True)
                                
                                # 모든 사용자 ID 유효성 검사
                                for user_id in data:
                                    if user_id != bot_id:  # 봇 ID가 아닌 경우만 검사
                                        try:
                                            # 사용자 정보 가져오기 시도
                                            print(f"Verifying user ID: {user_id}", flush=True)
                                            # 이 호출은 실패할 수 있지만, 그래도 시도
                                            # self.make_request('GET', f'/users/{user_id}')
                                        except Exception as e:
                                            print(f"Warning: Failed to verify user ID {user_id}: {e}", flush=True)
                                
                                # 순서 정렬
                                user_ids = list(data)  # 복사본 생성
                                
                                # 사용자 ID가 두 개인 경우 순서 확인
                                if len(user_ids) == 2:
                                    if user_ids[0] == bot_id and user_ids[1] != bot_id:
                                        print(f"Order is already correct: [bot_id, user_id]", flush=True)
                                    elif user_ids[1] == bot_id and user_ids[0] != bot_id:
                                        print(f"Reversing order from [user_id, bot_id] to [bot_id, user_id]", flush=True)
                                        user_ids = [bot_id, user_ids[0]]
                                    else:
                                        print(f"Warning: Unexpected ID configuration", flush=True)
                                
                                # Mattermost API 문서에 따라 다른 형식 시도
                                # 1. 일반 배열 형식
                                print(f"Trying array format with user_ids: {user_ids}", flush=True)
                                try:
                                    response = self.session.post(url, headers=self.headers, json=user_ids, files=files, timeout=10)
                                    if response.status_code < 400:
                                        print(f"Array format succeeded with status: {response.status_code}", flush=True)
                                        return response.json() if response.text else {}
                                    else:
                                        print(f"Array format failed with status: {response.status_code}", flush=True)
                                except Exception as e:
                                    print(f"Array format error: {e}", flush=True)
                                
                                # 2. JSON 객체 형식 시도 (user_ids 키 사용)
                                json_format = {"user_ids": user_ids}
                                print(f"Trying JSON object format: {json_format}", flush=True)
                                try:
                                    response = self.session.post(url, headers=self.headers, json=json_format, files=files, timeout=10)
                                    if response.status_code < 400:
                                        print(f"JSON format succeeded with status: {response.status_code}", flush=True)
                                        return response.json() if response.text else {}
                                    else:
                                        print(f"JSON format failed with status: {response.status_code}", flush=True)
                                except Exception as e:
                                    print(f"JSON format error: {e}", flush=True)
                                
                                # 3. 사용자 ID를 콤마로 구분한 문자열 형식 시도
                                id_str = ",".join(user_ids)
                                print(f"Trying comma-separated string format: {id_str}", flush=True)
                                try:
                                    headers = self.headers.copy()
                                    headers["Content-Type"] = "application/x-www-form-urlencoded"
                                    response = self.session.post(url, headers=headers, data=id_str, timeout=10)
                                    if response.status_code < 400:
                                        print(f"String format succeeded with status: {response.status_code}", flush=True)
                                        return response.json() if response.text else {}
                                    else:
                                        print(f"String format failed with status: {response.status_code}", flush=True)
                                except Exception as e:
                                    print(f"String format error: {e}", flush=True)
                                
                                # 모든 시도 실패 시 오류 발생
                                raise Exception("All attempts to create direct channel failed")
                                
                            except Exception as e:
                                print(f"Error in direct channel creation: {e}", flush=True)
                                raise
                        elif method.lower() == 'get':
                            response = self.session.get(url, headers=self.headers, timeout=10)
                        elif method.lower() == 'post':
                            response = self.session.post(url, headers=self.headers, json=data, files=files, timeout=10)
                        elif method.lower() == 'put':
                            response = self.session.put(url, headers=self.headers, json=data, timeout=10)
                        elif method.lower() == 'delete':
                            response = self.session.delete(url, headers=self.headers, timeout=10)
                        else:
                            raise ValueError(f"Unsupported method: {method}")
                        
                        print(f"Response status: {response.status_code}")
                        if response.status_code >= 400:
                            print(f"Error response: {response.text[:200]}")
                            
                        response.raise_for_status()
                        if response.text:
                            return response.json()
                        return {}
                    except Exception as e:
                        print(f"API request error ({method} {url}): {e}")
                        print(traceback.format_exc())
                        raise
                
                # 기존 Driver 클래스와 호환되는 메서드 추가
                def get_user_info(self, user_id='me'):
                    """users.get_user(user_id='me') 대체 메서드"""
                    return self.make_request('GET', f'/users/{user_id}')
                
                def get_users_by_username(self, username):
                    """username으로 사용자 검색"""
                    try:
                        # Mattermost API는 username으로 사용자 검색 기능 제공
                        return self.make_request('GET', f'/users/username/{username}')
                    except Exception as e:
                        print(f"Error finding user by username {username}: {e}", flush=True)
                        return None
                
                def get_all_users(self, page=0, per_page=100):
                    """Mattermost 서버의 모든 사용자 목록 가져오기"""
                    try:
                        # 페이지별로 사용자 목록 가져오기
                        return self.make_request('GET', f'/users?page={page}&per_page={per_page}')
                    except Exception as e:
                        print(f"Error getting users list: {e}", flush=True)
                        return []
                
                def create_dm_channel(self, user_ids):
                    """channels.create_direct_message_channel 대체 메서드"""
                    print(f"DEBUG: SimpleMattermostAPI.create_dm_channel: BEFORE modification, user_ids: {user_ids}", flush=True)
                    
                    # Mattermost API 문서에 따르면 user_ids는 배열 형태여야 함
                    if not isinstance(user_ids, list):
                        user_ids = [user_ids]
                    
                    # 순서 유지를 위한 보호 장치 - 데이터 그대로 전달
                    print(f"DEBUG: SimpleMattermostAPI.create_dm_channel: AFTER modification, final user_ids to API: {user_ids}", flush=True)
                    
                    # 순서 그대로 전달하기 위해 list() 함수로 복사본 만들기
                    return self.make_request('POST', '/channels/direct', data=list(user_ids))
                
                def create_post(self, options):
                    """posts.create_post 대체 메서드"""
                    return self.make_request('POST', '/posts', data=options)
                
                def upload_file(self, channel_id, files):
                    """files.upload_file 대체 메서드"""
                    return self.make_request('POST', f'/files?channel_id={channel_id}', files=files)
            
            # 직접 API 호출로 사용자 정보 확인
            direct_api_url = f"{scheme}://{hostname}:{port}"
            direct_api = SimpleMattermostAPI(direct_api_url, token)
            
            # 실제 API 호출 테스트
            print("Testing API connection by getting current user info...")
            try:
                user_info = direct_api.make_request('GET', '/users/me')
                print(f"Successfully authenticated as: {user_info.get('username', 'Unknown')} (ID: {user_info.get('id', 'Unknown')})")
                
                # 성공적으로 API 호출이 가능하면 mm 객체로 설정
                mm = direct_api
                mattermost_configured = True
                print("Alternative authentication method successful!")
            except Exception as e:
                print(f"Alternative authentication failed: {e}")
                mattermost_configured = False
        except Exception as e:
            print(f"Alternative API setup failed: {e}")
            print(traceback.format_exc())
            mattermost_configured = False
    
    print(f"Mattermost driver configured: {mattermost_configured}")
except Exception as e:
    print(f"Error configuring Mattermost driver: {e}")
    print(traceback.format_exc()) # 전체 스택 트레이스 출력
    print(f"Check if Mattermost server is running at {mattermost_url} and token is valid")
    mm = None
    mattermost_configured = False

# 아래 함수들은 mm 객체가 SimpleMattermostAPI 클래스인 경우를 처리하기 위해 수정

async def send_message_to_user(
    message: str,
    user_id: Optional[str] = None, 
    file_ids: Optional[List[str]] = None,
    channel_id: Optional[str] = None 
):
    """
    Mattermost 사용자에게 개인 메시지(DM)를 전송합니다. 파일 ID 목록을 첨부할 수 있습니다.
    channel_id가 제공되면 해당 채널을 사용하고, 그렇지 않으면 user_id를 사용하여 DM 채널을 생성합니다.
    """
    if not mattermost_configured or mm is None:
        print("Mattermost is not configured. Skipping message sending.")
        return False

    try:
        current_channel_id = channel_id

        if not current_channel_id and user_id:
            # channel_id가 제공되지 않았고 user_id가 제공된 경우에만 DM 채널 생성
            print(f"Channel ID not provided, creating DM channel for user_id: {user_id}")
            if hasattr(mm, 'make_request'): # SimpleMattermostAPI
                bot_user_info = mm.get_user_info('me')
                bot_user_id = bot_user_info['id']
                # DM 채널 생성 시 사용자 ID 순서: [봇 사용자, 대상 사용자]로 통일
                dm_channel_data = mm.create_dm_channel(user_ids=[bot_user_id, user_id])   
            else: # 기본 드라이버
                bot_user_info = mm.users.get_user(user_id='me')
                bot_user_id = bot_user_info['id']
                # DM 채널 생성 시 사용자 ID 순서: [봇 사용자, 대상 사용자]로 통일
                dm_channel_data = mm.channels.create_direct_message_channel(user_ids=[bot_user_id, user_id])

            current_channel_id = dm_channel_data['id']
            print(f"DM Channel created/retrieved: {current_channel_id} for user {user_id}")
        
        if not current_channel_id:
            print("Error: Channel ID could not be determined or created.")
            return False

        post_options = {
            "channel_id": current_channel_id,
            "message": message,
        }
        if file_ids:
            post_options["file_ids"] = file_ids
        
        print(f"Sending message to channel_id: {current_channel_id} with options: {post_options}")

        if hasattr(mm, 'make_request'): # SimpleMattermostAPI
            created_post = mm.create_post(options=post_options)
        else: # 기본 드라이버
            created_post = mm.posts.create_post(options=post_options)
        
        print(f"Message sent successfully. Post ID: {created_post['id']}")
        return True
    except Exception as e:
        print(f"Error sending message to user {user_id if user_id else ''} / channel {current_channel_id if current_channel_id else ''}: {e}")
        print(traceback.format_exc())
        return False

async def send_message_to_channel(channel_id: str, message: str, file_ids: Optional[List[str]] = None) -> bool:
    """
    지정된 Mattermost 채널에 메시지를 전송합니다. 파일 ID 목록을 첨부할 수 있습니다.
    """
    if not mattermost_configured or mm is None:
        print("Mattermost is not configured. Skipping message sending.")
        return False
    try:
        # SimpleMattermostAPI 클래스를 사용하는 경우
        if hasattr(mm, 'make_request'):
            post_data = {
                "channel_id": channel_id,
                "message": message,
            }
            if file_ids:
                post_data["file_ids"] = file_ids
                
            mm.make_request('POST', '/posts', data=post_data)
        else:
            # 기존 mattermostdriver 사용
            post_options: Dict[str, Any] = {
                "channel_id": channel_id,
                "message": message,
            }
            if file_ids:
                post_options["file_ids"] = file_ids

            mm.posts.create_post(options=post_options)
            
        print(f"Message sent to channel {channel_id}.")
        return True
    except Exception as e:
        print(f"Error sending message to channel {channel_id}: {e}")
        print(traceback.format_exc())
        return False

async def upload_file_to_mattermost(channel_id: str, file_path: str) -> Optional[str]:
    """
    파일을 Mattermost 채널에 업로드하고 파일 ID를 반환합니다.
    """
    if not mattermost_configured or mm is None:
        print("Mattermost is not configured. Skipping file upload.")
        return None
    if not os.path.exists(file_path):
        print(f"File not found at path: {file_path}")
        return None

    try:
        # SimpleMattermostAPI 클래스를 사용하는 경우
        if hasattr(mm, 'make_request'):
            with open(file_path, 'rb') as f:
                file_data = {'files': (os.path.basename(file_path), f)}
                response = mm.make_request('POST', f'/files?channel_id={channel_id}', files=file_data)
            
            file_id = response['file_infos'][0]['id']
        else:
            # 기존 mattermostdriver 사용
            with open(file_path, 'rb') as f:
                file_data = {'files': (os.path.basename(file_path), f)}
                response = mm.files.upload_file(channel_id=channel_id, files=file_data)
            
            file_id = response['file_infos'][0]['id']
            
        print(f"File {file_path} uploaded to channel {channel_id}. File ID: {file_id}")
        return file_id
    except Exception as e:
        print(f"Error uploading file {file_path} to Mattermost: {e}")
        print(traceback.format_exc())
        return None

# 테스트 함수 추가
async def test_mattermost_connection() -> Dict[str, Any]:
    """
    Mattermost 연결을 테스트하고 결과를 반환합니다.
    """
    if not mattermost_configured or mm is None:
        return {"success": False, "error": "Mattermost service is not configured."}
        
    result = {
        "configured": mattermost_configured,
        "url": mattermost_url,
        "connection_type": "SimpleMattermostAPI" if hasattr(mm, 'make_request') else "mattermostdriver",
    }
    
    try:
        # 사용자 정보 가져오기 시도
        if hasattr(mm, 'make_request'):
            user_info = mm.make_request('GET', '/users/me')
        else:
            user_info = mm.users.get_user(user_id='me')
            
        result["success"] = True
        result["user_info"] = {
            "id": user_info.get('id'),
            "username": user_info.get('username'),
            "email": user_info.get('email')
        }
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
        
    return result

# 이 서비스의 함수들은 workflow_service.py에서 호출되어 사용됩니다.
# 예시: 회의록 PDF를 특정 사용자에게 전송

async def find_mattermost_user_id(username: str) -> Optional[str]:
    """
    Mattermost 사용자 이름으로 사용자 ID를 찾습니다.
    username은 @ 기호를 포함할 수 있습니다 (e.g. @woorifisa1)
    """
    if not mattermost_configured or mm is None:
        print("Mattermost is not configured. Cannot find user ID.")
        return None
        
    try:
        # @ 기호 제거
        if username.startswith('@'):
            username = username[1:]
            
        print(f"Finding Mattermost user ID for username: {username}", flush=True)
        
        if hasattr(mm, 'get_users_by_username'):
            # 사용자 이름으로 사용자 검색
            user_info = mm.get_users_by_username(username)
            if user_info:
                print(f"Found user by username: ID={user_info.get('id')}, Username={user_info.get('username')}", flush=True)
                return user_info.get('id')
                
        # 모든 사용자 목록에서 검색
        if hasattr(mm, 'get_all_users'):
            users = mm.get_all_users()
            if users:
                # 사용자 목록 출력 (10명 이하)
                max_to_show = min(10, len(users))
                print(f"Found {len(users)} users on Mattermost. Showing first {max_to_show}:", flush=True)
                for i, user in enumerate(users[:max_to_show]):
                    print(f"  {i+1}. ID: {user.get('id')}, Username: {user.get('username')}, Email: {user.get('email')}", flush=True)
                
                # 사용자 이름 또는 이메일로 검색
                for user in users:
                    if user.get('username') == username or user.get('email') == username:
                        print(f"Found matching user: ID={user.get('id')}, Username={user.get('username')}", flush=True)
                        return user.get('id')
                        
        print(f"Could not find user with username/email: {username}", flush=True)
        return None
    except Exception as e:
        print(f"Error finding Mattermost user ID for {username}: {e}")
        print(traceback.format_exc())
        return None

def find_channel_id_by_name(channel_name: str, team_id: Optional[str] = None) -> Optional[str]:
    """
    Mattermost 채널 이름으로 채널 ID를 찾습니다.
    team_id가 제공되지 않으면 봇이 속한 모든 팀에서 검색합니다.
    channel_name은 URL 친화적인 이름 (핸들)이어야 합니다.
    """
    logger.info(f"Attempting to find channel ID for name: '{channel_name}', team_id: {team_id}")
    channel_name_lower = channel_name.lower() # API는 보통 소문자 핸들을 사용

    global mattermost_configured, mm, direct_api

    if mattermost_configured and mm:
        logger.debug("Using 'mm' (Mattermost Driver) for channel search.")
        try:
            if team_id:
                channel = mm.channels.get_channel_by_name(team_id=team_id, channel_name=channel_name_lower)
                if channel and channel.get('id'):
                    logger.info(f"Channel '{channel_name}' found in team '{team_id}' with ID: {channel['id']} using mm.")
                    return channel['id']
            else:
                teams = mm.teams.get_teams_for_user('me')
                if teams:
                    for team in teams:
                        current_team_id = team['id']
                        logger.debug(f"Searching channel '{channel_name_lower}' in team ID: {current_team_id} using mm.")
                        try:
                            channel = mm.channels.get_channel_by_name(team_id=current_team_id, channel_name=channel_name_lower)
                            if channel and channel.get('id'):
                                logger.info(f"Channel '{channel_name}' found in team '{current_team_id}' with ID: {channel['id']} using mm.")
                                return channel['id']
                        except Exception as e_inner:
                            logger.debug(f"Channel '{channel_name_lower}' not found in team '{current_team_id}' or error: {e_inner} (mm)")
                logger.info(f"Channel '{channel_name}' not found in any of the bot's teams using mm.")
        except Exception as e:
            logger.warning(f"Error using 'mm' to find channel '{channel_name}': {e}. Falling back to direct_api if available.")
            if not direct_api: # mm 실패했고 direct_api도 없으면 여기서 끝
                return None 
    
    # mm 사용 실패 또는 mm이 설정되지 않은 경우 direct_api 사용 시도
    if direct_api:
        logger.debug("Using 'direct_api' (SimpleMattermostAPI) for channel search.")
        try:
            if team_id:
                channel_data = direct_api.make_request('GET', f'/teams/{team_id}/channels/name/{channel_name_lower}')
                if channel_data and channel_data.get('id'):
                    logger.info(f"Channel '{channel_name}' found in team '{team_id}' with ID: {channel_data['id']} using direct_api.")
                    return channel_data['id']
            else:
                teams_data = direct_api.make_request('GET', '/users/me/teams')
                if teams_data and isinstance(teams_data, list):
                    for team in teams_data:
                        current_team_id = team.get('id')
                        if not current_team_id:
                            continue
                        logger.debug(f"Searching channel '{channel_name_lower}' in team ID: {current_team_id} using direct_api.")
                        channel_data = direct_api.make_request('GET', f'/teams/{current_team_id}/channels/name/{channel_name_lower}')
                        if channel_data and channel_data.get('id'):
                            logger.info(f"Channel '{channel_name}' found in team '{current_team_id}' with ID: {channel_data['id']} using direct_api.")
                            return channel_data['id']
                logger.info(f"Channel '{channel_name}' not found in any of the bot's teams using direct_api.")
        except Exception as e:
            logger.error(f"Error using 'direct_api' to find channel '{channel_name}': {e}")
            return None
    else:
        logger.warning("Neither 'mm' nor 'direct_api' is available for channel search.")

    logger.info(f"Channel ID for name '{channel_name}' (team_id: {team_id}) not found.")
    return None

async def list_mattermost_users() -> List[Dict[str, Any]]:
    """
    Mattermost 사용자 목록을 가져와 출력합니다.
    """
    if not mattermost_configured or mm is None:
        print("Mattermost is not configured. Cannot list users.")
        return []
        
    try:
        users = []
        if hasattr(mm, 'get_all_users'):
            users = mm.get_all_users()
            print(f"Found {len(users)} users on Mattermost:", flush=True)
            for i, user in enumerate(users):
                print(f"  {i+1}. ID: {user.get('id')}, Username: {user.get('username')}, Email: {user.get('email')}", flush=True)
        else:
            print("Cannot list users - get_all_users method not available.")
        return users
    except Exception as e:
        print(f"Error listing Mattermost users: {e}")
        print(traceback.format_exc())
        return []

async def send_minutes_to_user(user_id: str, minutes_pdf_path: str, meeting_title: str):
    """
    회의록 PDF를 특정 사용자에게 전송합니다.
    """
    if not os.path.exists(minutes_pdf_path):
        print(f"File not found: {minutes_pdf_path}")
        return False

    if not mattermost_configured or mm is None: 
        print("Mattermost is not configured. Skipping sending minutes.")
        return False

    try:
        # 1. 봇과 사용자 간의 DM 채널 ID 가져오기
        # SimpleMattermostAPI 또는 기본 드라이버 사용 분기
        if hasattr(mm, 'make_request'):
            bot_user_info = mm.get_user_info('me') # 'me'를 사용하여 봇 자신의 정보 가져오기
            bot_user_id = bot_user_info['id']
            print(f"Creating DM channel between bot (ID: {bot_user_id}) and user (ID: {user_id})", flush=True)
            # DM 채널 생성 시 사용자 ID 순서: [봇 사용자, 대상 사용자]로 통일
            # 배열 순서: [봇ID, 사용자ID] - 정확한 순서 유지를 위해 새 배열 생성
            bot_id_first = [bot_user_id, user_id]
            print(f"DEBUG: send_minutes_to_user: About to call create_dm_channel with EXACT user_ids: {bot_id_first}", flush=True)
            # 명시적으로 직접 배열을 생성해서 전달 (순서 변경 방지)
            channel_data = mm.create_dm_channel(user_ids=[bot_user_id, user_id])
        else:
            bot_user_info = mm.users.get_user(user_id='me')
            bot_user_id = bot_user_info['id']
            print(f"Creating DM channel between bot (ID: {bot_user_id}) and user (ID: {user_id})")
            # 기본 드라이버의 create_direct_message_channel도 [봇ID, 사용자ID] 순서로 전달합니다.
            channel_data = mm.channels.create_direct_message_channel(user_ids=[bot_user_id, user_id])
            
        channel_id = channel_data['id']
        print(f"DM Channel created/retrieved: {channel_id}")

        # 2. 파일 업로드
        file_id = await upload_file_to_mattermost(channel_id=channel_id, file_path=minutes_pdf_path)
        if file_id:
            # 3. 메시지 전송 (수정된 send_message_to_user 호출)
            message = f"'{meeting_title}' 회의록을 첨부 파일로 보내드립니다."
            # user_id는 이제 선택사항, channel_id를 명시적으로 전달
            return await send_message_to_user(message=message, file_ids=[file_id], channel_id=channel_id)
        print("File upload failed, not sending message.") # 파일 업로드 실패 시 로그 추가
        return False
    except Exception as e:
        print(f"Error sending minutes to user {user_id}: {e}")
        print(traceback.format_exc())
        return False
