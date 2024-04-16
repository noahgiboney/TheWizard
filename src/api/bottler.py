from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db
from fastapi import HTTPException

router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)

class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    print(f"DEBUG POSTDELIVERBOTTLES: {potions_delivered}")
    # calculate quantities delivered for each potion type
    potion_quantities = {
        "green": sum(potion.quantity for potion in potions_delivered if potion.potion_type == [0, 100, 0, 0]),
        "red": sum(potion.quantity for potion in potions_delivered if potion.potion_type == [100, 0, 0, 0]),
        "blue": sum(potion.quantity for potion in potions_delivered if potion.potion_type == [0, 0, 100, 0])
    }

    # calculate ml used for each potion type, 100 ml per potion
    ml_used = {color: quantity * 100 for color, quantity in potion_quantities.items()}

    with db.engine.begin() as connection: 
        # update database for each potion color
        for color in ['green', 'red', 'blue']:
            if potion_quantities[color] > 0:
                # update potions in db
                sql_update_potions = f"""
                    UPDATE global_inventory 
                    SET num_{color}_potions = num_{color}_potions + '{potion_quantities[color]}'
                """
                connection.execute(sqlalchemy.text(sql_update_potions))
                
                # update ml in the db
                sql_update_ml = f"""
                    UPDATE global_inventory 
                    SET num_{color}_ml = num_{color}_ml - {ml_used[color]}
                    WHERE num_{color}_ml >= {ml_used[color]}
                """
                result = connection.execute(sqlalchemy.text(sql_update_ml))
                if result.rowcount == 0: 
                    connection.rollback()  
                    return {"status": "error", "message": f"Not enough {color} ml available to fulfill the order."}

    print(f"Potions delivered: {potions_delivered}, Order ID: {order_id}")
    return {"status": "success", "message": "Delivery processed successfully"}

@router.post("/bottler/plan")
def get_bottle_plan():
    print("DEBUG: GETBOTTLEPLAN")
    # fetch poitions ml from inventory
    with db.engine.begin() as connection:
        sql = "SELECT num_green_ml, num_red_ml, num_blue_ml FROM global_inventory"
        result = connection.execute(sqlalchemy.text(sql))
        inventory_data = result.fetchone()

    print(f"DEBUG: {inventory_data}")

    num_green_ml, num_red_ml, num_blue_ml = inventory_data
    
    bottle_plan = []
    
    
    # calc how many bottles can be made per potion
    potions_to_bottle_green = num_green_ml // 100
    if potions_to_bottle_green > 0:
        bottle_plan.append({"potion_type": [0, 100, 0, 0], "quantity": potions_to_bottle_green})

    potions_to_bottle_red = num_red_ml // 100
    if potions_to_bottle_red > 0:
        bottle_plan.append({"potion_type": [100, 0, 0, 0], "quantity": potions_to_bottle_red})

    potions_to_bottle_blue = num_blue_ml // 100
    if potions_to_bottle_blue > 0:
        bottle_plan.append({"potion_type": [0, 0, 100, 0], "quantity": potions_to_bottle_blue})

    return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())