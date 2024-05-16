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
        # Fetch potion capacity
        capacity_result = connection.execute(sqlalchemy.text("SELECT potion_capacity FROM capacity LIMIT 1"))
        capacity_data = capacity_result.scalar()
        max_allowed_potions = capacity_data * 50
        print(f"DEBUG: Max allowed potions based on capacity: {max_allowed_potions}")

        # Fetch current potions
        result = connection.execute(sqlalchemy.text("SELECT COALESCE(SUM(quantity_change), 0) FROM potion_ledger"))
        total_existing_potions = result.scalar()
        print(f"DEBUG: Total existing potions: {total_existing_potions}")

        # Calculate the additional potions that can be made
        additional_potions_allowed = max_allowed_potions - total_existing_potions
        if additional_potions_allowed <= 0:
            print("DEBUG: No bottling needed, sufficient stock available.")
            return []

        print(f"DEBUG: Additional potions allowed: {additional_potions_allowed}")

        # Fetch ML inventory
        sql = "SELECT COALESCE(SUM(red_change), 0), COALESCE(SUM(green_change), 0), COALESCE(SUM(blue_change), 0), COALESCE(SUM(dark_change), 0) FROM ml_ledger"
        result = connection.execute(sqlalchemy.text(sql))
        local_inventory = [amount or 0 for amount in result.fetchone()]
        print(f"DEBUG: Local ML inventory: {local_inventory}")

        # Load recipes
        recipes_result = connection.execute(sqlalchemy.text("SELECT red, green, blue, dark, id FROM potions"))
        recipes = {row.id: [row.red, row.green, row.blue, row.dark] for row in recipes_result}
        print(f"DEBUG: Loaded recipes: {recipes}")

        # Calculate maximum possible potions for each type, ensuring only feasible recipes are considered
        potion_counts = {}
        feasible_recipes = {}
        for potion_id, recipe in recipes.items():
            if all(local_inventory[i] >= recipe[i] for i in range(4) if recipe[i] > 0):
                feasible_potions = min((local_inventory[i] // recipe[i] if recipe[i] > 0 else float('inf')) for i in range(4))
                if feasible_potions > 0:
                    potion_counts[potion_id] = feasible_potions
                    feasible_recipes[potion_id] = recipe
            else:
                print(f"DEBUG: Cannot make potion {potion_id} due to insufficient ingredients")

        print(f"DEBUG: Feasible potion counts: {potion_counts}")

        # Normalize distribution to ensure even distribution of potion types without exceeding the additional potions allowed
        if potion_counts:
            total_potions = sum(potion_counts.values())
            min_possible_potions = min(potion_counts.values())
            normalized_total = min(additional_potions_allowed, total_potions)
            evenly_distributed = normalized_total // len(potion_counts)
            remainder = normalized_total % len(potion_counts)

            for potion_id in potion_counts:
                potion_counts[potion_id] = evenly_distributed

            # Handle any remainder if the total doesn't divide evenly
            for potion_id in sorted(potion_counts.keys(), key=lambda x: potion_counts[x], reverse=True):
                if remainder > 0:
                    potion_counts[potion_id] += 1
                    remainder -= 1

        print(f"DEBUG: Normalized potion counts: {potion_counts}")

        # Calculate total ML usage
        total_used_inventory = [0, 0, 0, 0]
        for potion_id, count in potion_counts.items():
            recipe = feasible_recipes[potion_id]
            for i in range(4):
                total_used_inventory[i] += recipe[i] * count

        print(f"DEBUG: Total ML usage before adjustment: {total_used_inventory}")

        # Adjust potion counts to fit within the local inventory limits
        adjusted_potion_counts = potion_counts.copy()
        for i in range(4):
            if total_used_inventory[i] > local_inventory[i]:
                excess = total_used_inventory[i] - local_inventory[i]
                print(f"DEBUG: Ingredient {i} exceeds inventory by {excess} units")
                for potion_id, count in sorted(adjusted_potion_counts.items(), key=lambda x: feasible_recipes[x[0]][i], reverse=True):
                    if feasible_recipes[potion_id][i] > 0:
                        max_reduction = adjusted_potion_counts[potion_id]  # Max we can reduce is the current count
                        needed_reduction = (excess + feasible_recipes[potion_id][i] - 1) // feasible_recipes[potion_id][i]  # Calculate needed reduction
                        reduction = min(max_reduction, needed_reduction)  # Reduce by the lesser of max_reduction or needed_reduction
                        adjusted_potion_counts[potion_id] -= reduction
                        reduction_amount = reduction * feasible_recipes[potion_id][i]
                        excess -= reduction_amount
                        total_used_inventory[i] -= reduction_amount
                        print(f"DEBUG: Reducing potion {potion_id} by {reduction} units, {reduction_amount} ml, new count: {adjusted_potion_counts[potion_id]}, remaining excess: {excess}")
                        if excess <= 0:
                            break

        print(f"DEBUG: Adjusted potion counts: {adjusted_potion_counts}")
        print(f"DEBUG: Total ML usage after adjustment: {total_used_inventory}")

        # Verify final ML usage is within inventory limits
        final_bottle_plan = []
        for potion_id, count in adjusted_potion_counts.items():
            if count > 0:  # Ensure only non-zero quantities are added to the plan
                recipe = feasible_recipes[potion_id]
                final_bottle_plan.append({"potion_type": recipe, "quantity": count})

        print(f"DEBUG: FINAL BOTTLE PLAN: {final_bottle_plan}")
        for i, amount in enumerate(local_inventory):
            if total_used_inventory[i] > amount:
                print(f"ERROR: Ingredient {i} still exceeds inventory limits after adjustment. Used: {total_used_inventory[i]}, Available: {amount}")

        return final_bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())