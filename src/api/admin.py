from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.post("/reset")
def reset():
    """
    Reset the game state. Gold goes to 100, all potions are removed from inventory,
    and all barrels are removed from inventory. Carts are all reset.
    """
    
    with db.engine.connect() as connection:

        # clear carts
        connection.execute(sqlalchemy.text("TRUNCATE TABLE carts"))
        connection.execute(sqlalchemy.text("TRUNCATE TABLE cart_items"))

        # clear ledgers
        connection.execute(sqlalchemy.text("TRUNCATE TABLE gold_ledger"))
        connection.execute(sqlalchemy.text("TRUNCATE TABLE ml_ledger"))
        connection.execute(sqlalchemy.text("TRUNCATE TABLE potion_ledger"))

        # insert 100 gold
        connection.execute(sqlalchemy.text("INSERT INTO gold_ledger (quantity_change) VALUES (:quantity_change)"), {'quantity_change': 100})
        connection.commit()
    return "OK"

