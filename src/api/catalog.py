from fastapi import APIRouter
import sqlalchemy
from src import database as db
import sqlalchemy
from src import database as db

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    # SQL query to fetch inventory details
    sql_to_execute = """
    SELECT num_green_potions, num_green_ml, gold FROM global_inventory;
    """

    # Initialize an empty list to hold potion details
    potions_for_sale = []

    # Execute the query
    with db.engine.connect() as connection:
        result = connection.execute(sqlalchemy.text(sql_to_execute))
        inventory_data = result.fetchone()  # Fetches the first row of the result

        # Check if we got any result back
        if inventory_data:
            # Accessing results by column index since dict-style access is not supported here
            num_green_potions = inventory_data[0] 
            num_green_ml = inventory_data[1]       
            gold = inventory_data[2]               

            if num_green_potions > 0:
                potions_for_sale.append({
                    "sku": "GREEN_POTION_1",
                    "name": "green potion",
                    "quantity": num_green_potions,
                    "price": 50,  # Example price, adjust as needed
                    "potion_type": [0, 100, 0, 0],  # Example potion composition, adjust as needed
                })

    return potions_for_sale
