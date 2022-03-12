from fastapi.testclient import TestClient

from starling_server.server.app import app

client = TestClient(app)


def test_accounts():
    response = client.get("/accounts")
    data = response.json()

    assert response.status_code == 200
    assert isinstance(data, list)
    assert "uuid" in data[0]


def test_accounts_balance():
    response = client.get("/accounts/balances")
    data = response.json()

    assert response.status_code == 200
    assert isinstance(data, list)
    assert "cleared_balance" in data[0]