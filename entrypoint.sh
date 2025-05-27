#!/bin/sh

echo "Clearing Python cache..."
find /app -type d -name "__pycache__" -exec rm -r {} +
find /app -name "*.pyc" -delete
echo "Python cache cleared."

echo "Listing contents of /app:"
ls -lA /app

echo "\nListing contents of /app/app (if it exists):"
if [ -d "/app/app" ]; then
  ls -lA /app/app
else
  echo "/app/app directory does not exist."
fi

echo "\nAttempting to import main..."
# Python에게 main 모듈을 직접 임포트하도록 시도하여 오류 확인
python -c "import main; print('main imported successfully')"
IMPORT_RESULT=$?

if [ $IMPORT_RESULT -ne 0 ]; then
  echo "Failed to import main. Python exited with status $IMPORT_RESULT. Check logs above for import errors."
  exit $IMPORT_RESULT
fi

echo "Starting FastAPI server in background..."
uvicorn main:app --host 0.0.0.0 --port 8126 --reload &
UVICORN_PID=$!

echo "Waiting for server to start (8 seconds)..."
sleep 8

echo "Running pytest..."
python -m pytest /app/tests
PYTEST_RESULT=$?

# pytest 실행 후 uvicorn 프로세스 상태 확인 (혹시 모를 uvicorn 자체 오류)
if ! ps -p $UVICORN_PID > /dev/null; then
  echo "Uvicorn server process is not running after tests. It might have crashed."
  # 컨테이너가 종료되도록 실패 코드 반환
  exit 1
fi

if [ $PYTEST_RESULT -ne 0 ]; then
  echo "Pytest failed with status $PYTEST_RESULT. Stopping container."
  kill $UVICORN_PID # 백그라운드 uvicorn 프로세스 종료
  wait $UVICORN_PID 2>/dev/null # 종료 대기
  exit $PYTEST_RESULT
fi

echo "Pytest passed. Keeping server alive."
# uvicorn이 포그라운드에서 계속 실행되도록 wait
# 이렇게 하면 Ctrl+C로 컨테이너를 중지할 때 uvicorn도 함께 종료됨
wait $UVICORN_PID
