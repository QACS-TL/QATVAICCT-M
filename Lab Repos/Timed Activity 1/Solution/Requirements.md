# The importer must:
- Load customer_id, name and email.
- Reject duplicate customer_id values.
- Reject duplicate email addresses.
- Email addresses must contain "@".
- Rows with missing mandatory fields must be rejected.
- Import should continue when invalid rows are encountered.
- Errors should be logged.
- Imported records should include the source row number.
- Files larger than 50,000 records must be supported.
