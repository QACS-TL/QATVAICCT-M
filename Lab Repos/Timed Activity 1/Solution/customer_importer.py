import csv
import logging
from collections import Counter


logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ("customer_id", "name", "email")


def import_customers(file_path: str) -> list[dict[str, str | int]]:
    customers: list[dict[str, str | int]] = []
    seen_customer_ids: set[str] = set()
    seen_emails: set[str] = set()

    try:
        file = open(file_path, newline="", encoding="utf-8-sig")
    except OSError:
        logger.exception("Could not open customer file %s", file_path)
        raise

    with file:
        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            logger.error("Customer file %s has no header row", file_path)
            return customers

        duplicate_headers = [
            field
            for field, count in Counter(reader.fieldnames).items()
            if count > 1
        ]
        if duplicate_headers:
            logger.error(
                "Customer file %s has duplicate columns: %s",
                file_path,
                ", ".join(sorted(duplicate_headers)),
            )
            return customers

        missing_headers = set(REQUIRED_FIELDS).difference(reader.fieldnames)
        if missing_headers:
            logger.error(
                "Customer file %s is missing required columns: %s",
                file_path,
                ", ".join(sorted(missing_headers)),
            )
            return customers

        for row_number, row in enumerate(reader, start=2):
            extra_values = row.get(None)
            if extra_values:
                logger.warning(
                    "Skipping customer row %s: contains unexpected extra values",
                    row_number,
                )
                continue

            values = {field: row.get(field) for field in REQUIRED_FIELDS}
            missing_fields = [
                field
                for field, value in values.items()
                if value is None or not value.strip()
            ]
            if missing_fields:
                logger.warning(
                    "Skipping customer row %s: missing required values for %s",
                    row_number,
                    ", ".join(missing_fields),
                )
                continue

            customer_id = values["customer_id"].strip()
            email = values["email"].strip()
            if "@" not in email:
                logger.warning(
                    "Skipping customer row %s: email address for customer_id %s "
                    "must contain '@'",
                    row_number,
                    customer_id,
                )
                continue

            if customer_id in seen_customer_ids:
                logger.warning(
                    "Skipping customer row %s: duplicate customer_id %s",
                    row_number,
                    customer_id,
                )
                continue

            email_key = email.casefold()
            if email_key in seen_emails:
                logger.warning(
                    "Skipping customer row %s: duplicate email address %s",
                    row_number,
                    email,
                )
                continue

            seen_customer_ids.add(customer_id)
            seen_emails.add(email_key)
            customers.append(
                {
                    "customer_id": customer_id,
                    "name": values["name"],
                    "email": email,
                    "source_row_number": row_number,
                }
            )

    return customers
