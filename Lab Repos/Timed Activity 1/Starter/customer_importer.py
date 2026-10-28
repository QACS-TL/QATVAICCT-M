import csv
 
 
def import_customers(file_path: str)->list[dict[str:str]]:
    customers = []
    with open(file_path) as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            customers.append(
                {
                "customer_id": row["customer_id"],
                "name": row["name"],
                "email": row["email"]
                }
            )
        
        return customers
