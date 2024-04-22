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
        reset_global_inv = """
        UPDATE global_inventory
        SET num_red_ml = 0, num_green_ml = 0, num_blue_ml = 0, num_dark_ml
        gold = 100;
        """

        reset_potions_records = "TRUNCATE TABLE potions"

        connection.execute(sqlalchemy.text(reset_global_inv))
        connection.execute(sqlalchemy.text(reset_potions_records))
        connection.commit()
    return "OK"

