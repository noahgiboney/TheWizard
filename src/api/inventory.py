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
def get_inventory():
    # Fetch the full inventory, including all potion types and their corresponding ml
    sql_query = """
    SELECT num_green_potions, num_green_ml, num_red_potions, num_red_ml, num_blue_potions, num_blue_ml, gold
    FROM global_inventory;
    """
    with db.engine.connect() as connection:
        result = connection.execute(sqlalchemy.text(sql_query))
        inventory_data = result.fetchone()

    if inventory_data is None:
        raise HTTPException(status_code=404, detail="Inventory not found.")
    
    return {
        "green_potions": {
            "number_of_potions": inventory_data[0],
            "ml_in_barrels": inventory_data[1]
        },
        "red_potions": {
            "number_of_potions": inventory_data[2],
            "ml_in_barrels": inventory_data[3]
        },
        "blue_potions": {
            "number_of_potions": inventory_data[4],
            "ml_in_barrels": inventory_data[5]
        },
        "gold": inventory_data[6]
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
