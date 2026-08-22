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

    # @pytest.mark.parametrize('_,input_filename,output_match', [
    #     ('regular_event', './tests/test_event.json', {"responses": [
    #         {"bucket": "test-bucket", "event": "s3:ObjectCreated:Put", "key": "image.jpg"}]}),
    #     ('sparse_event', './tests/test_event_sparse.json',
    #      {'responses': [{'bucket': 'amzn-s3-demo-bucket', 'event': 's3:TestEvent'}]}),
    #     ('regular_bucket_event', './tests/test_event_no_key.json', {}),
    # ])
    # def test_load(self, _, input_filename: str, output_match: dict):
    #     test_client = TestClient(app)
    #     with open(input_filename) as _t:
    #         body = json.load(_t)
    #         resp = test_client.post("/load", json=body)
    #         assert resp.status_code == 200
    #         assert resp.json() == output_match
