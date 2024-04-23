from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db
from fastapi import HTTPException

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
    
    print(f"DEBUG: BARRELS DELIVERED: {barrels_delivered} WITH ORDER ID: {order_id}")
    
    # dictionary to track total ml for barrels and total cost for each potion type
    potion_totals = {
        "red": {"ml": 0, "cost": 0},
        "green": {"ml": 0, "cost": 0},
        "blue": {"ml": 0, "cost": 0},
        "dark": {"ml": 0, "cost": 0}
    }

    potion_color_map = {
        (1, 0, 0, 0): "red", 
        (0, 1, 0, 0): "green",
        (0, 0, 1, 0): "blue",
        (0, 0, 0, 1): "dark"
    }

    # totals for each barrel delivered
    for barrel in barrels_delivered:
        potion_type = tuple(barrel.potion_type)
        if potion_type in potion_color_map:
            color = potion_color_map[potion_type]
            potion_totals[color]["ml"] += barrel.ml_per_barrel * barrel.quantity
            potion_totals[color]["cost"] += barrel.price * barrel.quantity

    with db.engine.begin() as connection:
        for color, totals in potion_totals.items():
            if totals["ml"] > 0:
                # add ml to db
                sql_update_ml = sqlalchemy.text(
                    f"UPDATE global_inventory SET num_{color}_ml = num_{color}_ml + :ml_added"
                )
                connection.execute(sql_update_ml, {"ml_added": totals["ml"]})

            if totals["cost"] > 0:
                # subtract gold in db
                sql_update_gold = sqlalchemy.text(
                    "UPDATE global_inventory SET gold = gold - :cost"
                )
                connection.execute(sql_update_gold, {"cost": totals["cost"]})
    print("DEBUG: BARRELS DELIVERED SUCCESS")
    return {"status": "success", "message": "Delivery processed and inventory updated"}

class Purchase(BaseModel):
    sku: str
    quantity: int

@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    print(f"DEBUG WHOLESALE CATALOG: {wholesale_catalog}")

    # fetch current gold from global inventory
    with db.engine.connect() as connection:
        result = connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory"))
        gold_data = result.fetchone()

    if gold_data is None:
        print("No gold data found.")
        return []
    gold = gold_data[0]

    # Group barrels by type
    type_dict = {}
    for barrel in wholesale_catalog:
        type_key = tuple(barrel.potion_type)
        if type_key not in type_dict:
            type_dict[type_key] = []
        type_dict[type_key].append(barrel)

    purchase_plan = []

   #try to purchase differnt types of barrels
    types_bought = set()
    for type1 in type_dict:
        for type2 in type_dict:
            if type1 != type2 and (type1 not in types_bought and type2 not in types_bought):
                barrel1, barrel2 = type_dict[type1][0], type_dict[type2][0]
                if gold >= barrel1.price + barrel2.price:
                    purchase_plan.append(Purchase(sku=barrel1.sku, quantity=1))
                    purchase_plan.append(Purchase(sku=barrel2.sku, quantity=1))
                    gold -= (barrel1.price + barrel2.price)
                    types_bought.update([type1, type2])

   #buy single barrel 
    for type_key, barrels in type_dict.items():
        if type_key not in types_bought:
            barrel = barrels[0]
            if gold >= barrel.price:
                purchase_plan.append(Purchase(sku=barrel.sku, quantity=1))
                gold -= barrel.price
                types_bought.add(type_key)

    print(f"DEBUG: BARREL PURCHASE PLAN: {purchase_plan}")
    return purchase_plan
