from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import math
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
    
    global_inventory_sql = "SELECT num_green_ml, num_red_ml, num_blue_ml, gold FROM global_inventory"
    total_potions_sql = "SELECT SUM(quantity) AS total_quantity FROM potions"

    with db.engine.connect() as connection:
        result = connection.execute(sqlalchemy.text(global_inventory_sql))
        global_data = result.fetchone()

        total_potions_result = connection.execute(sqlalchemy.text(total_potions_sql))
        total_potions_data = total_potions_result.fetchone()

    if global_data is None:
        raise HTTPException(status_code=404, detail="Inventory not found.")
    
    # calculate totals
    total_ml = global_data.num_green_ml + global_data.num_red_ml + global_data.num_blue_ml
    total_quantity = total_potions_data.total_quantity if total_potions_data.total_quantity is not None else 0
    total_gold = global_data.gold

    print(f"DEBUG: AUDIT INVENTORY: {total_quantity}potions, {total_ml}ml, {total_gold}gold")

    return {
        "number_of_potions": total_quantity,
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
