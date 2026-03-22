@echo off

echo -----------------------------------------------------------
echo [1] Booting Real Local Redis Server...
start "Redis Server" ".\redis_bin\redis-server.exe"

timeout /t 2 /nobreak > nul

echo -----------------------------------------------------------
echo [2] Booting Python Flask API (Port 5000)...
start "Flask API" python run.py

timeout /t 2 /nobreak > nul

echo -----------------------------------------------------------
echo [3] Booting Celery Background Worker (4 threads)...
start "Celery Worker" python -m celery -A run.celery_app worker -l info --pool=threads --concurrency=4

echo -----------------------------------------------------------
echo Your Backend Ecosystem is officially running!
echo Three new console windows should be visible on your screen.
echo .
echo Please wait exactly 8 seconds for Celery to bind to Redis,
echo and then run the following command exactly in this terminal:
echo .
echo    python concurrency_test.py
echo -----------------------------------------------------------
