@echo off
setlocal EnableExtensions
title GeneVerify Launcher

rem ===========================================================================
rem  GeneVerify AI  -  one-click local startup
rem
rem  Double-click this file to start the whole application:
rem    1. FastAPI backend   ->  its own console window
rem    2. Vite dev frontend ->  its own console window
rem    3. wait until both really answer (polled, not a fixed sleep)
rem    4. open the application in your browser
rem
rem  It does not install anything, and it never touches the database, the
rem  stored documents, the sources or git.
rem
rem  Values below are the ones this project is actually configured with:
rem    backend  : backend\.venv\Scripts\python.exe run.py  ->  127.0.0.1:8000
rem               (backend\run.py; APP_ENV=development binds 127.0.0.1)
rem    health   : http://127.0.0.1:8000/api/v1/health   (api_prefix = /api/v1)
rem    frontend : npm run dev                           ->  localhost:5173
rem               (frontend\vite.config.ts, server.port = 5173)
rem    The backend CORS allow-list contains exactly http://localhost:5173, so
rem    the app is opened as "localhost", never as "127.0.0.1".
rem ===========================================================================

pushd "%~dp0"
set "ROOT=%CD%"
set "BACKEND_DIR=%ROOT%\backend"
set "FRONTEND_DIR=%ROOT%\frontend"
set "VENV_PY=%BACKEND_DIR%\.venv\Scripts\python.exe"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"
set "HEALTH_URL=http://127.0.0.1:8000/api/v1/health"
set "APP_URL=http://localhost:5173"

echo(
echo   ==========================================================
echo    GeneVerify AI  -  one-click startup
echo   ==========================================================
echo     project : %ROOT%
echo     backend : %HEALTH_URL%
echo     app     : %APP_URL%
echo     readiness: each service must answer 200 AND identify itself as GeneVerify
echo(

rem ---------------------------------------------------------------- preflight
if not exist "%BACKEND_DIR%"    goto :err_no_backend_dir
if not exist "%FRONTEND_DIR%"   goto :err_no_frontend_dir
if not exist "%VENV_PY%"        goto :err_no_venv
if not exist "%FRONTEND_DIR%\node_modules" goto :err_no_node_modules
where npm >nul 2>&1
if errorlevel 1 goto :err_no_npm

rem ------------------------------------------------- backend: start or reuse
call :is_listening %BACKEND_PORT%
if "%PORT_OPEN%"=="1" (
    echo   [backend ] Backend already running.
    echo              Port %BACKEND_PORT% is in use, so no second backend was started.
    set "BACKEND_STARTED=0"
) else (
    echo   [backend ] Starting the backend in its own window ...
    start "GeneVerify Backend" /D "%BACKEND_DIR%" cmd /k ""%VENV_PY%" run.py"
    set "BACKEND_STARTED=1"
)

rem ------------------------------------------------ frontend: start or reuse
call :is_listening %FRONTEND_PORT%
if "%PORT_OPEN%"=="1" (
    echo   [frontend] Frontend already running.
    echo              Port %FRONTEND_PORT% is in use, so no second frontend was started.
    set "FRONTEND_STARTED=0"
) else (
    echo   [frontend] Starting the frontend in its own window ...
    start "GeneVerify Frontend" /D "%FRONTEND_DIR%" cmd /k "npm run dev"
    set "FRONTEND_STARTED=1"
)

rem ------------------------------------------------------------------ waiting
echo   [backend ] Waiting for the backend to answer on %HEALTH_URL%
call :wait_for_http "%HEALTH_URL%" 90 "GeneVerify AI"
if not "%READY%"=="1" goto :err_backend

echo   [backend ] Backend is up.
echo   [frontend] Waiting for the frontend to answer on %APP_URL%
call :wait_for_http "%APP_URL%" 90 "GeneVerify AI"
if not "%READY%"=="1" goto :err_frontend

echo   [frontend] Frontend is up.

rem ------------------------------------------------------------------ browser
echo   [browser ] Opening %APP_URL%
start "" "%APP_URL%"

echo(
echo   ==========================================================
echo    GeneVerify is running.
echo(
echo     Application : %APP_URL%
echo     API health  : %HEALTH_URL%
echo     API docs    : http://127.0.0.1:%BACKEND_PORT%/docs
echo(
echo     Keep the "GeneVerify Backend" and "GeneVerify Frontend"
echo     windows open while you work. To close both of them:
echo         Stop GeneVerify.bat
echo   ==========================================================
echo(
ping -n 8 127.0.0.1 >nul
goto :finish

rem ==========================================================  subroutines  ==
:is_listening
rem  %~1 = TCP port.  Sets PORT_OPEN=1 when some process is listening on it.
set "PORT_OPEN=0"
netstat -ano | findstr /I "LISTENING" | findstr /R /C:":%~1 " >nul 2>&1 && set "PORT_OPEN=1"
exit /b

:wait_for_http
rem  %~1 = url, %~2 = max attempts (about one second each), %~3 = text the answer
rem  must contain ("GeneVerify AI": the API reports it in /health, the frontend
rem  page carries it in its title).  The text test is what makes "is it up" mean "is it GeneVerify"
rem  rather than "is any program answering on this port".  Sets READY=1/0.
set "READY=0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$u='%~1'; $m=[int]%~2; $n='%~3'; for($i=1;$i -le $m;$i++){ try { $r=Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 3; if ($r.StatusCode -eq 200 -and ($r.Content -match $n)) { exit 0 } } catch { }; Write-Host -NoNewline '.'; Start-Sleep -Seconds 1 }; exit 1" >nul 2>&1
if %ERRORLEVEL% EQU 0 set "READY=1"
exit /b

rem ==============================================================  failures ==
:err_no_backend_dir
echo   Project layout problem: no "backend" folder next to this launcher.
echo   Expected: %BACKEND_DIR%
goto :fail

:err_no_frontend_dir
echo   Project layout problem: no "frontend" folder next to this launcher.
echo   Expected: %FRONTEND_DIR%
goto :fail

:err_no_venv
echo   Python virtual environment not found.
echo   Expected: %VENV_PY%
echo   Create it once with:
echo       cd backend
echo       python -m venv .venv
echo       .venv\Scripts\python.exe -m pip install -r requirements.txt
echo       .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
goto :fail

:err_no_node_modules
echo   Frontend dependencies not found.
echo   Expected: %FRONTEND_DIR%\node_modules
echo   Install them once with:
echo       cd frontend
echo       npm install
goto :fail

:err_no_npm
echo   "npm" was not found on PATH, so the frontend cannot be started.
echo   Install Node.js, or start the frontend manually from a shell that has it.
goto :fail

:err_backend
echo(
if "%BACKEND_STARTED%"=="0" goto :err_backend_port
echo   Backend failed to start.
echo   Check the backend terminal for details.
echo   (The window is titled "GeneVerify Backend"; it stays open on purpose, so
echo    the traceback is still on screen - nothing was swallowed here.)
echo   Common causes: a bad backend\.env, or port %BACKEND_PORT% conflicting.
goto :show_backend_port

:err_backend_port
echo   Backend failed to start.
echo   Port %BACKEND_PORT% is already taken by a program that does not answer the
echo   GeneVerify health endpoint %HEALTH_URL%, so the backend was
echo   deliberately not started on top of it (that is what avoids duplicates).
echo   If that program is an older GeneVerify backend, run:
echo       Stop GeneVerify.bat
echo   and then start this launcher again.
:show_backend_port
echo   Something to look at: what is listening on port %BACKEND_PORT% right now
echo   (last column is the process id, visible in Task Manager too):
netstat -ano | findstr /I "LISTENING" | findstr /R /C:":%BACKEND_PORT% "
goto :fail

:err_frontend
echo(
if "%FRONTEND_STARTED%"=="0" goto :err_frontend_port
echo   Frontend failed to start.
echo   Check the frontend terminal for details.
echo   (The window is titled "GeneVerify Frontend"; it stays open on purpose, so
echo    the vite error is still on screen - nothing was swallowed here.)
echo   Note: Vite keeps port %FRONTEND_PORT% only if it is free - if something
echo   else already holds it, the dev server would move to another port and the
echo   backend CORS allow-list (http://localhost:%FRONTEND_PORT%) would not match.
goto :show_frontend_port

:err_frontend_port
echo   Frontend failed to start.
echo   Port %FRONTEND_PORT% is already taken by a program that is not serving the
echo   GeneVerify frontend at %APP_URL%, so no second frontend was started.
echo   If it is an older Vite dev server, run:  Stop GeneVerify.bat
:show_frontend_port
echo   Something to look at: what is listening on port %FRONTEND_PORT% right now
netstat -ano | findstr /I "LISTENING" | findstr /R /C:":%FRONTEND_PORT% "
goto :fail

:fail
echo(
echo   Nothing was deleted and no data was changed; the services that did start
echo   are still running. To stop them:  Stop GeneVerify.bat
echo(
pause
goto :finish

:finish
popd
endlocal
exit /b 0
