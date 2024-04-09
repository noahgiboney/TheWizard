from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/barrels",
    tags=["barrels"],
    dependencies=[Depends(auth.get_api_key)],
)

class Barrel(BaseModel):
    sku: str

    ml_per_barrel: int
    potion_type: list[int]
    price: int

    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_barrels(barrels_delivered: list[Barrel], order_id: int):
    # total md in barrel delivered
    total_ml_added = sum(barrel.ml_per_barrel * barrel.quantity for barrel in barrels_delivered if barrel.potion_type == [0, 100, 0, 0])
    
    # calculate total cost of barrels
    total_cost = sum(barrel.price * barrel.quantity for barrel in barrels_delivered if barrel.potion_type == [0, 100, 0, 0])
    print(total_cost)
    
    if total_ml_added > 0:
        with db.engine.begin() as connection:
            # add ml from the barrel to the db
            sql_update_ml = "UPDATE global_inventory SET num_green_ml = num_green_ml + :ml_added"
            connection.execute(sqlalchemy.text(sql_update_ml), {"ml_added": total_ml_added})
            
            # subtract the gold from the db
            if total_cost > 0:  
                sql_update_gold = "UPDATE global_inventory SET gold = gold - :cost"
                connection.execute(sqlalchemy.text(sql_update_gold), {"cost": total_cost})

    print(f"Barrels delivered: {barrels_delivered}, Order ID: {order_id}")
    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    # fetch current gold amount from inventory
    with db.engine.connect() as connection:
        result = connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory"))
        gold_data = result.fetchone()

    if gold_data is None:
        print("No gold data found.")
        return []

    gold = gold_data[0]

    purchase_plan = []

    # go over catalog and find out how many to purchase
    for barrel in wholesale_catalog:
        if "SMALL_GREEN" in barrel.sku and barrel.price <= gold:
            # how many of such barrels can be purchased with the available gold
            barrels_affordable = min(gold // barrel.price, barrel.quantity)

            if barrels_affordable > 0:
                purchase_plan.append({
                    "sku": barrel.sku,
                    "quantity": barrels_affordable
                })
                gold -= barrels_affordable * barrel.price
                break

    return purchase_plan
