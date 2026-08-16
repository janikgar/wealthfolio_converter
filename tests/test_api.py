import os
import json
import pytest
from fastapi.testclient import TestClient
from wealthfolio_converter.api.main import create_app, app


class TestApi:
    def test_read_root(self):
        test_client = TestClient(app)
        resp = test_client.get("/")
        assert resp.status_code == 200
        assert resp.json() == {"health": "ok"}

    @pytest.mark.parametrize("_,endpoint,stage,status", [
        ("docs", "/docs", "DEV", 200),
        ("redoc", "/redoc", "DEV", 200),
        ("docs_prod", "/docs", "PRODUCTION", 404),
        ("redoc_prod", "/redoc", "PRODUCTION", 404),
    ])
    def test_docs(self, _, endpoint, stage: str, status: int):
        # using a mock app to ensure STAGE is honored
        os.environ["STAGE"] = stage
        test_app = create_app()
        test_client = TestClient(test_app)
        resp = test_client.get(endpoint)
        assert resp.status_code == status

    def test_load(self):
        test_client = TestClient(app)
        with open("./tests/test_event.json") as _t:
            body = json.load(_t)
            resp = test_client.post("/load", json=body)
            assert resp.status_code == 200
            assert resp.json() == {"responses": [
                {"bucket": "test-bucket", "key": "image.jpg"}]}
