from customer_importer import import_customers

def test_import_single_customer():
    customers = import_customers(
        "sample.csv"
    )
    assert len(customers) == 3
    
    
def test_customer_name_loaded():
    customers = import_customers(
        "sample.csv"
    )
    assert (
        customers[0]["name"]
        == "Peter"
    )
