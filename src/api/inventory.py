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
    
    
    gold_sql = "SELECT SUM(quantity_change) as gold from gold_ledger"
    potions_sql = "SELECT SUM(quantity_change) as potions from potion_ledger"
    ml_sql = "SELECT SUM(red_change + green_change + blue_change + dark_change) as ml from ml_ledger"

    with db.engine.connect() as connection:
        gold_result = connection.execute(sqlalchemy.text(gold_sql))
        gold_data = gold_result.fetchone()

        potion_result = connection.execute(sqlalchemy.text(potions_sql))
        potion_data = potion_result.fetchone()

        ml_result = connection.execute(sqlalchemy.text(ml_sql))
        ml_data = ml_result.fetchone()
    
    # calculate totals
    total_potions = potion_data.potions
    total_gold = gold_data.gold
    total_ml = ml_data.ml

    print(f"DEBUG: AUDIT INVENTORY: {total_potions}potions, {total_ml}ml, {total_gold}gold")

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
