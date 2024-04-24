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
    adjectives = [
        "Magic", "Ancient", "Mystic", "Rare", "Invisible", "Fiery", "Icy", "Glowing",
        "Dark", "Shimmering", "Sparkling", "Bubbling", "Spectral", "Enchanted",
        "Venomous", "Potent", "Vibrant", "Dull", "Soothing", "Aggressive"
    ]
    nouns = [
        "Elixir", "Potion", "Brew", "Serum", "Tonic", "Mixture", "Drink", "Concoction",
        "Blend", "Solution", "Philter", "Draft", "Distillate", "Extract", "Essence"
    ]
    extras = [
        "of Power", "of Stealth", "of Healing", "of Energy", "of Luck", "of Might",
        "of Wisdom", "of Charm", "of Speed", "of Invisibility", "", "", "", "", ""
    ]
    effects = [
        "Revitalization", "Endurance", "Intellect", "Strength", "Courage", "Fright",
        "Tranquility", "Haste", "Slumber", "Transparency"
    ]

    # Choose components for the name randomly
    adjective = random.choice(adjectives)
    second_adjective = random.choice(adjectives + [""])
    noun = random.choice(nouns)
    extra = random.choice(extras)
    effect = random.choice(effects + ["", "", "", "", ""])

    if random.choice([True, False]):
        adjective = f"{adjective} {second_adjective}".strip()

    if random.choice([True, False]):
        extra = f"{extra} of {effect}".strip()

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

            # check if the potion with the exact composition already exists
            sql_check_potion = """
                SELECT id, quantity FROM potions
                WHERE red = :red AND green = :green AND blue = :blue AND dark = :dark
            """
            result = connection.execute(sqlalchemy.text(sql_check_potion), {
                'red': red, 'green': green, 'blue': blue, 'dark': dark
            })
            potion_result = result.mappings().first()

            if potion_result:
                # update the quantity of the existing potion
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
                # generate a new potion name and SKU
                unique_sku_found = False
                while not unique_sku_found:
                    name = generate_potion_name()
                    sku = generate_sku(name)

                    # check if the generated SKU already exists
                    result = connection.execute(sqlalchemy.text("SELECT COUNT(*) FROM potions WHERE sku = :sku"), {'sku': sku})
                    if result.scalar() == 0:
                        unique_sku_found = True

                # insert the new potion record
                sql_insert_potion = """
                    INSERT INTO potions (red, green, blue, dark, name, sku, price, quantity)
                    VALUES (:red, :green, :blue, :dark, :name, :sku, :price, :quantity)
                """
                connection.execute(sqlalchemy.text(sql_insert_potion), {
                    'red': red, 'green': green, 'blue': blue, 'dark': dark,
                    'name': name, 'sku': sku, 'price': 40, 'quantity': potion_quantity
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

        # check the amount of potions
        result = connection.execute(sqlalchemy.text("SELECT SUM(quantity) FROM potions"))
        total_existing_potions = result.scalar() or 0

        # bottle nothing if i have 50 potions
        if total_existing_potions >= 50:
            print("DEBUG: No bottling needed, sufficient stock available.")
            return []

        # get global inventory 
        sql = "SELECT num_red_ml, num_green_ml, num_blue_ml, num_dark_ml FROM global_inventory"
        result = connection.execute(sqlalchemy.text(sql))
        inventory_data = result.fetchone()

    inventory = list(inventory_data)

    # generate 6 possible recipes
    recipes = generate_recipes(inventory, 6) 

    bottle_plan = []
    potion_volume_ml = 100
    total_bottles = total_existing_potions 
    max_total_bottles = 50 

    # calculate bottles based on recipes
    for recipe in recipes:
        if total_bottles >= max_total_bottles:
            break  #

        max_bottles = float('inf')
        for i, ratio in enumerate(recipe):
            if ratio > 0:
                required_ml = potion_volume_ml * ratio // 100
                max_bottles = min(max_bottles, inventory[i] // required_ml)

        # calculate the number of bottles to produce for this recipe
        max_bottles = min(max_bottles, (max_total_bottles - total_bottles) // len(recipes))

        if max_bottles > 0:
            bottle_plan.append({"potion_type": recipe, "quantity": max_bottles})
            total_bottles += max_bottles
            for i, ratio in enumerate(recipe):
                inventory[i] -= max_bottles * (potion_volume_ml * ratio // 100)

    print(f"DEBUG: BOTTLE PLAN: {bottle_plan}")
    return bottle_plan

if __name__ == "__main__":
    print(get_bottle_plan())