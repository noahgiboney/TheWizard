from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db
from fastapi import HTTPException
import random

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
    print(f"DEBUG POTIONS DELIVERED: {potions_delivered}")

    with db.engine.begin() as connection:
        for potion in potions_delivered:
            red, green, blue, dark = potion.potion_type
            potion_quantity = potion.quantity

            # Get potion ID from the potions table
            sql_get_potion_id = """
                SELECT id FROM potions
                WHERE red = :red AND green = :green AND blue = :blue AND dark = :dark
            """
            result = connection.execute(sqlalchemy.text(sql_get_potion_id), {
                'red': red, 'green': green, 'blue': blue, 'dark': dark
            })
            potion_id = result.scalar()

            if potion_id:
                # Insert records into potion_ledger for the delivered potions
                sql_insert_potion_ledger = """
                    INSERT INTO potion_ledger (potion_id, quantity_change)
                    VALUES (:potion_id, :quantity_change)
                """
                connection.execute(sqlalchemy.text(sql_insert_potion_ledger), {
                    'potion_id': potion_id,
                    'quantity_change': potion_quantity
                })
            else:
                raise HTTPException(status_code=404, detail="Potion not found")

            # Insert a new row into ml_ledger for the change in ML
            sql_insert_ml_ledger = """
                INSERT INTO ml_ledger (red_change, green_change, blue_change, dark_change)
                VALUES (:red_change, :green_change, :blue_change, :dark_change)
            """
            connection.execute(sqlalchemy.text(sql_insert_ml_ledger), {
                'red_change': -red * potion_quantity,
                'green_change': -green * potion_quantity,
                'blue_change': -blue * potion_quantity,
                'dark_change': -dark * potion_quantity
            })

    print(f"DEBUG POTIONS DELIVERED: {potions_delivered}, orderID: {order_id}")
    return {"status": "success", "message": "Delivery processed successfully"}

@router.post("/plan")
def get_bottle_plan():
    with db.engine.begin() as connection:
        # check the total amount of existing potions
        result = connection.execute(sqlalchemy.text("SELECT SUM(quantity_change) FROM potion_ledger"))
        total_existing_potions = result.scalar() or 0

        # bottle nothing if there are already 50 or more potions
        if total_existing_potions >= 50:
            print("DEBUG: No bottling needed, sufficient stock available.")
            return []

        # get current material inventory
        sql = "SELECT SUM(red_change), SUM(green_change), SUM(blue_change), SUM(dark_change) FROM ml_ledger"
        result = connection.execute(sqlalchemy.text(sql))
        inventory_data = result.fetchone()
        inventory = list(inventory_data)

        # get potion recipes from the potions table
        recipes_result = connection.execute(sqlalchemy.text("SELECT red, green, blue, dark, id FROM potions"))
        recipes = { (row.red, row.green, row.blue, row.dark): row.id for row in recipes_result }

        # initialize the bottle plan
        bottle_plan = []
        max_total_bottles = 50

        # calculate bottles based on the recipes from the database
        for recipe, potion_id in recipes.items():
            if total_existing_potions >= max_total_bottles:
                break

            max_bottles = float('inf')
            for i, ratio in enumerate(recipe):
                if ratio > 0:
                    max_bottles = min(max_bottles, inventory[i] // ratio)

            # calculate the number of bottles to produce for this recipe
            max_bottles = min(max_bottles, max_total_bottles - total_existing_potions)

            if max_bottles > 0:
                # update the inventory for used ml
                for i, ratio in enumerate(recipe):
                    if ratio > 0:
                        inventory[i] -= max_bottles * ratio

                bottle_plan.append({"potion_id": potion_id, "quantity": max_bottles})
                total_existing_potions += max_bottles

        print(f"DEBUG: BOTTLE PLAN: {bottle_plan}")
        return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())