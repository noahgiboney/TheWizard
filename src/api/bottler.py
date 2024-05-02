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

from fastapi import APIRouter
import sqlalchemy

@router.post("/plan")
def get_bottle_plan():
     with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("SELECT COALESCE(SUM(quantity_change), 0) FROM potion_ledger"))
        total_existing_potions = result.scalar()

        if total_existing_potions >= 50:
            print("DEBUG: No bottling needed, sufficient stock available.")
            return []

        sql = "SELECT COALESCE(SUM(red_change), 0), COALESCE(SUM(green_change), 0), COALESCE(SUM(blue_change), 0), COALESCE(SUM(dark_change), 0) FROM ml_ledger"
        result = connection.execute(sqlalchemy.text(sql))
        inventory_data = result.fetchone()
        inventory = [amount or 0 for amount in inventory_data]

        recipes_result = connection.execute(sqlalchemy.text("SELECT red, green, blue, dark, id FROM potions"))
        recipes = {row.id: [row.red, row.green, row.blue, row.dark] for row in recipes_result}

        bottle_plan = []
        max_total_bottles = 50 - total_existing_potions
        potion_capacities = {potion_id: min(inventory[i] // required_material if required_material > 0 else float('inf') for i, required_material in enumerate(recipe)) for potion_id, recipe in recipes.items() if any(recipe)}

        total_capacity = sum(potion_capacities.values())

        if total_capacity == 0:
            print("DEBUG: No materials available for bottling.")
            return []

        for potion_id, max_bottles in sorted(potion_capacities.items(), key=lambda x: x[1], reverse=True):
            if max_total_bottles == 0:
                break
            allocated_bottles = int((max_bottles / total_capacity) * max_total_bottles)
            allocated_bottles = min(allocated_bottles, max_bottles, max_total_bottles)
            if allocated_bottles > 0:
                bottle_plan.append({"potion_type": recipes[potion_id], "quantity": allocated_bottles})
                max_total_bottles -= allocated_bottles

        print(f"DEBUG: BOTTLE PLAN: {bottle_plan}")
        return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())