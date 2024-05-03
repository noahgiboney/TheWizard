from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db
from fastapi import HTTPException

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.get("/audit")
def get_inventory_summary():
    # SQL queries to fetch total changes for gold and potions
    gold_sql = "SELECT SUM(quantity_change) as gold from gold_ledger"
    potions_sql = "SELECT SUM(quantity_change) as potions from potion_ledger"
    
    # Separate SQL queries to fetch changes for each ml color
    red_sql = "SELECT SUM(red_change) as red from ml_ledger"
    green_sql = "SELECT SUM(green_change) as green from ml_ledger"
    blue_sql = "SELECT SUM(blue_change) as blue from ml_ledger"
    dark_sql = "SELECT SUM(dark_change) as dark from ml_ledger"

    with db.engine.connect() as connection:
        # Executing and fetching gold and potions data
        gold_result = connection.execute(sqlalchemy.text(gold_sql))
        gold_data = gold_result.fetchone()
        
        potion_result = connection.execute(sqlalchemy.text(potions_sql))
        potion_data = potion_result.fetchone()
        
        # Executing and fetching data for each ml color
        red_result = connection.execute(sqlalchemy.text(red_sql))
        red_data = red_result.fetchone()
        
        green_result = connection.execute(sqlalchemy.text(green_sql))
        green_data = green_result.fetchone()
        
        blue_result = connection.execute(sqlalchemy.text(blue_sql))
        blue_data = blue_result.fetchone()
        
        dark_result = connection.execute(sqlalchemy.text(dark_sql))
        dark_data = dark_result.fetchone()

    # Calculate totals for gold, potions, and ml
    total_potions = potion_data.potions if potion_data.potions else 0
    total_gold = gold_data.gold if gold_data.gold else 0
    total_ml = (red_data.red if red_data.red else 0) + \
               (green_data.green if green_data.green else 0) + \
               (blue_data.blue if blue_data.blue else 0) + \
               (dark_data.dark if dark_data.dark else 0)

    # Print totals for each ml color for debugging
    print(f"DEBUG: ML COLORS - Red: {red_data.red if red_data.red else 0}, Green: {green_data.green if green_data.green else 0}, Blue: {blue_data.blue if blue_data.blue else 0}, Dark: {dark_data.dark if dark_data.dark else 0}")

    # Return totals for gold, potions, and ml in specified format
    return {
        "number_of_potions": total_potions,
        "ml_in_barrels": total_ml,
        "gold": total_gold
    }

# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    """Plan how many capacities of potions and ml can be bought based on available gold."""
    gold_sql = "SELECT COALESCE(SUM(quantity_change), 0) as gold from gold_ledger"
    with db.engine.begin() as connection:
        gold_result = connection.execute(sqlalchemy.text(gold_sql))
        gold_data = gold_result.fetchone()
        current_gold = gold_data.gold

        max_possible_capacities = current_gold // 1000

        additional_potion_capacity = max_possible_capacities // 2
        additional_ml_capacity = max_possible_capacities - additional_potion_capacity

        return {
            "potion_capacity": additional_potion_capacity,
            "ml_capacity": additional_ml_capacity
        }

class CapacityPurchase(BaseModel):
    potion_capacity: int
    ml_capacity: int

# Gets called once a day
@router.post("/deliver/{order_id}")
def deliver_capacity_plan(capacity_purchase : CapacityPurchase, order_id: int):
    """Updates capacities for potions and ml based on purchased units."""
    with db.engine.begin() as connection:
        # update potion capacity
        connection.execute(sqlalchemy.text("""
            UPDATE capacity SET potion_capacity = potion_capacity + :new_potion_capacity
        """), {'new_potion_capacity': capacity_purchase.potion_capacity})

        # update ml capacity
        connection.execute(sqlalchemy.text("""
            UPDATE capacity SET ml_capacity = ml_capacity + :new_ml_capacity
        """), {'new_ml_capacity': capacity_purchase.ml_capacity})

        return {"status": "success", "message": "Capacity delivered successfully"}
