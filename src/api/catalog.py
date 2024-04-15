from fastapi import APIRouter
import sqlalchemy
from src import database as db
import sqlalchemy
from src import database as db

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    # Updated SQL to fetch inventory details for all potion types
    sql_to_execute = """
    SELECT num_green_potions, num_green_ml, num_red_potions, num_red_ml, num_blue_potions, num_blue_ml, gold
    FROM global_inventory;
    """

    potions_for_sale = []

    with db.engine.connect() as connection:
        result = connection.execute(sqlalchemy.text(sql_to_execute))
        inventory_data = result.fetchone() 
        print(inventory_data)

        if inventory_data:
            # Access results by column index
            num_green_potions, num_green_ml, num_red_potions, num_red_ml, num_blue_potions, num_blue_ml, gold = inventory_data

            # Check and append green potions if available
            if num_green_potions > 0:
                potions_for_sale.append({
                    "sku": "GREEN_POTION_1",
                    "name": "green potion",
                    "quantity": num_green_potions,
                    "price": 100,
                    "potion_type": [0, 100, 0, 0], 
                })

            # Check and append red potions if available
            if num_red_potions > 0:
                potions_for_sale.append({
                    "sku": "RED_POTION_1",
                    "name": "red potion",
                    "quantity": num_red_ml,
                    "price": 100, 
                    "potion_type": [100, 0, 0, 0],
                })

            # Check and append blue potions if available
            if num_blue_potions > 0:
                potions_for_sale.append({
                    "sku": "BLUE_POTION_1",
                    "name": "blue potion",
                    "quantity": num_blue_potions,
                    "price": 100,  
                    "potion_type": [0, 0, 100, 0],
                })

    return potions_for_sale
