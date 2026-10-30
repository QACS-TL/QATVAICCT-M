import csv
from pathlib import Path

import pytest

from customer_importer import import_customers

FIELDNAMES = ["customer_id", "name", "email"]

def write_customers(path, rows):
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

def test_import_single_customer():
    customers = import_customers(
        str(Path(__file__).with_name("sample.csv"))
    )
    assert len(customers) == 3
    
  
def test_customer_name_loaded():
    customers = import_customers(
        str(Path(__file__).with_name("sample.csv"))
    )
    assert (
        customers[0]["name"]
        == "Peter"
    )

def test_rejects_duplicate_customer_ids(tmp_path):
    file_path = tmp_path / "customers.csv"
    write_customers(
        file_path,
        [
            {"customer_id": "1000", "name": "Peter", "email": "peter@example.com"},
            {"customer_id": "1000", "name": "Other", "email": "other@example.com"},
            {"customer_id": "1001", "name": "Sadia", "email": "sadia@example.com"},
        ],
    )

    customers = import_customers(str(file_path))

    assert [customer["customer_id"] for customer in customers] == ["1000", "1001"]

def test_rejects_duplicate_email_addresses(tmp_path):
    file_path = tmp_path / "customers.csv"
    write_customers(
        file_path,
        [
            {"customer_id": "1000", "name": "Peter", "email": "same@example.com"},
            {"customer_id": "1001", "name": "Sadia", "email": "same@example.com"},
            {"customer_id": "1002", "name": "Bisi", "email": "bisi@example.com"},
        ],
    )

    customers = import_customers(str(file_path))

    assert [customer["customer_id"] for customer in customers] == ["1000", "1002"]

def test_rejects_malformed_row_and_continues(tmp_path):
    file_path = tmp_path / "customers.csv"
    file_path.write_text(
        "customer_id,name,email\n"
        "1000,Peter,peter@example.com\n"
        "1001,Sadia,sadia@example.com,unexpected-value\n"
        "1002,Bisi,bisi@example.com\n",
        encoding="utf-8",
    )

    customers = import_customers(str(file_path))

    assert [customer["customer_id"] for customer in customers] == ["1000", "1002"]

@pytest.mark.parametrize(
    "row",
    [
        {"customer_id": "", "name": "Peter", "email": "peter@example.com"},
        {"customer_id": "1000", "name": "", "email": "peter@example.com"},
        {"customer_id": "1000", "name": "Peter", "email": ""},
    ],
)

def test_rejects_rows_with_blank_mandatory_fields(tmp_path, row):
    file_path = tmp_path / "customers.csv"
    write_customers(
        file_path,
        [
            {"customer_id": "999", "name": "Valid", "email": "valid@example.com"},
            row,
            {"customer_id": "1001", "name": "Also Valid", "email": "also@example.com"},
        ],
    )

    customers = import_customers(str(file_path))

    assert [customer["customer_id"] for customer in customers] == ["999", "1001"]

@pytest.mark.parametrize("email", ["plainaddress", "missing-at.example.com"])
def test_rejects_invalid_email_addresses(tmp_path, email):
    file_path = tmp_path / "customers.csv"
    write_customers(
        file_path,
        [
            {"customer_id": "1000", "name": "Invalid", "email": email},
            {"customer_id": "1001", "name": "Valid", "email": "valid@example.com"},
        ],
    )

    customers = import_customers(str(file_path))

    assert [customer["customer_id"] for customer in customers] == ["1001"]

def test_logs_rejected_rows_and_continues(tmp_path, caplog):
    file_path = tmp_path / "customers.csv"
    write_customers(
        file_path,
        [
            {"customer_id": "1000", "name": "Peter", "email": "peter@example.com"},
            {"customer_id": "1001", "name": "Invalid", "email": "not-an-email"},
            {"customer_id": "1002", "name": "Bisi", "email": "bisi@example.com"},
        ],
    )

    customers = import_customers(str(file_path))

    assert [customer["customer_id"] for customer in customers] == ["1000", "1002"]
    assert any("1001" in record.message for record in caplog.records)

def test_imports_more_than_50000_records(tmp_path):
    file_path = tmp_path / "large_customers.csv"
    with file_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(
            {
                "customer_id": str(customer_id),
                "name": f"Customer {customer_id}",
                "email": f"customer{customer_id}@example.com",
            }
            for customer_id in range(50_001)
        )

    customers = import_customers(str(file_path))

    assert len(customers) == 50_001
    assert customers[0]["customer_id"] == "0"
    assert customers[-1]["customer_id"] == "50000"

def test_raises_and_logs_file_error_when_input_file_does_not_exist(tmp_path, caplog):
    file_path = tmp_path / "missing.csv"

    with pytest.raises(FileNotFoundError):
        import_customers(str(file_path))

    assert any("Could not open customer file" in record.message for record in caplog.records)


def test_source_row_number_tracks_csv_record_position(tmp_path):
    file_path = tmp_path / "customers.csv"
    write_customers(
        file_path,
        [
            {"customer_id": "1000", "name": "Peter", "email": "peter@example.com"},
            {"customer_id": "", "name": "Invalid", "email": "invalid@example.com"},
            {"customer_id": "1002", "name": "Bisi", "email": "bisi@example.com"},
        ],
    )

    customers = import_customers(str(file_path))

    assert [customer["source_row_number"] for customer in customers] == [2, 4]


def test_handles_utf8_bom_in_header(tmp_path):
    file_path = tmp_path / "customers.csv"
    file_path.write_text(
        "\ufeffcustomer_id,name,email\n"
        "1000,Peter,peter@example.com\n",
        encoding="utf-8",
    )

    customers = import_customers(str(file_path))

    assert len(customers) == 1
    assert customers[0]["customer_id"] == "1000"


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("", "no header row"),
        ("customer_id,name\n1000,Peter\n", "missing required columns"),
    ],
)
def test_logs_header_errors_and_returns_no_records(tmp_path, caplog, contents, message):
    file_path = tmp_path / "customers.csv"
    file_path.write_text(contents, encoding="utf-8")

    assert import_customers(str(file_path)) == []
    assert any(message in record.message for record in caplog.records)


def test_rejects_duplicate_headers_and_logs_error(tmp_path, caplog):
    file_path = tmp_path / "customers.csv"
    file_path.write_text(
        "customer_id,name,email,email\n"
        "1000,Peter,peter@example.com,other@example.com\n",
        encoding="utf-8",
    )

    assert import_customers(str(file_path)) == []
    assert any("duplicate columns" in record.message for record in caplog.records)


def test_rejects_short_row_and_continues(tmp_path, caplog):
    file_path = tmp_path / "customers.csv"
    file_path.write_text(
        "customer_id,name,email\n"
        "1000,Peter,peter@example.com\n"
        "1001,Sadia\n"
        "1002,Bisi,bisi@example.com\n",
        encoding="utf-8",
    )

    customers = import_customers(str(file_path))

    assert [customer["customer_id"] for customer in customers] == ["1000", "1002"]
    assert any("row 3" in record.message for record in caplog.records)


def test_trims_customer_ids_and_email_addresses_for_duplicates(tmp_path):
    file_path = tmp_path / "customers.csv"
    write_customers(
        file_path,
        [
            {
                "customer_id": " 1000 ",
                "name": "Peter",
                "email": " Peter@Example.com ",
            },
            {
                "customer_id": "1000",
                "name": "Duplicate ID",
                "email": "other@example.com",
            },
            {
                "customer_id": "1002",
                "name": "Duplicate email",
                "email": "peter@example.COM",
            },
        ],
    )

    customers = import_customers(str(file_path))

    assert len(customers) == 1
    assert customers[0]["customer_id"] == "1000"
    assert customers[0]["email"] == "Peter@Example.com"


def test_preserves_name_whitespace_when_trimming_identifiers(tmp_path):
    file_path = tmp_path / "customers.csv"
    write_customers(
        file_path,
        [
            {
                "customer_id": "1000",
                "name": "  Peter  ",
                "email": "peter@example.com",
            }
        ],
    )

    customers = import_customers(str(file_path))

    assert customers[0]["name"] == "  Peter  "
