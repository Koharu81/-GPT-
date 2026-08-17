"""소형 한국어·영어 언어 모델 학습 명령줄 인터페이스."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import random
import time

import torch

from .config import ModelConfig
from .data import build_corpus_split, collate_language_model_batch, dataset_sha256
from .model import DecoderOnlyTransformer
from .tokenizer import CharacterTokenizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="처음부터 학습하는 소형 한국어·영어 챗봇")
    parser.add_argument("--data", type=Path, default=Path("data/raw/bootstrap_dialogues.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--eval-interval", type=int, default=25)
    parser.add_argument("--eval-batches", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--max-seq-len", type=int, default=128)
    parser.add_argument("--d-model", type=int, default=192)
    parser.add_argument("--n-heads", type=int, default=6)
    parser.add_argument("--n-layers", type=int, default=4)
    return parser.parse_args()


def resolve_device(requested: str) -> torch.device:
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA를 요청했지만 사용할 수 있는 CUDA 장치가 없습니다.")
    return torch.device(requested)


def set_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


@torch.no_grad()
def estimate_loss(
    model: DecoderOnlyTransformer,
    sequences: list[list[int]],
    *,
    batch_size: int,
    pad_id: int,
    device: torch.device,
    batches: int,
    seed: int,
) -> float:
    model.eval()
    rng = random.Random(seed)
    losses: list[float] = []
    for _ in range(batches):
        inputs, targets = collate_language_model_batch(
            sequences, batch_size, pad_id=pad_id, device=device, rng=rng
        )
        _, loss = model(inputs, targets)
        assert loss is not None
        losses.append(float(loss.item()))
    model.train()
    return sum(losses) / len(losses)


def save_checkpoint(
    path: Path,
    *,
    model: DecoderOnlyTransformer,
    optimizer: torch.optim.Optimizer,
    config: ModelConfig,
    step: int,
    training_loss: float,
    validation_loss: float,
    data_path: Path,
) -> None:
    payload = {
        "model_state": model.state_dict(),
        "optimizer_state": optimizer.state_dict(),
        "model_config": config.to_dict(),
        "step": step,
        "training_loss": training_loss,
        "validation_loss": validation_loss,
        "data_path": str(data_path),
        "data_sha256": dataset_sha256(data_path),
    }
    torch.save(payload, path)


def main() -> None:
    args = parse_args()
    if args.steps <= 0 or args.batch_size <= 0:
        raise ValueError("steps와 batch-size는 양수여야 합니다.")
    set_seed(args.seed)
    device = resolve_device(args.device)
    tokenizer = CharacterTokenizer.train_from_jsonl(args.data)
    config = ModelConfig(
        vocab_size=tokenizer.vocab_size,
        max_seq_len=args.max_seq_len,
        d_model=args.d_model,
        n_heads=args.n_heads,
        n_layers=args.n_layers,
    )
    corpus = build_corpus_split(args.data, tokenizer, max_seq_len=config.max_seq_len, seed=args.seed)
    model = DecoderOnlyTransformer(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.01)
    rng = random.Random(args.seed)

    checkpoint_dir = args.output_dir / "checkpoints"
    tokenizer_dir = args.output_dir / "tokenizer"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    tokenizer.save(tokenizer_dir)

    print(
        f"device={device.type} parameters={model.parameter_count():,} "
        f"train_sequences={len(corpus.train_sequences)} validation_sequences={len(corpus.validation_sequences)}"
    )
    started_at = time.perf_counter()
    history: list[dict[str, float | int]] = []
    latest_train_loss = float("nan")
    latest_validation_loss = float("nan")

    model.train()
    for step in range(1, args.steps + 1):
        inputs, targets = collate_language_model_batch(
            corpus.train_sequences,
            args.batch_size,
            pad_id=tokenizer.pad_id,
            device=device,
            rng=rng,
        )
        optimizer.zero_grad(set_to_none=True)
        _, loss = model(inputs, targets)
        assert loss is not None
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        latest_train_loss = float(loss.item())

        if step == 1 or step % args.eval_interval == 0 or step == args.steps:
            latest_validation_loss = estimate_loss(
                model,
                corpus.validation_sequences,
                batch_size=args.batch_size,
                pad_id=tokenizer.pad_id,
                device=device,
                batches=args.eval_batches,
                seed=args.seed + step,
            )
            elapsed = time.perf_counter() - started_at
            entry = {
                "step": step,
                "train_loss": latest_train_loss,
                "validation_loss": latest_validation_loss,
                "elapsed_seconds": elapsed,
            }
            history.append(entry)
            print(
                f"step={step:>4d} train_loss={latest_train_loss:.4f} "
                f"validation_loss={latest_validation_loss:.4f} elapsed={elapsed:.1f}s"
            )

    checkpoint_path = checkpoint_dir / "latest.pt"
    save_checkpoint(
        checkpoint_path,
        model=model,
        optimizer=optimizer,
        config=config,
        step=args.steps,
        training_loss=latest_train_loss,
        validation_loss=latest_validation_loss,
        data_path=args.data,
    )
    run_metadata = {
        "training_arguments": vars(args) | {"data": str(args.data), "output_dir": str(args.output_dir)},
        "model_config": config.to_dict(),
        "model_parameters": model.parameter_count(),
        "device": device.type,
        "dataset_sha256": dataset_sha256(args.data),
        "train_sequences": len(corpus.train_sequences),
        "validation_sequences": len(corpus.validation_sequences),
        "history": history,
    }
    (args.output_dir / "last_run.json").write_text(
        json.dumps(run_metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"checkpoint={checkpoint_path}")


if __name__ == "__main__":
    main()
