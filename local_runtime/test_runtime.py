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
        local_chat = client.post("/api/chat", json={"message": "Hello"})
        assert local_chat.status_code == 200
        history = client.get("/api/history", params={"query": "Hello"}).json()
        assert len(history) == 2
        user_history = next(item for item in history if item["role"] == "user")
        assert client.post(f"/api/history/{user_history['id']}/reuse").status_code == 200
        with runtime.db() as connection:
            connection.execute("INSERT INTO model_versions (user_id, version, label, dataset_records, requested_steps, parameter_count, train_loss, validation_loss, artifact_path, is_active, created_at) VALUES (1, 'mirae-v1', '첫 모델', 30, 500, 100, 2.0, 3.1, '/tmp/mirae-v1/checkpoints/latest.pt', 0, ?)", (runtime.now(),))
            connection.execute("INSERT INTO model_versions (user_id, version, label, dataset_records, requested_steps, parameter_count, train_loss, validation_loss, artifact_path, is_active, created_at) VALUES (1, 'mirae-v2', '두 번째 모델', 60, 1000, 200, 1.5, 2.6, '/tmp/mirae-v2/checkpoints/latest.pt', 1, ?)", (runtime.now(),))
        versions = client.get("/api/models").json()
        assert len(versions) == 2
        comparison = client.get("/api/models/compare", params={"left": versions[1]["id"], "right": versions[0]["id"]})
        assert comparison.status_code == 200
        assert comparison.json()["deltas"]["dataset_records"] == 30
        original_model_reply, used_artifacts = runtime.model_reply, []
        try:
            runtime.model_reply = lambda _message, _pairs, artifact_dir=None: (str(artifact_dir), "checkpoint")
            responses = client.post("/api/models/respond", json={"left": versions[1]["id"], "right": versions[0]["id"], "message": "Hello"})
            assert responses.status_code == 200
            assert responses.json()["left"]["reply"] == "/tmp/mirae-v1"
            assert responses.json()["right"]["reply"] == "/tmp/mirae-v2"
        finally:
            runtime.model_reply = original_model_reply
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
