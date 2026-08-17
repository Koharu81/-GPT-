# Mirae AI Local SDK

두 SDK 모두 로컬 런처가 실행 중인 `http://127.0.0.1:8000`을 기본값으로 사용하며, 외부 AI 서비스에 요청을 보내지 않습니다. 웹 패널에서 발급한 API 키를 사용하세요.

| 라이브러리 | 시작 파일 | 기본 사용 |
|---|---|---|
| TypeScript | `typescript/src/index.ts` | `new MiraeClient({ apiKey }).reply(message)` |
| Python | `python/mirae_ai` | `MiraeClient(api_key).reply(message)` |

## TypeScript

`typescript` 폴더에서 `pnpm install` 후 `pnpm check`와 `pnpm test`를 실행할 수 있습니다. 실제 앱에서는 `src/index.ts`를 프로젝트에 복사하거나 번들링 설정에 포함하세요.

## Python

`python` 폴더에서 `PYTHONPATH=. python examples/chat.py`를 실행합니다. 이 클라이언트는 Python 표준 라이브러리만 사용합니다.
