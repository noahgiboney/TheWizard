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
    # Calculate total ml for green potions only
    total_ml_added = sum(barrel.ml_per_barrel * barrel.quantity for barrel in barrels_delivered if barrel.potion_type == [0, 100, 0, 0])  # Adjust potion_type as needed

    # Update the database if there's anything to add
    if total_ml_added > 0:
        with db.engine.begin() as connection:
            sql_to_execute = "UPDATE global_inventory SET num_green_ml = num_green_ml + :ml_added"
            connection.execute(sqlalchemy.text(sql_to_execute), {"ml_added": total_ml_added})

    print(f"Barrels delivered: {barrels_delivered}, Order ID: {order_id}")
    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    # Fetch current inventory details
    with db.engine.connect() as connection:
        result = connection.execute(sqlalchemy.text("SELECT num_green_ml, gold FROM global_inventory"))
        inventory_data = result.fetchone()

    if inventory_data is None:
        print("No inventory data found.")
        return []

    num_green_ml, gold = inventory_data

    # Define the ml threshold for purchasing new barrels and the list to store purchase plans
    ml_threshold = 1000  # Example: aim to have at least 1000 ml of green potion materials
    purchase_plan = []

    # Only proceed if we have less than the threshold of green ml
    if num_green_ml < ml_threshold:
        # Iterate over the wholesale catalog to decide on purchases
        for barrel in wholesale_catalog:
            # Assuming green potion barrels have a specific SKU pattern or potion_type you can check
            if "GREEN" in barrel.sku and barrel.price <= gold:
                # Calculate how many barrels to buy without exceeding the gold or ml_threshold
                max_barrels_to_buy = min((ml_threshold - num_green_ml) // barrel.ml_per_barrel, gold // barrel.price, barrel.quantity)
                
                if max_barrels_to_buy > 0:
                    purchase_plan.append({
                        "sku": barrel.sku,
                        "quantity": max_barrels_to_buy
                    })
                    # Update the num_green_ml and gold to reflect this purchase plan
                    num_green_ml += max_barrels_to_buy * barrel.ml_per_barrel
                    gold -= max_barrels_to_buy * barrel.price

                    # Stop if we have reached our ml threshold or spent all our gold
                    if num_green_ml >= ml_threshold or gold <= 0:
                        break

    print(purchase_plan)
    return purchase_plan

