@echo off
title BhoomiFi Launcher
color 0A

echo.
echo  ========================================
echo   BhoomiFi — Starting All Services...
echo  ========================================
echo.

echo  [1/4] Starting ML Service on port 5000...
start "ML Service :5000" cmd /k "cd /d C:\Users\Saish\OneDrive\Desktop\Projects\BHOOMI-Fi\BHOOMI-FI\ml-service && C:\Users\Saish\OneDrive\Desktop\Projects\BHOOMI-Fi\BHOOMI-FI\.venv\Scripts\activate && python app.py"
timeout /t 3 /nobreak > nul

echo  [2/4] Starting MySQL Logger on port 5001...
start "MySQL Logger :5001" cmd /k "cd /d C:\Users\Saish\OneDrive\Desktop\Projects\BHOOMI-Fi\BHOOMI-FI && C:\Users\Saish\OneDrive\Desktop\Projects\BHOOMI-Fi\BHOOMI-FI\.venv\Scripts\activate && python backend/mysql_logger.py"
timeout /t 3 /nobreak > nul

echo  [3/4] Starting MongoDB Logger on port 5002...
start "MongoDB Logger :5002" cmd /k "cd /d C:\Users\Saish\OneDrive\Desktop\Projects\BHOOMI-Fi\BHOOMI-FI && C:\Users\Saish\OneDrive\Desktop\Projects\BHOOMI-Fi\BHOOMI-FI\.venv\Scripts\activate && python backend/mongo_logger.py"
timeout /t 3 /nobreak > nul

echo  [4/4] Starting Node Backend on port 8888...
start "Node Server :8888" cmd /k "cd /d C:\Users\Saish\OneDrive\Desktop\Projects\BHOOMI-Fi\BHOOMI-FI && node backend/server.js"
timeout /t 4 /nobreak > nul

echo.
echo  ========================================
echo   All services started successfully!
echo   Opening BhoomiFi in browser...
echo  ========================================
echo.

timeout /t 2 /nobreak > nul
start http://localhost:8888

echo  Press any key to close this window...
pause > nul