from fastapi import APIRouter
import sqlalchemy
from src import database as db
import sqlalchemy
from src import database as db
from fastapi import HTTPException
import re

router = APIRouter()


def validate_sku(sku):
    if not re.match(r'^[a-zA-Z0-9_]{1,20}$', sku):
        raise ValueError("SKU format is invalid")

def validate_quantity(quantity):
    if not (1 <= quantity <= 10000):
        raise ValueError("Quantity must be between 1 and 10000")

def validate_price(price):
    if not (1 <= price <= 500):
        raise ValueError("Price must be between 1 and 500")

def validate_potion_type(potion_type):
    if sum(potion_type) != 100:
        raise ValueError("Potion type components must add up to exactly 100")

@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    print("DEBUG CATALOG")
    # fetch sql
    sql = """
    SELECT num_green_potions, num_red_potions, num_blue_potions
    FROM global_inventory;
    """

    potions_for_sale = []

    with db.engine.connect() as connection:
        result = connection.execute(sqlalchemy.text(sql))
        inventory_data = result.fetchone()
        print(inventory_data)

        if not inventory_data:
            raise HTTPException(status_code=404, detail="No inventory data found.")

        num_green_potions, num_red_potions, num_blue_potions = inventory_data

        # for now only seel r g b potions
        if num_green_potions > 0:
            try:
                validate_sku("GREEN_POTION_1")
                validate_quantity(num_green_potions)
                validate_price(100)
                validate_potion_type([0, 100, 0, 0])
                potions_for_sale.append({
                    "sku": "GREEN_POTION_1",
                    "name": "Green Potion",
                    "quantity": num_green_potions,
                    "price": 100,
                    "potion_type": [0, 100, 0, 0]
                })
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        if num_red_potions > 0:
            try:
                validate_sku("RED_POTION_1")
                validate_quantity(num_red_potions)
                validate_price(100)
                validate_potion_type([100, 0, 0, 0])
                potions_for_sale.append({
                    "sku": "RED_POTION_1",
                    "name": "Red Potion",
                    "quantity": num_red_potions,
                    "price": 100,
                    "potion_type": [100, 0, 0, 0]
                })
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        if num_blue_potions > 0:
            try:
                validate_sku("BLUE_POTION_1")
                validate_quantity(num_blue_potions)
                validate_price(100)
                validate_potion_type([0, 0, 100, 0])
                potions_for_sale.append({
                    "sku": "BLUE_POTION_1",
                    "name": "Blue Potion",
                    "quantity": num_blue_potions,
                    "price": 100,
                    "potion_type": [0, 0, 100, 0]
                })
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

    return potions_for_sale
