"""Tests for order DB helpers (no GUI)."""

import json
import os

import pytest

from ufprint import orders


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_orders.db")
    monkeypatch.setattr(orders, "DB_NAME", db_path)
    orders.init_db()
    return db_path


def test_init_db_creates_file(temp_db):
    assert os.path.isfile(temp_db)


def test_encode_decode_print_specs():
    data = {"quantity": 50, "print_type": "УФ печать"}
    encoded = orders.encode_print_specs(data)
    assert isinstance(encoded, str)
    decoded = orders.decode_print_specs(encoded)
    assert decoded["quantity"] == 50
    assert decoded["print_type"] == "УФ печать"


def test_decode_print_specs_invalid():
    assert orders.decode_print_specs("") == {}
    assert orders.decode_print_specs(None) == {}
    assert orders.decode_print_specs("not-json") == {}


def test_insert_and_list_orders(temp_db):
    oid = orders.insert_order(
        customer_name="Иван",
        customer_phone="+7",
        customer_email="a@b.c",
        company_name="ООО Тест",
        print_specs={"quantity": 10, "print_type": "Цифровая печать"},
        side_a_path="/a.png",
        side_b_path="/b.png",
        status="Черновик",
    )
    assert oid >= 1

    rows = orders.list_orders()
    assert len(rows) == 1
    order_id, customer, company, _date, specs_json, status = rows[0]
    assert order_id == oid
    assert customer == "Иван"
    assert company == "ООО Тест"
    assert status == "Черновик"
    assert json.loads(specs_json)["quantity"] == 10


def test_get_order_row(temp_db):
    oid = orders.insert_order(
        customer_name="Петр",
        customer_phone="",
        customer_email="",
        company_name="Co",
        print_specs={"quantity": 1},
        side_a_path="a.png",
        side_b_path="",
    )
    row = orders.get_order(oid)
    assert row is not None
    assert row["customer_name"] == "Петр"
    assert row["side_a_path"] == "a.png"
    assert orders.get_order(99999) is None
