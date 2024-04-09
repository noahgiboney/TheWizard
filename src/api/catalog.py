from fastapi import APIRouter
import sqlalchemy
from src import database as db
import sqlalchemy
from src import database as db

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    # fetch inventory
    sql_to_execute = """
    SELECT num_green_potions, num_green_ml, gold FROM global_inventory;
    """

    potions_for_sale = []

    with db.engine.connect() as connection:
        result = connection.execute(sqlalchemy.text(sql_to_execute))
        inventory_data = result.fetchone() 
        print(inventory_data)

        if inventory_data:
            # acess results by column index
            num_green_potions = inventory_data[0] 
            num_green_ml = inventory_data[1]       
            gold = inventory_data[2]               

            # return response
            if num_green_potions > 0:
                potions_for_sale.append({
                    "sku": "GREEN_POTION_1",
                    "name": "green potion",
                    "quantity": 1,
                    "price": 50, 
                    "potion_type": [0, 100, 0, 0], 
                })

    return potions_for_sale
