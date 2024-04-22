from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db
from fastapi import HTTPException
import random

router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)

class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int

def generate_potion_name():
    adjectives = ["Magic", "Ancient", "Mystic", "Rare", "Invisible", "Fiery", "Icy", "Glowing", "Dark", "Shimmering"]
    nouns = ["Elixir", "Potion", "Brew", "Serum", "Tonic", "Mixture", "Drink", "Concoction", "Blend", "Solution"]
    extras = ["of Power", "of Stealth", "of Healing", "of Energy", "of Luck", "", "", "", "", ""]  # Including some blanks for variability

    adjective = random.choice(adjectives)
    noun = random.choice(nouns)
    extra = random.choice(extras)

    potion_name = f"{adjective} {noun} {extra}".strip()
    return potion_name

def generate_sku(name):
    return name.upper().replace(" ", "_")

@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    print(f"DEBUG POTIONS DELIVERED: {potions_delivered}")

    with db.engine.begin() as connection:
        for potion in potions_delivered:
            red, green, blue, dark = potion.potion_type
            potion_quantity = potion.quantity

            sql_check_potion = """
                SELECT id, quantity FROM potions
                WHERE red = :red AND green = :green AND blue = :blue AND dark = :dark
            """

            # check if potions exsits
            result = connection.execute(sqlalchemy.text(sql_check_potion), {
                'green': green,
                'red': red,
                'blue': blue,
                'dark': dark
            })
            potion_result = result.mappings().first()

            if potion_result:
                #update the quantity
                new_quantity = potion_result['quantity'] + potion_quantity
                sql_update_potion = """
                    UPDATE potions
                    SET quantity = :new_quantity
                    WHERE id = :id
                """
                connection.execute(sqlalchemy.text(sql_update_potion), {
                    'new_quantity': new_quantity,
                    'id': potion_result['id']
                })
            else:
                # if potion does not exists create a new record
                name = generate_potion_name()
                sku = generate_sku(name)
                sql_insert_potion = """
                    INSERT INTO potions (red, green, blue, dark, name, sku, price, quantity)
                    VALUES (:red, :green, :blue, :dark, :name, :sku, :price, :quantity)
                """
                connection.execute(sqlalchemy.text(sql_insert_potion), {
                    'red': red,
                    'green': green,
                    'blue': blue,
                    'dark': dark,
                    'name': name,
                    'sku': sku,
                    'price': 50,
                    'quantity': potion_quantity
                })
            
            # update ml in inventory
            for color, amount in zip(['red', 'green', 'blue', 'dark'], [red, green, blue, dark]):
                ml_update = amount * potion_quantity
                sql_update_ml = f"""
                    UPDATE global_inventory 
                    SET num_{color}_ml = num_{color}_ml - :ml_update
                    WHERE num_{color}_ml >= :ml_update
                """
                result = connection.execute(sqlalchemy.text(sql_update_ml), {'ml_update': ml_update})
                if result.rowcount == 0:
                    raise HTTPException(status_code=400, detail=f"Not enough {color} ml available to fulfill the order.")

    print(f"DEBUD POTIONS DELIVERED: {potions_delivered}, orderID: {order_id}")
    return {"status": "success", "message": "Delivery processed successfully"}

def generate_recipes(inventory, num_recipes=10):
    total_inventory = sum(inventory)
    if total_inventory == 0:
        return []  
    
    recipes = []
    while len(recipes) < num_recipes:
        parts = [random.randint(0, stock) for stock in inventory]
        total_parts = sum(parts)
        if total_parts == 0:
            continue  

        normalized_parts = [part * 100 // total_parts for part in parts]
        adjustment = 100 - sum(normalized_parts)
        for i in range(len(normalized_parts)):
            if normalized_parts[i] > 0:
                normalized_parts[i] += adjustment
                break

        recipes.append(tuple(normalized_parts))

    return recipes

@router.post("/plan")
def get_bottle_plan():
    with db.engine.begin() as connection:
        sql = "SELECT num_red_ml, num_green_ml, num_blue_ml, num_dark_ml FROM global_inventory"
        result = connection.execute(sqlalchemy.text(sql))
        inventory_data = result.fetchone()

    inventory = list(inventory_data)

    # generate 6 possible recipes
    recipes = generate_recipes(inventory, 6) 

    bottle_plan = []
    potion_volume_ml = 100  
    
    # calculate bottles based on recipes
    for recipe in recipes:
        max_bottles = float('inf')
        for i, ratio in enumerate(recipe):
            if ratio > 0:
                required_ml = potion_volume_ml * ratio // 100
                max_bottles = min(max_bottles, inventory[i] // required_ml)
        
        if max_bottles > 0:
            bottle_plan.append({"potion_type": recipe, "quantity": max_bottles})
            for i, ratio in enumerate(recipe):
                inventory[i] -= max_bottles * (potion_volume_ml * ratio // 100)

    print(f"DEBUG: BOTTLE PLAN: {bottle_plan}")
    return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())