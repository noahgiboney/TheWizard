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
    with db.engine.begin() as connection:
        for potion in potions_delivered:
            red, green, blue, dark = potion.potion_type
            potion_quantity = potion.quantity

            # grab id from potions table
            sql_get_potion_id = """
                SELECT id FROM potions
                WHERE red = :red AND green = :green AND blue = :blue AND dark = :dark
            """
            result = connection.execute(sqlalchemy.text(sql_get_potion_id), {
                'red': red, 'green': green, 'blue': blue, 'dark': dark
            })
            potion_id = result.scalar()

            if potion_id:
                # insert records into potion_ledger for the delivered potions
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

            # insert a new row into ml_ledger for the change in ML
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

    print(f"DEBUG POTIONS BOTTLED: {potions_delivered}, orderID: {order_id}")
    return {"status": "success", "message": "Delivery processed successfully"}

from fastapi import APIRouter
import sqlalchemy

@router.post("/plan")
def get_bottle_plan():
    with db.engine.begin() as connection:
        # fetch potion capacity 
        capacity_result = connection.execute(sqlalchemy.text("SELECT potion_capacity FROM capacity LIMIT 1"))
        capacity_data = capacity_result.scalar()
        max_allowed_potions = capacity_data * 50 

        # fetch current potions
        result = connection.execute(sqlalchemy.text("SELECT COALESCE(SUM(quantity_change), 0) FROM potion_ledger"))
        total_existing_potions = result.scalar()

        # max bottles
        max_allowed_potions -= total_existing_potions
        if max_allowed_potions <= 0:
            print("DEBUG: No bottling needed, sufficient stock available.")
            return []

        # fetch ml inventory
        sql = "SELECT COALESCE(SUM(red_change), 0), COALESCE(SUM(green_change), 0), COALESCE(SUM(blue_change), 0), COALESCE(SUM(dark_change), 0) FROM ml_ledger"
        result = connection.execute(sqlalchemy.text(sql))
        inventory = [amount or 0 for amount in result.fetchone()]
        local_inventory = inventory[:]  # Local copy of the inventory for adjustments

        # load recipes
        recipes_result = connection.execute(sqlalchemy.text("SELECT red, green, blue, dark, id FROM potions"))
        recipes = {row.id: [row.red, row.green, row.blue, row.dark] for row in recipes_result}

        bottle_plan = []
        # calculate the maximum bottles per potion based on the local inventory
        for potion_id, recipe in recipes.items():
            if any(recipe):  
                max_bottles_for_recipe = min((local_inventory[i] // recipe[i] if recipe[i] > 0 else float('inf')) for i in range(4))
                if max_bottles_for_recipe > 0:
                    allocated_bottles = min(max_bottles_for_recipe, max_allowed_potions)
                    if allocated_bottles > 0:
                        # adjust local inventory based on the allocated bottles
                        for i in range(4):
                            if recipe[i] > 0:
                                local_inventory[i] -= recipe[i] * allocated_bottles
                        bottle_plan.append({"potion_type": recipes[potion_id], "quantity": allocated_bottles})
                        max_allowed_potions -= allocated_bottles
                        if max_allowed_potions <= 0:
                            break

        print(f"DEBUG: FINAL BOTTLE PLAN: {bottle_plan}")
        return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())