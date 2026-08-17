"""Quick post-training check for the bundled directly trained model."""

from app import model_reply


pairs = [{"prompt": "오늘 하루가 조금 길게 느껴져.", "response": "긴 하루를 지나왔군요."}]
reply, mode = model_reply("오늘 하루가 조금 길게 느껴져.", pairs)  # type: ignore[arg-type]
if not reply.strip():
    raise SystemExit("The local model returned an empty response.")
print(f"mode={mode}\nreply={reply}")
