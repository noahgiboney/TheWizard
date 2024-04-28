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
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """

    return {
        "potion_capacity": 0,
        "ml_capacity": 0
        }

class CapacityPurchase(BaseModel):
    potion_capacity: int
    ml_capacity: int

# Gets called once a day
@router.post("/deliver/{order_id}")
def deliver_capacity_plan(capacity_purchase : CapacityPurchase, order_id: int):
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """

    return "OK"
