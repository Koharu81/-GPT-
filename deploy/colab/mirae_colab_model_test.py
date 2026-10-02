import os
from pathlib import Path

MODEL_PATH = Path(os.getenv("MIRAE_MODEL_PATH", "/content/drive/MyDrive/Mirae_AI/models/Mirae-Qwen2.5-1.5B-Instruct"))
MODEL_NAME = "Mirae-Qwen2.5-1.5B-Instruct"
MAX_NEW_TOKENS = 512

print("Mirae Colab model test")
print("MODEL_PATH =", MODEL_PATH)
print("exists =", MODEL_PATH.exists())

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        "모델 폴더가 없습니다. Google Drive의 MyDrive/Mirae_AI/models/ "
        "아래에 Mirae-Qwen2.5-1.5B-Instruct 폴더를 업로드하세요."
    )

required = [
    "config.json",
    "generation_config.json",
    "merges.txt",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
]
missing = [name for name in required if not (MODEL_PATH / name).exists()]
if missing:
    raise FileNotFoundError("누락된 모델 파일: " + ", ".join(missing))

print("필수 모델 파일 확인 완료")
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

print("torch =", torch.__version__)
print("cuda available =", torch.cuda.is_available())
if not torch.cuda.is_available():
    raise RuntimeError("GPU가 활성화되지 않았습니다. Colab에서 런타임 유형의 GPU를 선택하세요.")

print("GPU =", torch.cuda.get_device_name(0))

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH,
    local_files_only=True,
    trust_remote_code=False,
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH,
    local_files_only=True,
    trust_remote_code=False,
    torch_dtype=torch.float16,
).to("cuda")
model.eval()

print("model loaded =", True)
print("model name =", MODEL_NAME)
def generate(message: str, max_new_tokens: int = MAX_NEW_TOKENS) -> str:
    messages = [
        {
            "role": "system",
            "content": "You are Mirae AI, a general-purpose assistant. Answer naturally in the user's language.",
        },
        {"role": "user", "content": message},
    ]
    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
    )
    if hasattr(inputs, "items"):
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        input_ids = inputs["input_ids"]
    else:
        input_ids = inputs.to(model.device)
        inputs = {"input_ids": input_ids}

    with torch.inference_mode():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated = output[0][input_ids.shape[-1]:]
    return tokenizer.decode(generated, skip_special_tokens=True).strip()


tests = [
    "안녕하세요. Mirae AI가 무엇인지 한 문장으로 설명해줘.",
    "日本語で短く自己紹介してください。",
    "Explain what an API is in one short paragraph.",
]

for i, prompt in enumerate(tests, 1):
    print(f"\n===== TEST {i} =====")
    print("USER:", prompt)
    print("MIRAE:", generate(prompt))

print("\nCUDA memory allocated:", round(torch.cuda.memory_allocated() / 1024**3, 2), "GB")
print("CUDA memory reserved:", round(torch.cuda.memory_reserved() / 1024**3, 2), "GB")
print("\n모델 GPU 실행 검증 완료")
