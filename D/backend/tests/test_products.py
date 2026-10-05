from fastapi.testclient import TestClient


def test_get_product_returns_options_and_all_skus(client: TestClient) -> None:
    res = client.get("/api/products/classic-tee")

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == "classic-tee"
    assert body["name"] and body["description"]
    assert [o["name"] for o in body["options"]] == ["colour", "size"]
    assert body["options"][0]["values"] == ["Black", "Blue", "Red"]
    assert len(body["skus"]) >= 6

    skus = {(s["options"]["colour"], s["options"]["size"]): s for s in body["skus"]}
    blue_m = skus[("Blue", "M")]
    assert blue_m == {
        "id": "TEE-BLU-M",
        "product_id": "classic-tee",
        "price_cents": 3190,
        "available_quantity": 4,
        "image_url": "/static/images/tee-blue.svg",
        "options": {"colour": "Blue", "size": "M"},
    }


def test_seed_contains_required_edge_cases(client: TestClient) -> None:
    skus = client.get("/api/products/classic-tee").json()["skus"]
    combos = {(s["options"]["colour"], s["options"]["size"]): s for s in skus}

    assert ("Blue", "XL") not in combos  # combination that does not exist
    assert combos[("Blue", "S")]["available_quantity"] == 0  # exists but out of stock
    assert len({s["price_cents"] for s in skus}) > 1
    assert len({s["image_url"] for s in skus}) > 1


def test_unknown_product_returns_structured_404(client: TestClient) -> None:
    res = client.get("/api/products/does-not-exist")

    assert res.status_code == 404
    assert res.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


def test_unknown_route_returns_structured_404(client: TestClient) -> None:
    res = client.get("/api/nope")

    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"
