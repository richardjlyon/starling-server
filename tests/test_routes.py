from fastapi.testclient import TestClient

from server.app import app

client = TestClient(app)


def test_accounts():
    response = client.get("/accounts")
    data = response.json()

    assert response.status_code == 200
    assert isinstance(data, list)
    assert "uuid" in data[0]
