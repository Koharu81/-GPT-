# Mirae AI Studio Local

Mirae AI Studio Local은 **외부 추론 API 없이** 개인 PC에서 대화 데이터, 소형 Transformer, API 키, 외부 POST 엔드포인트를 직접 운영하는 로컬 웹 서비스입니다. 이 패키지에는 한국어·영어 혼합의 자체 작성 스타터 대화 30쌍과, 그 대화로 학습한 초기 소형 모델 체크포인트가 포함됩니다.

> 초기 모델은 약 65만 개 파라미터의 실험용 소형 모델입니다. 사람처럼 폭넓은 지식이나 상용 챗봇 수준의 품질을 제공하지 않습니다. 학습 데이터와 일치하는 질문에는 검증된 대화 쌍을 우선 반환하고, 새로운 주제에는 직접 학습 모델 또는 정직한 로컬 안내 응답을 사용합니다.

## 1. 설치와 첫 실행

압축 파일을 아래 위치에 풉니다.

```text
C:\Users\L\Downloads\AI
```

그 폴더 안의 `run_mirae.bat`를 더블 클릭합니다. 처음 실행할 때만 Python 가상환경과 패키지를 설치하므로 인터넷 연결이 필요합니다. 설치가 끝나면 기본 브라우저에서 `http://127.0.0.1:8000`이 열립니다. 이 주소는 **내 PC에서만 동작**하며, 외부 서버로 데이터가 전송되지 않습니다.

Python 3.11 이상이 설치되어 있지 않다면 [Python 공식 다운로드 페이지](https://www.python.org/downloads/)에서 설치한 후 다시 실행하세요. 설치 화면에서는 **Add Python to PATH** 옵션을 선택하는 편이 편리합니다.

> 이 패키지의 서버 코드, 로그인, API 키 인증, JSONL 처리, 직접 학습 체크포인트 로드는 Linux 검증 환경에서 자동 테스트했습니다. 다만 Windows 전용 `.bat` 파일은 이 검증 환경에서 실제 실행할 수 없으므로, Windows에서 처음 실행할 때 `run_mirae.bat`를 더블 클릭한 뒤 브라우저가 열리고 관리자 생성 화면이 나타나는지 확인해 주세요. 문제가 있으면 런처 창의 마지막 오류 메시지를 보관하세요.

## 2. 첫 사용자 만들기

처음 열린 화면에서 사용자 이름과 8자 이상 비밀번호를 입력하면 로컬 관리자 계정이 만들어집니다. 계정·학습 데이터·API 키의 해시는 `data/mirae.db` SQLite 파일에 저장됩니다. 이 파일과 API 키를 다른 사람에게 보내지 마세요.

## 3. 추가 학습 시작하기

학습 데이터 화면에서 **스타터 30쌍** 버튼을 먼저 누릅니다. 이 대화들은 프로젝트를 위해 직접 작성한 한국어·영어 혼합 예시입니다. 그 후 직접 만든 대화 쌍을 추가하거나 수정하고, 학습 관찰 화면에서 1,000스텝부터 시작해 보세요.

| 단계 | 권장 행동 | 이유 |
|---|---|---|
| 1 | 스타터 30쌍 가져오기 | 대화 형식·두 언어·공감형 말투의 최소 기반을 만듭니다. |
| 2 | 자신만의 대화 50–100쌍 추가 | 당신의 게임, 프로젝트, 말투에 맞는 특징을 제공합니다. |
| 3 | 1,000–2,000스텝으로 학습 | 초기 과적합을 확인하며 짧은 실험을 반복합니다. |
| 4 | JSONL 내보내기 | 어떤 데이터로 모델을 만들었는지 보관하고 검토합니다. |

학습은 `data/training_pairs.jsonl`을 만들고 PyTorch로 체크포인트를 갱신합니다. GTX 1050 Ti 4GB에서는 다른 고사양 작업을 닫고 시작하는 것을 권합니다. 학습 중에는 로컬 런처 창을 닫지 마세요.

## 4. API 키와 외부 POST 요청

API 키 페이지에서 키 이름을 입력해 키를 발급합니다. 전체 키는 **생성 직후 한 번만 표시**되며, 서버에는 SHA-256 해시만 저장됩니다. 키는 `Authorization: Bearer` 또는 `X-API-Key` 헤더로 전달할 수 있습니다.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/chat/completions \
  -H "Authorization: Bearer YOUR_MIRAE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"안녕하세요. Hello!\"}"
```

응답은 아래처럼 `choices[0].message.content`에 텍스트를 담습니다.

```json
{
  "object": "chat.completion",
  "model": "mirae-local-small",
  "mode": "local-data",
  "choices": [
    {"index": 0, "message": {"role": "assistant", "content": "..."}}
  ]
}
```

## 5. 보안과 운영 범위

이 패키지는 기본적으로 `127.0.0.1`에만 바인딩합니다. 즉, 같은 PC의 Unity, Godot, Python, Node 프로그램은 API를 호출할 수 있지만 인터넷에서 직접 접근할 수는 없습니다. 원격 공개가 필요하다면 인증·HTTPS·방화벽을 별도로 설계해야 하며, API 키가 포함된 저장소나 화면 캡처를 공개하면 안 됩니다.

관리자 화면은 이 로컬 설치에서 만든 첫 계정에만 열립니다. 여러 사람이 하나의 서버를 함께 쓰는 서비스로 확장하려면 역할 관리, 비밀번호 재설정, 세션 영속화, 속도 제한, 감사 로그를 추가로 강화해야 합니다.

## 6. 포함된 검증 결과

| 항목 | 결과 |
|---|---|
| React/TypeScript 웹 패널 타입 검사 | 통과 |
| 웹 패널 서버 단위 테스트 | 4개 통과 |
| 로컬 FastAPI 로그인·데이터·키·POST 엔드포인트 흐름 테스트 | 통과 |
| 직접 학습 체크포인트 로드 점검 | 통과 |

## 7. 데이터 원칙

대화 기록, 개인정보, 저작권 제한 자료를 본인 또는 작성자의 명시적 동의 없이 학습 데이터에 넣지 마세요. 스타터 대화는 프로젝트 자체 작성 자료이며, 일반 사용자의 후기·평가·증언을 흉내 내거나 포함하지 않습니다.

## 8. 확장 모델과 버전 비교

이번 패키지는 두 개의 직접 학습 모델 버전을 포함합니다. 첫 모델은 30개 스타터 대화로 500스텝을 학습했고, 두 번째 모델은 기존 30개와 추가로 작성한 75개 대화를 합친 **105개 대화 쌍**으로 2,000스텝을 학습했습니다. 두 번째 모델은 약 66만 8천 개 파라미터이며, 학습 로그 기준 마지막 학습 손실은 1.1908, 검증 손실은 2.8705였습니다. 검증 손실은 800스텝 부근에서 가장 낮았으므로, 다음 학습에서는 더 다양한 데이터를 추가하고 800–1,200스텝 구간도 함께 비교하는 편이 좋습니다.

대화 요청은 `chat_history`에 사용자·어시스턴트 쌍으로 저장됩니다. `GET /api/history?query=단어`로 검색할 수 있으며, `GET /api/models`와 `GET /api/models/compare?left=1&right=2`로 모델 메타데이터와 손실·데이터 수 차이를 확인할 수 있습니다.

대화 기록은 `POST /api/history/{history_id}/reuse`로 **검토용 학습 초안**에 다시 넣을 수 있습니다. 초안은 곧바로 학습하지 않으므로 학습 데이터 화면에서 문장을 확인한 뒤 승인하세요. 두 버전에 같은 질문을 보낼 때는 `POST /api/models/respond`에 `left`, `right`, `message`를 보내면 각 체크포인트의 응답을 나란히 받을 수 있습니다.

## 9. TypeScript와 Python SDK

`sdk/` 폴더에는 외부 의존성이 없는 API 클라이언트 라이브러리와 예제가 포함됩니다.

```ts
import { MiraeClient } from "./sdk/typescript/src/index.js";

const mirae = new MiraeClient({ apiKey: "YOUR_MIRAE_API_KEY" });
console.log(await mirae.reply("안녕하세요. Hello!"));
```

```python
from mirae_ai import MiraeClient

mirae = MiraeClient(api_key="YOUR_MIRAE_API_KEY")
print(mirae.reply("안녕하세요. Hello!"))
```

TypeScript SDK는 `sdk/typescript`에서 `pnpm install`, `pnpm check`, `pnpm test`를 실행할 수 있습니다. Python SDK는 `sdk/python`에서 `PYTHONPATH=. pytest -q tests/test_client.py`로 검증할 수 있습니다. 두 SDK 모두 `POST /api/v1/chat/completions`에 Bearer API 키를 보내며, 키나 대화 내용을 외부 AI 서비스로 전달하지 않습니다.
