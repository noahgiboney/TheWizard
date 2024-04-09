from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)

class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    # find all green potions
    green_potions_quantity = sum(potion.quantity for potion in potions_delivered if potion.potion_type == [0, 100, 0, 0])

    green_ml_used = green_potions_quantity * 100

    # update the database with green potions and subtract the used ml
    if green_potions_quantity > 0:
        with db.engine.begin() as connection:
            # update potions in db
            sql_update_potions = """
                UPDATE global_inventory 
                SET num_green_potions = num_green_potions + :quantity_added
            """
            connection.execute(sqlalchemy.text(sql_update_potions), {'quantity_added': green_potions_quantity})

            # upadate ml in the db
            sql_update_ml = """
                UPDATE global_inventory 
                SET num_green_ml = num_green_ml - :ml_used
                WHERE num_green_ml >= :ml_used
            """
            connection.execute(sqlalchemy.text(sql_update_ml), {'ml_used': green_ml_used})

    print(f"Potions delivered: {potions_delivered}, Order ID: {order_id}")
    return "OK"

@router.post("/plan")
def get_bottle_plan():
    # fetch the current volume of green potion liquid that is available
    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("SELECT num_green_ml FROM global_inventory"))
        inventory_data = result.fetchone()
    
    if not inventory_data:
        print("Inventory data not found.")
        return {"error": "Inventory data not found."}

    num_green_ml = inventory_data[0]
    
    # calculate how many bottles can be made
    potions_to_bottle = num_green_ml // 100  

    return [
        {
            "potion_type": [0, 100, 0, 0], 
            "quantity": potions_to_bottle,
        }
    ]

if __name__ == "__main__":
    print(get_bottle_plan())