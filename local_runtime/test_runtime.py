from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

import app as runtime


def test_local_studio_core_flow() -> None:
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        runtime.DATA_DIR = root / "data"
        runtime.ARTIFACT_DIR = root / "artifacts"
        runtime.DATA_DIR.mkdir()
        runtime.ARTIFACT_DIR.mkdir()
        runtime.DB_PATH = runtime.DATA_DIR / "mirae.db"
        runtime.sessions.clear()
        runtime.init_db()
        client = TestClient(runtime.app)

        response = client.post("/api/setup", json={"username": "creator", "password": "safe-password-123"})
        assert response.status_code == 200
        assert client.post("/api/pairs", json={"prompt": "Hello", "response": "Hello! 만나서 반가워요."}).status_code == 200
        created_key = client.post("/api/keys", json={"name": "test integration"})
        assert created_key.status_code == 200
        api_key = created_key.json()["key"]

        completion = client.post(
            "/api/v1/chat/completions",
            json={"message": "Hello"},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert completion.status_code == 200
        assert completion.json()["choices"][0]["message"]["content"] == "Hello! 만나서 반가워요."
        assert client.post("/api/v1/chat/completions", json={"message": "Hello"}, headers={"Authorization": "Bearer invalid-key"}).status_code == 401
        with runtime.db() as connection:
            stored_hash = connection.execute("SELECT key_hash FROM api_keys").fetchone()["key_hash"]
        assert stored_hash != api_key
        key_id = client.get("/api/keys").json()[0]["id"]
        assert client.delete(f"/api/keys/{key_id}").status_code == 200
        assert client.post("/api/v1/chat/completions", json={"message": "Hello"}, headers={"Authorization": f"Bearer {api_key}"}).status_code == 401
