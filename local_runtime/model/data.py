"""대화 JSONL을 언어 모델 학습 배치로 변환한다."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
from typing import Iterable

import torch
from torch import Tensor

from .tokenizer import ByteTokenizer

ROLE_PREFIX = {
    "user": "사용자: ",
    "prompter": "사용자: ",
    "assistant": "어시스턴트: ",
}


@dataclass(frozen=True)
class CorpusSplit:
    train_sequences: list[list[int]]
    validation_sequences: list[list[int]]


def load_jsonl(path: str | Path) -> list[dict]:
    records: list[dict] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{line_number}에 올바르지 않은 JSON이 있습니다.") from error
        if not isinstance(record.get("messages"), list) or not record["messages"]:
            raise ValueError(f"{path}:{line_number}에 messages 목록이 없습니다.")
        records.append(record)
    if not records:
        raise ValueError("학습할 대화 레코드가 없습니다.")
    return records


def conversation_to_text(messages: Iterable[dict]) -> str:
    parts: list[str] = []
    for message in messages:
        role = str(message.get("role", "")).strip().lower()
        text = str(message.get("text", "")).strip()
        if role not in ROLE_PREFIX or not text:
            continue
        parts.append(f"{ROLE_PREFIX[role]}{text}")
    if len(parts) < 2:
        raise ValueError("각 대화에는 유효한 사용자/어시스턴트 메시지가 최소 두 개 필요합니다.")
    return "\n".join(parts)


def _record_to_sequences(record: dict, tokenizer: ByteTokenizer, max_seq_len: int) -> list[list[int]]:
    sequence = tokenizer.encode(conversation_to_text(record["messages"]), add_bos=True, add_eos=True)
    window_size = max_seq_len + 1
    if len(sequence) <= window_size:
        return [sequence]
    stride = max(1, max_seq_len // 2)
    windows = [sequence[index : index + window_size] for index in range(0, len(sequence) - 1, stride)]
    return [window for window in windows if len(window) >= 2]


def build_corpus_split(
    path: str | Path,
    tokenizer: ByteTokenizer,
    *,
    max_seq_len: int,
    validation_fraction: float = 0.1,
    seed: int = 42,
) -> CorpusSplit:
    if not 0.0 < validation_fraction < 0.5:
        raise ValueError("validation_fraction은 0과 0.5 사이여야 합니다.")
    records = load_jsonl(path)
    record_ids = [str(record.get("id", index)) for index, record in enumerate(records)]
    shuffled_indices = list(range(len(records)))
    random.Random(seed).shuffle(shuffled_indices)
    validation_count = max(1, round(len(records) * validation_fraction))
    validation_indices = set(shuffled_indices[:validation_count])

    train_sequences: list[list[int]] = []
    validation_sequences: list[list[int]] = []
    for index, record in enumerate(records):
        target = validation_sequences if index in validation_indices else train_sequences
        target.extend(_record_to_sequences(record, tokenizer, max_seq_len))
    if not train_sequences or not validation_sequences:
        joined_ids = ", ".join(record_ids)
        raise ValueError(f"학습/검증 분할에 실패했습니다. 레코드 ID: {joined_ids}")
    return CorpusSplit(train_sequences=train_sequences, validation_sequences=validation_sequences)


def collate_language_model_batch(
    sequences: list[list[int]],
    batch_size: int,
    *,
    pad_id: int,
    device: torch.device,
    rng: random.Random,
) -> tuple[Tensor, Tensor]:
    if not sequences:
        raise ValueError("배치를 만들 시퀀스가 없습니다.")
    selected = [rng.choice(sequences) for _ in range(batch_size)]
    sequence_length = max(len(sequence) for sequence in selected) - 1
    inputs = torch.full((batch_size, sequence_length), pad_id, dtype=torch.long)
    targets = torch.full((batch_size, sequence_length), -100, dtype=torch.long)
    for row, sequence in enumerate(selected):
        inputs[row, : len(sequence) - 1] = torch.tensor(sequence[:-1], dtype=torch.long)
        targets[row, : len(sequence) - 1] = torch.tensor(sequence[1:], dtype=torch.long)
    return inputs.to(device), targets.to(device)


def dataset_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
