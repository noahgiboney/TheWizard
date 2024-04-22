from fastapi import APIRouter
import sqlalchemy
from src import database as db
import sqlalchemy
from src import database as db
from fastapi import HTTPException
import re

router = APIRouter()
@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    # fetch potions from the potions table
    sql = """
    SELECT id, name, sku, price, quantity, red, green, blue, dark
    FROM potions
    WHERE quantity > 0;
    """

    potions_for_sale = []

    with db.engine.connect() as connection:
        result = connection.execute(sqlalchemy.text(sql))
        potion_data = result.fetchall()

        for potion in potion_data:
            potion_type = [potion.red, potion.green ,potion.blue, potion.dark]

            try:          
                potions_for_sale.append({
                    "sku": potion.sku,
                    "name": potion.name,
                    "quantity": potion.quantity,
                    "price": potion.price,
                    "potion_type": potion_type
                })
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
    print(f"DEBUG: POTIONS FOR SALE: {potions_for_sale}")
    return potions_for_sale
