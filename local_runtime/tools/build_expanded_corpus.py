"""Create an expanded project-authored bilingual dialogue corpus for Mirae AI Studio."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "starter_dialogues.jsonl"
OUTPUT = ROOT / "expanded_dialogues.jsonl"

CURATED_PAIRS = [
    ("오늘은 아무것도 하기 싫어.", "그럴 수 있어요. 해야 할 일을 없애기보다, 지금의 에너지를 기준으로 가장 작은 행동 하나만 골라 볼까요?"),
    ("I keep comparing my project to bigger games.", "Large games were also built from small scenes. Compare your work to yesterday's build, not to someone else's finished journey."),
    ("플레이어가 길을 잃지 않게 하려면?", "정답을 화살표로 모두 보여주기보다, 빛·소리·시선이 자연스럽게 다음 장소를 가리키게 해 보세요."),
    ("What makes an NPC memorable?", "Give the NPC a small contradiction: brave about one thing, hesitant about another. Contradictions make dialogue feel human."),
    ("내 코드는 지저분한 것 같아.", "지저분함을 발견했다는 건 다음 정리의 기준이 생겼다는 뜻이에요. 한 함수 이름부터 더 분명하게 바꿔 보세요."),
    ("Can you help me name a game scene?", "Describe its mood, movement, and one strange object. A name often appears where those three meet."),
    ("혼자 만들면 너무 느린 느낌이야.", "속도보다 리듬을 만드는 것이 더 중요할 수 있어요. 매주 한 가지 보이는 결과를 남기는 리듬을 시도해 보세요."),
    ("I am afraid players will not understand my story.", "Let the player understand one feeling before every detail. Emotion can carry the story while the mystery remains."),
    ("게임 UI가 너무 복잡해.", "화면에서 플레이어가 지금 가장 자주 결정하는 한 가지를 찾으세요. 그 결정에 필요 없는 요소부터 조용히 빼 보세요."),
    ("Explain delta time simply.", "Delta time is the time that passed since the last frame. Multiplying movement by it keeps motion consistent across different frame rates."),
    ("오늘 한 줄도 못 썼어.", "한 줄을 못 쓴 날에도 문제를 생각하고 있었다면 작업은 완전히 멈춘 것이 아니에요. 내일은 파일을 여는 것부터 시작해요."),
    ("How do I reduce scope?", "Keep the feeling, remove the furniture. Preserve the one interaction that makes the idea special and cut surrounding complexity."),
    ("AI한테 내 말투를 가르치고 싶어.", "자주 쓰는 인사, 생각이 바뀔 때 쓰는 말, 위로할 때 쓰는 문장을 모으세요. 말투는 반복되는 선택에서 드러납니다."),
    ("What should I log while debugging?", "Log the input, the state before the change, and the state after it. Three small facts are more useful than a wall of output."),
    ("기획이 자꾸 바뀌어.", "바뀌는 아이디어는 별도 메모로 옮기고, 이번 주에 검증할 한 가지 가설만 현재 작업에 남겨 보세요."),
    ("I want my chatbot to sound warm, not fake.", "Use specific listening before reassurance. Reflect one detail the person shared, then offer a gentle next step without pretending certainty."),
    ("레벨 디자인이 비어 보인다.", "모든 공간을 오브젝트로 채울 필요는 없어요. 의도적인 빈 공간은 플레이어에게 호흡과 다음 선택을 줍니다."),
    ("Can you explain state machines?", "A state machine names the modes an object can be in, such as idle, running, or jumping, and defines when it may move between them."),
    ("나는 시작은 잘하는데 끝을 못 내.", "끝내는 기준이 너무 멀리 있을 수 있어요. 오늘의 완료 조건을 '동작하는 작은 장면 하나'처럼 작게 다시 써 보세요."),
    ("How do I make a tutorial feel natural?", "Teach through a meaningful action. Let the first task solve a real problem in the world rather than pause the game for instructions."),
    ("영어로 말하면 자신감이 없어.", "Perfect grammar is not the entrance fee for a conversation. Use short sentences first, then add detail when you feel ready."),
    ("What is a good API response?", "A good API response is predictable: clear status, stable fields, useful errors, and no secret information leaking into the client."),
    ("모델이 이상한 답을 하면 어떻게 해?", "먼저 어떤 질문에서 어떤 답이 나왔는지 기록하세요. 그다음 원하는 답을 대화 쌍으로 추가하고 짧게 다시 학습해 보세요."),
    ("I need a short break but feel guilty.", "A deliberate break is part of sustainable work. Set a small timer, rest fully, then return to one defined task."),
    ("게임의 첫 10초가 중요해?", "중요해요. 첫 10초에는 조작 하나, 감정 하나, 궁금증 하나를 남겨 보세요. 설명보다 경험이 먼저입니다."),
    ("What is overfitting?", "Overfitting happens when a model memorizes its training examples too closely and struggles with new inputs. More varied data helps."),
    ("내 AI가 모른다고 말하게 하고 싶어.", "좋은 방향이에요. 모르는 정보를 만들지 않도록, '확신할 수 없어요'와 '더 알려주실래요?' 같은 예시를 함께 학습시키세요."),
    ("How can I test a game mechanic quickly?", "Build the ugliest playable version first. If the core action feels good with simple shapes, art can amplify it later."),
    ("사람들이 내 작품을 싫어할까 봐 무서워.", "모든 사람에게 맞는 작품은 없어요. 대신 어떤 한 사람이 오래 기억할 감정을 만들고 싶은지 생각해 볼 수 있어요."),
    ("Explain JSONL in Korean.", "JSONL은 한 줄에 하나의 JSON 객체를 넣는 형식입니다. 많은 대화 데이터를 줄 단위로 저장하고 처리하기에 편리합니다."),
    ("내가 만든 데이터가 충분한지 어떻게 알아?", "같은 질문을 반복하기보다 다양한 상황, 감정, 표현, 그리고 원하는 거절·불확실성 응답이 들어 있는지 확인해 보세요."),
    ("How should an AI respond to a vague question?", "It can answer the part it understands, state the ambiguity briefly, and ask one focused follow-up question."),
    ("버그를 설명하는 게 어려워.", "기대했던 결과, 실제 결과, 재현 순서 세 가지를 짧게 적어 보세요. 그 자체로 훌륭한 버그 보고서가 됩니다."),
    ("I want a cozy game atmosphere.", "Use a slow rhythm, forgiving feedback, warm sound layers, and small signs that the world notices the player."),
    ("오늘 작업한 걸 잊어버릴까 봐 걱정돼.", "마무리 전에 '오늘 바꾼 것, 막힌 것, 내일 첫 행동'을 세 줄로 남겨 보세요. 내일의 시작이 훨씬 가벼워집니다."),
    ("What does a model version mean?", "A model version is a named snapshot of training data, settings, and weights. It lets you compare progress instead of guessing."),
    ("캐릭터가 왜 이 선택을 하는지 모르겠어.", "그 선택으로 캐릭터가 지키려는 것과 잃을까 봐 두려운 것을 적어 보세요. 동기는 그 사이에서 선명해집니다."),
    ("Can you help me make a daily plan?", "Choose one must-do task, one small maintenance task, and one kind thing for yourself. Keep the list short enough to finish."),
    ("내 AI 프로젝트가 너무 거창해 보여.", "첫 버전은 '한 사람이 한 가지 질문에 도움이 되는 작은 도구'면 충분해요. 작은 약속을 지키며 확장할 수 있습니다."),
    ("How do I protect an API key?", "Keep it on the server or in local secrets, never commit it to source control, and revoke it immediately if it is exposed."),
    ("한국어 답변이 어색해.", "학습 데이터에 자연스러운 한국어 대화 쌍을 더하고, 존댓말과 반말 중 하나의 기준을 정해서 일관되게 보여 주세요."),
    ("What is a checkpoint?", "A checkpoint saves a model's learned weights and training state so you can test, compare, or continue later without starting over."),
    ("작품 소개 문장을 못 쓰겠어.", "'누구를 위해, 어떤 감정을, 어떤 방식으로' 만들었는지 한 문장으로 먼저 적어 보세요. 화려한 표현은 나중에 더해도 됩니다."),
    ("I made a mistake in front of my team.", "Mistakes are easier to repair when named plainly. Say what happened, what you learned, and the next action you will take."),
    ("게임 사운드는 언제 넣어야 해?", "핵심 조작이 안정된 뒤라도 너무 늦기 전에 넣어 보세요. 소리는 행동의 느낌을 바꾸므로 디자인 판단을 더 정확하게 해 줍니다."),
    ("How do I make a search feature useful?", "Search should return the most relevant words with enough context to understand them, and it should clearly show when no result exists."),
    ("오늘은 집중이 안 돼.", "집중을 강요하기보다 방해를 하나만 줄여 보세요. 창 하나를 닫고, 10분 타이머를 켜는 것만으로도 충분할 수 있어요."),
    ("What should I compare between model versions?", "Compare dataset size, training steps, validation loss, safety behavior, and a fixed set of representative prompts."),
    ("내 게임의 감정을 말로 설명하고 싶어.", "플레이어가 떠날 때 남았으면 하는 한 장면을 묘사해 보세요. 그 장면이 감정의 언어가 됩니다."),
    ("Can a small model still be useful?", "Yes. A small model can be useful when its task, language, data, and limits are narrow and carefully designed."),
    ("답변이 너무 길어지는 걸 막고 싶어.", "짧고 좋은 답변의 예시를 데이터에 넣고, 한 문단 뒤에 질문 하나를 덧붙이는 형식을 반복해서 보여 주세요."),
    ("How do I handle negative feedback?", "Separate taste from signal. Look for repeated patterns, thank the person, and decide which feedback serves your intended experience."),
    ("세계관 설정이 너무 많아.", "플레이어가 지금 보는 장면에 필요한 설정만 남기세요. 나머지는 세계가 필요로 할 때 조용히 드러나도 됩니다."),
    ("What is retrieval?", "Retrieval finds relevant stored information before answering. It helps a system reuse trusted notes instead of relying only on generation."),
    ("내 AI에 기억 기능을 넣는 게 무서워.", "기억은 편리함과 책임을 함께 가집니다. 무엇을 저장하는지, 어떻게 찾는지, 언제 지우는지부터 사용자에게 분명히 보여 주세요."),
    ("I want to finish something this week.", "Pick a result you can show in one screenshot or one playable minute. Visible finish lines make a week feel possible."),
    ("대화가 너무 딱딱해.", "답변 앞에 짧은 공감 한 문장을 두고, 정보는 두세 문장으로 나누어 보세요. 리듬이 부드러워질 수 있어요."),
    ("What is a local API?", "A local API is an interface running on your own computer or network. It lets your programs communicate without sending requests to a public service."),
    ("새 기능을 넣고 싶을 때 기준이 뭐야?", "그 기능이 핵심 경험을 더 선명하게 하는지, 아니면 불안을 가리기 위한 장식인지 먼저 물어 보세요."),
    ("Can you be honest when you are unsure?", "Yes. I can say what I know from your local data, what I cannot confirm, and which detail would help me answer better."),
    ("오늘은 아주 작은 성공이 필요해.", "파일을 열고 제목 하나를 바꾸는 것도 성공이에요. 작은 완료는 다음 행동을 부르는 신호가 됩니다."),
    ("How do I make choices matter in a game?", "Let choices change something the player can notice: a relationship, a route, a resource, or the meaning of a later scene."),
    ("데이터를 지우면 모델도 잊어?", "데이터를 지워도 이미 학습된 체크포인트는 남아 있을 수 있어요. 완전히 잊게 하려면 정리된 데이터로 새 모델을 다시 학습해야 합니다."),
    ("What should I do after training?", "Test the model with familiar, slightly changed, and unrelated prompts. Save the results with the version so the next comparison is honest."),
    ("내 작품이 남들과 달라야 한다는 압박이 있어.", "다름은 억지로 만들기보다 당신이 오래 관찰한 것을 솔직하게 담을 때 생기는 경우가 많아요."),
    ("Can you help me write a gentle error message?", "Try: '저장하지 못했어요. 연결을 확인한 뒤 다시 시도해 주세요. 입력한 내용은 그대로 남아 있습니다.'"),
    ("오늘 배운 걸 잊고 싶지 않아.", "배운 내용을 한 줄의 규칙과 한 줄의 예시로 남겨 보세요. 기억은 재사용할 수 있을 때 더 오래 남습니다."),
    ("What does bilingual support mean?", "It means the system can understand and respond across two languages, including mixed messages when the training data demonstrates them."),
    ("내 AI가 내 프로젝트를 응원해 줬으면 해.", "그렇다면 실제로 힘이 됐던 말과, 부담스러웠던 말 모두를 데이터에 넣어 주세요. 좋은 응원은 구체적이고 과장되지 않습니다."),
    ("How can I make an endpoint easy to use?", "Use one clear URL, one authentication method, a small request shape, consistent errors, and copyable examples in common languages."),
    ("테스트가 귀찮지만 필요해.", "테스트는 미래의 나에게 보내는 짧은 편지예요. 중요한 행동 하나만 자동으로 확인해도 변경이 덜 무서워집니다."),
    ("I do not know which idea to choose.", "Choose the idea you can test with the least irreversible work. Learning quickly is more valuable than choosing perfectly."),
    ("엔딩 장면이 약한 것 같아.", "엔딩은 모든 것을 설명하기보다 처음의 질문을 다른 감정으로 다시 보게 하면 오래 남습니다."),
    ("What is an embedding?", "An embedding is a numeric representation that places similar meanings closer together. It is often used for semantic search."),
    ("오늘도 조금만 해도 될까?", "그럼요. 조금만 하는 날을 허락해야 오래 할 수 있어요. 오늘의 '조금'을 구체적으로 정해 볼까요?"),
]


def main() -> None:
    records = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    for index, (prompt, response) in enumerate(CURATED_PAIRS, start=len(records) + 1):
        records.append({"id": f"mirae-expanded-{index:03d}", "source": "project-authored-expanded", "messages": [{"role": "user", "text": prompt}, {"role": "assistant", "text": response}]})
    OUTPUT.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")
    print(f"Wrote {len(records)} project-authored dialogue records to {OUTPUT}")


if __name__ == "__main__":
    main()
