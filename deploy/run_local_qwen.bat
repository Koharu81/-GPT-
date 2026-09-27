@echo off
setlocal
cd /d "%~dp0.."
if "%QWEN_MODEL_PATH%"=="" set "QWEN_MODEL_PATH=C:\Users\L\Downloads\AI\Mirae_AI_Studio_Local\models\Mirae-Qwen2.5-1.5B-Instruct"
if "%MODEL_NAME%"=="" set "MODEL_NAME=Mirae-Qwen2.5-1.5B-Instruct"
if "%MODEL_API_KEY%"=="" (
  echo Enter a private key for the local model endpoint.
  set /p "MODEL_API_KEY=MODEL_API_KEY: "
)
python -m uvicorn deploy.local_qwen_server:app --host 127.0.0.1 --port 8002
pause
