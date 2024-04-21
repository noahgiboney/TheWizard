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
    # Fetch potions for sale from the potions table
    sql = """
    SELECT id, name, sku, price, quantity, green, red, blue, dark
    FROM potions
    WHERE quantity > 0;
    """

    potions_for_sale = []

    with db.engine.connect() as connection:
        result = connection.execute(sqlalchemy.text(sql))
        potion_data = result.fetchall()

        if not potion_data:
            raise HTTPException(status_code=404, detail="No potions available for sale.")

        for potion in potion_data:
            potion_type = [potion.green, potion.red, potion.blue, potion.dark]

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
