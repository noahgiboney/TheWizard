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
    # Filter out and sum the quantity of green potions
    green_potions_quantity = sum(potion.quantity for potion in potions_delivered if potion.potion_type == [0, 100, 0, 0])

    # If there are green potions to add, update the database
    if green_potions_quantity > 0:
        with db.engine.begin() as connection:
            # Prepare the SQL command to update the inventory
            sql_to_execute = "UPDATE global_inventory SET num_green_potions = num_green_potions + :quantity_added"
            # Execute the command with the calculated quantity
            connection.execute(sqlalchemy.text(sql_to_execute), {'quantity_added': green_potions_quantity})

    print(f"Potions delivered: {potions_delivered}, Order ID: {order_id}")
    return "OK"

@router.post("/plan")
def get_bottle_plan():
    ml_per_potion = 50  # Assuming each potion needs 50ml to be created

    # Fetch the current amount of green potion ml available
    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("SELECT num_green_ml FROM global_inventory"))
        inventory_data = result.fetchone()

    if not inventory_data:
        print("Inventory data not found.")
        return []

    num_green_ml = inventory_data[0]

    # Calculate how many green potions can be bottled
    potions_to_bottle = num_green_ml // ml_per_potion

    # Update the inventory to reflect the bottled potions
    if potions_to_bottle > 0:
        with db.engine.begin() as connection:
            # Updating the num_green_ml to reflect the used material
            new_num_green_ml = num_green_ml - (potions_to_bottle * ml_per_potion)
            connection.execute(sqlalchemy.text("UPDATE global_inventory SET num_green_ml = :new_ml"), {'new_ml': new_num_green_ml})

            # Optionally, also update the num_green_potions if tracking bottled potions separately
            connection.execute(sqlalchemy.text("UPDATE global_inventory SET num_green_potions = num_green_potions + :potions_added"), {'potions_added': potions_to_bottle})

    # Return the bottling plan for green potions
    return [
        {
            "potion_type": [0, 100, 0, 0],  # Representing green potions
            "quantity": potions_to_bottle,
        }
    ]

if __name__ == "__main__":
    print(get_bottle_plan())