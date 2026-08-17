"""Dependency-free client for the locally running Mirae AI Studio API."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


@dataclass
class MiraeApiError(Exception):
    message: str
    status: int
    body: Any = None

    def __str__(self) -> str:
        return self.message


class MiraeClient:
    def __init__(self, api_key: str, base_url: str = "http://127.0.0.1:8000") -> None:
        if not api_key.strip():
            raise ValueError("api_key is required.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def chat(self, message: str) -> dict[str, Any]:
        if not message.strip():
            raise ValueError("message is required.")
        payload = json.dumps({"message": message}).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/v1/chat/completions",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310 - caller controls only local base URL.
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raw = error.read().decode("utf-8")
            try:
                body = json.loads(raw)
                message = str(body.get("detail", raw))
            except json.JSONDecodeError:
                body, message = raw, raw or error.reason
            raise MiraeApiError(message, error.code, body) from error

    def reply(self, message: str) -> str:
        completion = self.chat(message)
        return str(completion.get("choices", [{}])[0].get("message", {}).get("content", ""))
