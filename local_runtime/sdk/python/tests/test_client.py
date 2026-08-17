import json
from io import BytesIO
from unittest.mock import patch

from mirae_ai import MiraeClient


class FakeResponse:
    def __init__(self, body: dict): self.body = body
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self): return json.dumps(self.body).encode("utf-8")


def test_client_sends_bearer_and_returns_reply():
    with patch("mirae_ai.client.urlopen", return_value=FakeResponse({"choices": [{"message": {"content": "반가워요."}}]})) as opener:
        client = MiraeClient("mirae_test")
        assert client.reply("안녕") == "반가워요."
        assert opener.call_args.args[0].headers["Authorization"] == "Bearer mirae_test"
