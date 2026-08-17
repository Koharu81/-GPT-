"""모델과 학습 설정 정의."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ModelConfig:
    """초기 실험에 적합한 작은 디코더 전용 Transformer 설정.

    기본값은 약 5M 파라미터 안팎을 목표로 한다. 데이터가 극히 작을 때는
    `d_model`, `n_layers`, `max_seq_len`을 더 낮춰 파이프라인만 검증한다.
    """

    vocab_size: int = 261
    max_seq_len: int = 128
    d_model: int = 192
    n_heads: int = 6
    n_layers: int = 4
    dropout: float = 0.1
    ff_multiplier: int = 4

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)
