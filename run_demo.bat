@echo off
setlocal enabledelayedexpansion
title S3 ML 기반 자재 수요 예측 - 데모 서버
cd /d "%~dp0"

echo ============================================================
echo  S3 ML 기반 자재 수요 예측 - 데모 서버
echo ============================================================
echo.

set "PY=.venv\Scripts\python.exe"

rem --- 1) 가상환경 확인 (없으면 생성) --------------------------
if not exist "%PY%" (
    echo [1/4] 가상환경이 없어 새로 만듭니다. 잠시 기다려 주세요...
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if not exist "%PY%" (
        echo.
        echo [오류] 가상환경을 만들지 못했습니다.
        echo        Python 3.10 이상이 설치되어 있는지 확인하세요.
        echo        https://www.python.org/downloads/  ^(설치 시 Add to PATH 체크^)
        goto :fail
    )
    echo [1/4] 패키지를 설치합니다...
    "%PY%" -m pip install --upgrade pip >nul
    "%PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [오류] 패키지 설치에 실패했습니다. 네트워크 또는 사내 프록시 설정을 확인하세요.
        goto :fail
    )
) else (
    echo [1/4] 가상환경 확인 완료
)
echo.

rem --- 2) 환경 점검 --------------------------------------------
echo [2/4] 실행 환경 점검
"%PY%" tools\check_env.py
if errorlevel 1 (
    echo.
    echo [중단] 위 항목을 먼저 해결한 뒤 다시 실행하세요.
    goto :fail
)
echo.

rem --- 3) 포트 선택 --------------------------------------------
set "PORT="
for /f "delims=" %%p in ('"%PY%" tools\check_env.py --port-only') do set "PORT=%%p"
if "%PORT%"=="" set "PORT=8000"
if "%PORT%"=="0" (
    echo [오류] 사용 가능한 포트가 없습니다. 실행 중인 서버 창을 닫고 다시 시도하세요.
    goto :fail
)
echo [3/4] 사용 포트: %PORT%
echo.

rem --- 4) 서버 실행 + 브라우저 열기 -----------------------------
echo [4/4] 서버를 시작합니다. 브라우저가 자동으로 열립니다.
echo       종료하려면 이 창에서 Ctrl+C 를 누르거나 창을 닫으세요.
echo ------------------------------------------------------------
start "" "http://127.0.0.1:%PORT%/"
"%PY%" -m uvicorn backend.app:app --port %PORT%

echo.
echo 서버가 종료되었습니다.
pause
exit /b 0

:fail
echo.
pause
exit /b 1
