"""학습 코퍼스에서 직접 어휘를 만드는 문자 단위 토크나이저.

각 Unicode 문자를 하나의 토큰으로 사용한다. 한국어와 영어 혼합 데이터에서
유효하지 않은 UTF-8 바이트열이 생성되는 문제를 피하며, 외부 어휘·모델 파일은
일절 사용하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

PAD = 0
BOS = 1
EOS = 2
UNK = 3
SEP = 4
SPECIAL_TOKENS = {
    "pad": PAD,
    "bos": BOS,
    "eos": EOS,
    "unk": UNK,
    "sep": SEP,
}


@dataclass(frozen=True)
class CharacterTokenizer:
    """훈련 데이터 문자 집합만으로 구성되는 재현 가능한 토크나이저."""

    token_to_id: dict[str, int]
    id_to_token: dict[int, str]
    pad_id: int = PAD
    bos_id: int = BOS
    eos_id: int = EOS
    unk_id: int = UNK
    sep_id: int = SEP

    @property
    def vocab_size(self) -> int:
        return len(self.token_to_id) + len(SPECIAL_TOKENS)

    @classmethod
    def from_texts(cls, texts: Iterable[str]) -> "CharacterTokenizer":
        characters = sorted({character for text in texts for character in text})
        token_to_id = {character: index + len(SPECIAL_TOKENS) for index, character in enumerate(characters)}
        id_to_token = {index: character for character, index in token_to_id.items()}
        return cls(token_to_id=token_to_id, id_to_token=id_to_token)

    @classmethod
    def train_from_jsonl(cls, path: str | Path) -> "CharacterTokenizer":
        """대화 JSONL의 역할 표식과 본문을 포함해 문자 어휘를 직접 만든다."""
        role_prefix = {"user": "사용자: ", "prompter": "사용자: ", "assistant": "어시스턴트: "}
        texts: list[str] = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            messages = record.get("messages", [])
            formatted: list[str] = []
            for message in messages:
                role = str(message.get("role", "")).strip().lower()
                text = str(message.get("text", "")).strip()
                if role in role_prefix and text:
                    formatted.append(f"{role_prefix[role]}{text}")
            if formatted:
                texts.append("\n".join(formatted))
        if not texts:
            raise ValueError("토크나이저를 학습할 유효한 텍스트가 없습니다.")
        return cls.from_texts(texts)

    def encode(self, text: str, *, add_bos: bool = False, add_eos: bool = False) -> list[int]:
        ids = [self.token_to_id.get(character, self.unk_id) for character in text]
        if add_bos:
            ids.insert(0, self.bos_id)
        if add_eos:
            ids.append(self.eos_id)
        return ids

    def decode(self, token_ids: Iterable[int], *, skip_special_tokens: bool = True) -> str:
        output: list[str] = []
        for raw_token_id in token_ids:
            token_id = int(raw_token_id)
            if token_id in self.id_to_token:
                output.append(self.id_to_token[token_id])
            elif token_id == self.unk_id and not skip_special_tokens:
                output.append("□")
        return "".join(output)

    def save(self, directory: str | Path) -> Path:
        output_dir = Path(directory)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "tokenizer.json"
        payload = {
            "type": "character",
            "vocab_size": self.vocab_size,
            "special_tokens": SPECIAL_TOKENS,
            "token_to_id": self.token_to_id,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    @classmethod
    def load(cls, directory: str | Path) -> "CharacterTokenizer":
        path = Path(directory) / "tokenizer.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("type") != "character":
            raise ValueError("지원하지 않는 토크나이저 설정입니다.")
        token_to_id = {str(token): int(index) for token, index in payload["token_to_id"].items()}
        id_to_token = {index: token for token, index in token_to_id.items()}
        return cls(token_to_id=token_to_id, id_to_token=id_to_token)


# 이전 실험 코드와의 호환성을 위한 별칭이다. 새 코드에서는 CharacterTokenizer를 사용한다.
ByteTokenizer = CharacterTokenizer
