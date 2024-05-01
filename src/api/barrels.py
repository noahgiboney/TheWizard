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
    
    potion_totals = {
        "red": 0,
        "green": 0,
        "blue": 0,
        "dark": 0
    }

    potion_color_map = {
        (1, 0, 0, 0): "red", 
        (0, 1, 0, 0): "green",
        (0, 0, 1, 0): "blue",
        (0, 0, 0, 1): "dark"
    }

    with db.engine.begin() as connection:
        for barrel in barrels_delivered:
            potion_type = tuple(barrel.potion_type)
            if potion_type in potion_color_map:
                color = potion_color_map[potion_type]
                potion_totals[color] += barrel.ml_per_barrel * barrel.quantity

        # inserting changes into ml_ledger for each color
        sql_insert_ml_ledger = sqlalchemy.text(
            "INSERT INTO ml_ledger (red_change, green_change, blue_change, dark_change) "
            "VALUES (:red_change, :green_change, :blue_change, :dark_change)"
        )
        connection.execute(
            sql_insert_ml_ledger,
            {
                "red_change": potion_totals["red"],
                "green_change": potion_totals["green"],
                "blue_change": potion_totals["blue"],
                "dark_change": potion_totals["dark"]
            }
        )

        # insert a record for gold spent in gold ledger
        total_cost = sum(barrel.price * barrel.quantity for barrel in barrels_delivered)
        sql_update_gold = sqlalchemy.text(
            "INSERT INTO gold_ledger (quantity_change) VALUES(:cost)"
        )
        connection.execute(sql_update_gold, {"cost": -total_cost})

    print("DEBUG: BARRELS DELIVERED SUCCESS")
    return {"status": "success", "message": "Delivery processed and inventory updated"}

class Purchase(BaseModel):
    sku: str
    quantity: int

@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    print(f"DEBUG WHOLESALE CATALOG: {wholesale_catalog}")

    # fetch gold from global inventory
    with db.engine.connect() as connection:
        result = connection.execute(sqlalchemy.text("SELECT SUM(quantity_change) as gold from gold_ledger"))
        gold_data = result.fetchone()

    if gold_data is None:
        print("No gold data found.")
        return []
    gold = gold_data.gold
    print(f"DEBUG: Starting gold: {gold}")

    # group barrels by type and sort by cost efficiency (price per ml)
    type_dict = {}
    for barrel in wholesale_catalog:
        type_key = tuple(barrel.potion_type)
        if type_key not in type_dict:
            type_dict[type_key] = []
        type_dict[type_key].append(barrel)
        type_dict[type_key].sort(key=lambda x: x.price / x.ml_per_barrel)

    purchase_plan = []
    total_ml = 0  # Track total milliliters purchased

    # prioritize purchasing barrels from different types with the best price/ml
    for type_key in sorted(type_dict.keys(), key=lambda k: type_dict[k][0].price / type_dict[k][0].ml_per_barrel):
        if total_ml >= 5000:
            break  # Stop adding if total ml exceeds or reaches 10,000 ml
        for barrel in type_dict[type_key]:
            if gold >= barrel.price and total_ml + barrel.ml_per_barrel <= 5000:
                purchase_plan.append(Purchase(sku=barrel.sku, quantity=1))
                gold -= barrel.price
                total_ml += barrel.ml_per_barrel
                print(f"DEBUG: Bought barrel {barrel.sku} adding {barrel.ml_per_barrel}ml, total ml: {total_ml}")
                break

    print(f"DEBUG: BARREL PURCHASE PLAN: {purchase_plan}")
    return purchase_plan
