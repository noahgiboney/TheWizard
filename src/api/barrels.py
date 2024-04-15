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
    print(f"DEBUG POST DELIVER BARRELS: {barrels_delivered} {order_id}")
    # dictionary to track total ml added and total cost for each potion type
    potion_totals = {
        "green": {"ml": 0, "cost": 0},
        "red": {"ml": 0, "cost": 0},
        "blue": {"ml": 0, "cost": 0}
    }

    # rgb map of potions 
    potion_color_map = {
        (0, 100, 0): "green",
        (100, 0, 0): "red",
        (0, 0, 100): "blue"
    }

    # calculate totals for each barrel delivered
    for barrel in barrels_delivered:
        potion_type = tuple(barrel.potion_type)
        if potion_type in potion_color_map:
            color = potion_color_map[potion_type]
            potion_totals[color]["ml"] += barrel.ml_per_barrel * barrel.quantity
            potion_totals[color]["cost"] += barrel.price * barrel.quantity

    # update the database for each potion type
    with db.engine.begin() as connection:
        for color, totals in potion_totals.items():
            if totals["ml"] > 0:
                # add ml from the barrels to the database
                sql_update_ml = f"UPDATE global_inventory SET num_{color}_ml = num_{color}_ml + :ml_added"
                connection.execute(sqlalchemy.text(sql_update_ml), {"ml_added": totals["ml"]})

                # subtract the cost from the gold in the database
                if totals["cost"] > 0:
                    sql_update_gold = "UPDATE global_inventory SET gold = gold - :cost"
                    connection.execute(sqlalchemy.text(sql_update_gold), {"cost": totals["cost"]})

    print(f"Barrels delivered: {barrels_delivered}, Order ID: {order_id}")
    return {"status": "success", "message": "Delivery processed and inventory updated"}

class Purchase(BaseModel):
    sku: str
    quantity: int

#Gets called once a day 
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    print(f"DEBUG GETWHOLESALEPURCHASE: {wholesale_catalog}")
    # Fetch current gold amount from inventory
    with db.engine.connect() as connection:
        result = connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory"))
        gold_data = result.fetchone()

    if gold_data is None:
        print("No gold data found.")
        return []

    gold = gold_data[0]
    purchase_plan = []

    # iterate catalog and 
    for barrel in wholesale_catalog:
        if gold < barrel.price:
            continue  # not enough gold to buy even one barrel

        max_purchaseable = min(gold // barrel.price, barrel.quantity)
        if max_purchaseable > 0:
            purchase_plan.append(Purchase(sku=barrel.sku, quantity=max_purchaseable))
            gold -= max_purchaseable * barrel.price  # update remaining gold after purchase

    return purchase_plan
