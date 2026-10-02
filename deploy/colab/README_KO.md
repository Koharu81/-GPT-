# Mirae AI — Google Colab 모델 실행용 구성

## 현재 구조

Mirae의 공개 웹앱은 계속 Vercel에서 실행합니다.
공개 API와 계정 기능은 별도 서버에 둡니다.
Neon PostgreSQL은 그대로 사용합니다.
Resend 이메일 인증도 그대로 사용합니다.
Google Colab은 로컬 Qwen 모델을 GPU로 실행하고 검증하는 용도로 사용합니다.

중요: Google Colab 관리형 런타임은 일반 공개 웹서비스 호스팅 용도로 사용할 수 없습니다.
따라서 Colab의 FastAPI 포트를 인터넷에 공개해서 mirae.koharu.live가 직접 호출하는 구조는 사용하지 않습니다.

## 옮길 파일

필수 소스:
- deploy/api/main.py
- deploy/api/requirements.txt
- deploy/local_qwen_server.py
- deploy/local_qwen_requirements.txt

필수 모델:
- C:\\Users\\L\\Downloads\\AI\\Mirae_AI_Studio_Local\\models\\Mirae-Qwen2.5-1.5B-Instruct\\

모델 폴더의 config.json, generation_config.json, merges.txt, model.safetensors,
tokenizer.json, tokenizer_config.json, vocab.json, LICENSE, README.md를 유지합니다.

.git, node_modules, __pycache__, .venv, logs, 테스트 결과물은 Colab 모델 실행에 필요하지 않습니다.
## 절대로 같이 옮길 필요가 없는 것

frontend는 deploy/web에 있습니다.
현재 공개 웹앱은 Vercel이 담당하므로 Colab으로 옮기지 않습니다.

client/, server/, shared/, drizzle/은 현재 공개 Mirae 배포의 Colab 모델 실행에 필요한 파일이 아닙니다.

local_runtime/ 전체도 이번 모델 실행에는 필요하지 않습니다.
특히 local_runtime에는 현재 미커밋 작업이 있으므로 통째로 복사하거나 git add . 하지 않습니다.

Neon 데이터베이스 자체도 복사하지 않습니다.
기존 계정, 세션, 설정, 대화 기록, API 키는 Neon에 남아 있어야 합니다.

Resend 설정도 복사하지 않습니다.
RESEND_API_KEY와 RESEND_FROM은 공개 API 서버의 환경변수로 유지합니다.

## 모델 파일 크기

현재 model.safetensors는 약 3.09 GB입니다.
따라서 일반적인 Colab 파일 업로드보다 Google Drive에 모델 폴더를 보관하고 Colab에서 Drive를 mount하는 방식이 편합니다.

권장 Drive 경로:
/content/drive/MyDrive/Mirae_AI/models/Mirae-Qwen2.5-1.5B-Instruct

Colab에서 최종 모델 경로:
MODEL_PATH=/content/drive/MyDrive/Mirae_AI/models/Mirae-Qwen2.5-1.5B-Instruct
## PC → Google Drive 이동

1. Windows 탐색기에서 아래 폴더를 엽니다.
C:\\Users\\L\\Downloads\\AI\\Mirae_AI_Studio_Local\\models\\Mirae-Qwen2.5-1.5B-Instruct

2. 폴더 전체를 Google Drive의 다음 위치에 업로드합니다.
My Drive/Mirae_AI/models/Mirae-Qwen2.5-1.5B-Instruct

3. 폴더 내부에 최소한 다음 파일이 있는지 확인합니다.
config.json
generation_config.json
merges.txt
model.safetensors
tokenizer.json
tokenizer_config.json
vocab.json

4. Colab에서 Google Drive를 mount합니다.
5. /content/drive/MyDrive/Mirae_AI/models/... 경로가 존재하는지 검사합니다.
6. GPU가 활성화되어 있는지 검사합니다.
7. 모델을 로드하고 테스트 문장을 생성합니다.

## 코드 변경

deploy/api/main.py는 모델 공급자를 환경변수로 분리했습니다.
기본값은 기존 Hugging Face Router이므로 기존 Railway 동작을 깨지 않습니다.

새 환경변수:
MODEL_API_URL
MODEL_API_KEY
MODEL_NAME

따라서 기존 Railway에서는 HF_TOKEN을 그대로 사용해도 됩니다.
Colab용 로컬 모델 서버를 별도로 운영하는 환경에서는 MODEL_API_URL을 로컬 OpenAI-compatible endpoint로 지정할 수 있도록 코드가 준비되어 있습니다.
다만 관리형 Colab의 공개 웹서비스 제한 때문에 이 endpoint를 인터넷에 공개해서 운영하지 않습니다.

## 웹앱 연결

공개 웹앱은 계속 https://mirae.koharu.live 를 사용합니다.
현재 /api/* 요청은 Vercel rewrite를 통해 공개 API 서버로 전달됩니다.

관리형 Colab을 공개 API로 연결하는 것은 이번 구성에서 하지 않습니다.
Colab에서 모델을 검증한 뒤 실제 공개 API 서버에 같은 모델을 배포하는 단계가 별도로 필요합니다.

## Colab의 한계

Colab 런타임은 영구 서버가 아닙니다.
무료 환경에서는 사용량과 GPU 종류가 보장되지 않고 런타임 수명도 제한됩니다.
따라서 서비스의 회원가입, 로그인, 세션, DB, 이메일, API 키를 Colab 파일시스템에 의존시키면 안 됩니다.
## 확인 순서

1. GPU 확인
2. Drive mount
3. 모델 파일 존재 확인
4. transformers/torch 설치
5. tokenizer 로드
6. model 로드
7. 한국어 생성 테스트
8. 일본어 생성 테스트
9. 영어 생성 테스트
10. 긴 답변 테스트
11. GPU 메모리 확인

성공 기준:
- model.safetensors를 정상 로드한다.
- CUDA가 True다.
- 생성 결과가 빈 문자열이 아니다.
- 모델이 Mirae-Qwen2.5-1.5B-Instruct로 표시된다.

## 배포 전후 구분

Colab 단계는 '모델이 실제 GPU에서 정상 생성되는가'를 검증하는 단계입니다.
공개 서비스 단계는 'Mirae FastAPI가 Neon/Resend/API Key/Streaming/Web Search까지 정상 처리하는가'를 검증하는 단계입니다.
두 계층을 분리하면 Colab 런타임이 종료되어도 사용자 계정과 데이터가 사라지지 않습니다.
