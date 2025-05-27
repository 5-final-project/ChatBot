# # Mattermost 참여자 생성하는 코드


# import asyncio
# import httpx
# import os
# import sys
# import json
# import mysql.connector
# from mysql.connector import Error as DBError # Import Error for specific handling

# # Add project root to Python path to allow imports from 'app'
# sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# from app.core.config import settings

# async def create_mm_user(client: httpx.AsyncClient, email: str, username: str, password: str, first_name: str = "", last_name: str = "") -> dict:
#     url = f"{settings.MATTERMOST_URL}/api/v4/users"
#     headers = {
#         "Authorization": f"Bearer {settings.MATTERMOST_BOT_TOKEN}",
#         "Content-Type": "application/json",
#     }
#     payload = {
#         "email": email,
#         "username": username,
#         "password": password,
#         "first_name": first_name,
#         "last_name": last_name,
#     }
#     try:
#         response = await client.post(url, headers=headers, json=payload)
#         response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
#         print(f"User '{username}' creation API call successful. Status: {response.status_code}")
#         # Return the full response content, which should be the user object
#         return response.json() 
#     except httpx.HTTPStatusError as e:
#         error_response = {}
#         try:
#             error_response = e.response.json()
#         except json.JSONDecodeError:
#             pass # Keep error_response empty if not valid JSON
        
#         if e.response.status_code == 400 and error_response.get("id") in [
#             "store.sql_user.save.username_exists.app_error",
#             "store.sql_user.save.email_exists.app_error",
#             "api.user.create_user.existing_username.app_error", # Another possible error ID for existing username
#             "api.user.create_user.existing_email.app_error" # Another possible error ID for existing email
#         ]:
#             print(f"User '{username}' or email '{email}' likely already exists. API Status: {e.response.status_code}, Message: {error_response.get('message')}")
#             return {"status": "exists", "message": error_response.get('message', 'User or email already exists.'), "details": error_response}
#         elif e.response.status_code == 403:
#              print(f"Permission denied for creating user '{username}'. Check bot token permissions. API Status: {e.response.status_code}, Message: {error_response.get('message')}")
#              return {"status": "error", "message": f"Permission denied: {error_response.get('message', 'Forbidden')}", "details": error_response}
#         else:
#             print(f"Error creating user '{username}'. Status: {e.response.status_code}, Response: {e.response.text}")
#             return {"status": "error", "message": f"Failed to create user: {e.response.text}", "details": error_response}
#     except httpx.RequestError as e:
#         print(f"Request error while creating user '{username}': {e}")
#         return {"status": "error", "message": f"Request error: {e}"}

# async def get_mm_user_details(client: httpx.AsyncClient, username: str) -> dict:
#     # Mattermost API expects username without '@'
#     username_to_find = username.lstrip('@')
#     url = f"{settings.MATTERMOST_URL}/api/v4/users/username/{username_to_find}"
#     headers = {
#         "Authorization": f"Bearer {settings.MATTERMOST_BOT_TOKEN}",
#     }
#     try:
#         response = await client.get(url, headers=headers)
#         response.raise_for_status()
#         print(f"Successfully fetched details for user '{username_to_find}'.")
#         return response.json()
#     except httpx.HTTPStatusError as e:
#         if e.response.status_code == 404:
#             print(f"User '{username_to_find}' not found. API Status: 404")
#             return {"status": "not_found", "message": "User not found."}
#         print(f"Error fetching user '{username_to_find}'. Status: {e.response.status_code}, Response: {e.response.text}")
#         return {"status": "error", "message": f"Failed to fetch user: {e.response.text}"}
#     except httpx.RequestError as e:
#         print(f"Request error while fetching user '{username_to_find}': {e}")
#         return {"status": "error", "message": f"Request error: {e}"}

# def get_db_connection():
#     try:
#         conn = mysql.connector.connect(
#             host=settings.DB_HOST,
#             port=settings.DB_PORT,
#             user=settings.DB_USER,
#             password=settings.DB_PASSWORD,
#             database=settings.DB_NAME,
#             charset=settings.DB_CHARSET,
#             # ssl_disabled=(settings.DB_SSL_MODE == "DISABLED" or not settings.DB_SSL_MODE) # Adjusted for clarity
#         )
#         if conn.is_connected():
#             print("Successfully connected to the MySQL database.")
#             return conn
#     except DBError as e:
#         print(f"Error connecting to MySQL database: {e}")
#         return None

# async def main():
#     print("Starting Mattermost user management script...")
#     print(f"Mattermost URL: {settings.MATTERMOST_URL}")
#     if not settings.MATTERMOST_URL or not settings.MATTERMOST_BOT_TOKEN:
#         print("MATTERMOST_URL or MATTERMOST_BOT_TOKEN is not set in .env file. Exiting.")
#         return

#     users_to_process = [
#         {"first_name": "다희", "last_name": "김", "username": "dahee.kim", "email_local_part": "dahee.kim"},
#         {"first_name": "경훈", "last_name": "김", "username": "kyeonghun.kim", "email_local_part": "kyeonghun.kim"},
#         {"first_name": "상우", "last_name": "오", "username": "sangwoo.oh", "email_local_part": "sangwoo.oh"},
#         {"first_name": "웅상", "last_name": "윤", "username": "woongsang.yoon", "email_local_part": "woongsang.yoon"},
#         {"first_name": "재우", "last_name": "박", "username": "jaewoo.park", "email_local_part": "jaewoo.park"},
#         {"first_name": "서준", "last_name": "이", "username": "seojun.lee", "email_local_part": "seojun.lee"},
#         {"first_name": "하윤", "last_name": "박", "username": "hayoon.park", "email_local_part": "hayoon.park"},
#         {"first_name": "도윤", "last_name": "최", "username": "doyoon.choi", "email_local_part": "doyoon.choi"},
#         {"first_name": "지우", "last_name": "강", "username": "jiwoo.kang", "email_local_part": "jiwoo.kang"},
#         {"first_name": "시우", "last_name": "정", "username": "siwoo.jung", "email_local_part": "siwoo.jung"},
#         {"first_name": "서아", "last_name": "조", "username": "seoa.cho", "email_local_part": "seoa.cho"},
#         {"first_name": "예준", "last_name": "황", "username": "yejun.hwang", "email_local_part": "yejun.hwang"},
#         {"first_name": "하은", "last_name": "송", "username": "haeun.song", "email_local_part": "haeun.song"},
#         {"first_name": "지호", "last_name": "문", "username": "jiho.moon", "email_local_part": "jiho.moon"},
#         {"first_name": "수아", "last_name": "임", "username": "sua.lim", "email_local_part": "sua.lim"},
#     ]
#     default_password = "Password123!"  # Consider a more secure way to handle passwords
#     email_domain = "example.com" # Or your actual domain

#     all_users_data = []

#     db_conn = get_db_connection()
#     if not db_conn:
#         print("Could not connect to database. Exiting script.")
#         return

#     try:
#         with db_conn.cursor() as cursor:
#             # Drop the table if it exists
#             drop_table_query = "DROP TABLE IF EXISTS mattermost_user_mappings;"
#             print(f"Executing: {drop_table_query}")
#             cursor.execute(drop_table_query)
#             print("Table 'mattermost_user_mappings' dropped if it existed.")

#             # Create the table with the new schema
#             create_table_query = """
#             CREATE TABLE mattermost_user_mappings (
#                 mattermost_user_id VARCHAR(26) NOT NULL PRIMARY KEY,
#                 username VARCHAR(255) NOT NULL UNIQUE,
#                 email VARCHAR(255) NOT NULL UNIQUE,
#                 first_name VARCHAR(100),
#                 last_name VARCHAR(100),
#                 nickname VARCHAR(255),
#                 roles VARCHAR(255),
#                 create_at BIGINT,
#                 update_at BIGINT,
#                 INDEX idx_username (username),
#                 INDEX idx_email (email)
#             ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
#             """
#             print("Executing: CREATE TABLE mattermost_user_mappings...")
#             cursor.execute(create_table_query)
#             print("Table 'mattermost_user_mappings' created successfully.")
#             db_conn.commit() # Commit drop and create operations

#         async with httpx.AsyncClient() as client:
#             for user_spec in users_to_process:
#                 email = f"{user_spec['email_local_part']}@{email_domain}"
#                 username = user_spec['username']
#                 # Use first_name and last_name from user_spec for DB insertion
#                 db_first_name = user_spec['first_name'] 
#                 db_last_name = user_spec['last_name']

#                 print(f"\n--- Processing user: {username} ({db_first_name} {db_last_name}) ---")
                
#                 # Attempt to create user
#                 creation_result = await create_mm_user(client, email, username, default_password, db_first_name, db_last_name)
                
#                 user_details = None
#                 if creation_result.get("id") and creation_result.get("status") is None: # Successfully created
#                     print(f"User '{username}' created successfully in Mattermost. ID: {creation_result.get('id')}")
#                     user_details = creation_result 
#                 elif creation_result.get("status") == "exists":
#                     print(f"User '{username}' already exists in Mattermost. Fetching details...")
#                     # user_details = await get_mm_user_details(client, username) # Already tried in create_mm_user logic if it's smart enough
#                 elif creation_result.get("status") == "error":
#                     print(f"An error occurred during Mattermost creation of '{username}': {creation_result.get('message')}")
#                 else:
#                     print(f"Unexpected Mattermost response during creation of '{username}': {creation_result}")

#                 # Always try to fetch details to ensure we have the latest, or if creation failed but user might exist
#                 print(f"Fetching details for '{username}' from Mattermost (either due to prior existence or to confirm status)...")
#                 fetched_details = await get_mm_user_details(client, username)
#                 if fetched_details and not fetched_details.get("status"): # Successfully fetched valid user object
#                     user_details = fetched_details
#                     print(f"Successfully fetched/confirmed details for Mattermost user '{username}'.")
#                 elif user_details and user_details.get("id"): # If creation was successful but fetch failed, use created data
#                     print(f"Using initially created data for '{username}' as subsequent fetch failed.")
#                 else: # Fetch failed, and no prior success from creation
#                     user_details = fetched_details # Store not_found or error status from fetch
#                     print(f"Could not fetch valid details for Mattermost user '{username}'. Status: {user_details.get('status') if user_details else 'N/A'}")

#                 if user_details and user_details.get("id") and not user_details.get("status"): # Check if it's a valid user object with an ID
#                     all_users_data.append({
#                         "mattermost_user_id": user_details.get("id"),
#                         "username": user_details.get("username"),
#                         "email": user_details.get("email"),
#                         "first_name": db_first_name, # Use name from user_spec
#                         "last_name": db_last_name,   # Use name from user_spec
#                         "nickname": user_details.get("nickname", ""),
#                         "roles": user_details.get("roles", ""),
#                         "create_at": user_details.get("create_at"),
#                         "update_at": user_details.get("update_at")
#                     })
#                     print(f"Prepared DB data for {user_details.get('username')}:")
#                     print(f"  ID: {user_details.get('id')}")
#                     print(f"  Username: {user_details.get('username')}")
#                     print(f"  Email: {user_details.get('email')}")
#                     print(f"  First Name (for DB): {db_first_name}")
#                     print(f"  Last Name (for DB): {db_last_name}")
#                     print(f"  MM Nickname: {user_details.get('nickname')}")
#                     print(f"  MM Roles: {user_details.get('roles')}")
#                     print(f"  MM Create At: {user_details.get('create_at')}")
#                     print(f"  MM Update At: {user_details.get('update_at')}")
#                 elif user_details:
#                     print(f"Could not get final valid details for '{username}' for DB insertion. Status: {user_details.get('status')}, Message: {user_details.get('message')}")
#                 else:
#                     print(f"No details could be obtained for '{username}' for DB insertion.")

#         # Insert all collected user data into the database
#         if all_users_data:
#             print("\n--- Inserting/Updating data into MySQL table: mattermost_user_mappings ---")
#             insert_query = ("""
#             INSERT INTO mattermost_user_mappings 
#             (mattermost_user_id, username, email, first_name, last_name, nickname, roles, create_at, update_at)
#             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
#             ON DUPLICATE KEY UPDATE
#             username=VALUES(username), email=VALUES(email), first_name=VALUES(first_name), 
#             last_name=VALUES(last_name), nickname=VALUES(nickname), roles=VALUES(roles), 
#             create_at=VALUES(create_at), update_at=VALUES(update_at);
#             """) # ON DUPLICATE KEY UPDATE is good practice, though table is fresh.
            
#             records_to_insert = []
#             for user_data in all_users_data:
#                 records_to_insert.append((
#                     user_data['mattermost_user_id'],
#                     user_data['username'],
#                     user_data['email'],
#                     user_data['first_name'],
#                     user_data['last_name'],
#                     user_data['nickname'],
#                     user_data['roles'],
#                     user_data.get('create_at'), # Use .get for nullable fields
#                     user_data.get('update_at')  # Use .get for nullable fields
#                 ))
            
#             if records_to_insert:
#                 with db_conn.cursor() as cursor:
#                     cursor.executemany(insert_query, records_to_insert)
#                     db_conn.commit()
#                     print(f"{cursor.rowcount} records inserted/updated in mattermost_user_mappings.")
#             else:
#                 print("No valid user data to insert into the database.")
#         else:
#             print("No user data was successfully prepared for DB insertion.")

#     except DBError as e:
#         print(f"Database operation failed: {e}")
#     finally:
#         if db_conn and db_conn.is_connected():
#             db_conn.close()
#             print("MySQL connection closed.")

#     print("\nMattermost user management script finished.")

# if __name__ == "__main__":
#     if sys.platform == "win32" and sys.version_info >= (3, 8):
#         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
#     asyncio.run(main())
