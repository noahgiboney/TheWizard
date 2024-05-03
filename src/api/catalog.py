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
    # fetch potions along with total quantity available
    sql = """
    SELECT p.id, p.name, p.sku, p.price, COALESCE(SUM(pl.quantity_change), 0) as quantity,
           p.red, p.green, p.blue, p.dark
    FROM potions p
    LEFT JOIN potion_ledger pl ON p.id = pl.potion_id
    GROUP BY p.id, p.name, p.sku, p.price, p.red, p.green, p.blue, p.dark
    HAVING COALESCE(SUM(pl.quantity_change), 0) > 0;
    """

    potions_for_sale = []

    with db.engine.connect() as connection:
        result = connection.execute(sqlalchemy.text(sql))
        potion_data = result.fetchall()

        for potion in potion_data:
            potion_type = [potion.red, potion.green ,potion.blue, potion.dark]

            potions_for_sale.append({
                "sku": potion.sku,
                "name": potion.name,
                "quantity": potion.quantity,
                "price": potion.price,
                "potion_type": potion_type
            })

    print(f"DEBUG: POTIONS FOR SALE: {potions_for_sale}")
    return potions_for_sale
