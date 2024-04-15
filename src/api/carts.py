from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from enum import Enum
import sqlalchemy
from src import database as db
from fastapi import HTTPException
import uuid

router = APIRouter(
    prefix="/carts",
    tags=["cart"],
    dependencies=[Depends(auth.get_api_key)],
)

class search_sort_options(str, Enum):
    customer_name = "customer_name"
    item_sku = "item_sku"
    line_item_total = "line_item_total"
    timestamp = "timestamp"

class search_sort_order(str, Enum):
    asc = "asc"
    desc = "desc"   

@router.get("/search/", tags=["search"])
def search_orders(
    customer_name: str = "",
    potion_sku: str = "",
    search_page: str = "",
    sort_col: search_sort_options = search_sort_options.timestamp,
    sort_order: search_sort_order = search_sort_order.desc,
):
    """
    Search for cart line items by customer name and/or potion sku.

    Customer name and potion sku filter to orders that contain the 
    string (case insensitive). If the filters aren't provided, no
    filtering occurs on the respective search term.

    Search page is a cursor for pagination. The response to this
    search endpoint will return previous or next if there is a
    previous or next page of results available. The token passed
    in that search response can be passed in the next search request
    as search page to get that page of results.

    Sort col is which column to sort by and sort order is the direction
    of the search. They default to searching by timestamp of the order
    in descending order.

    The response itself contains a previous and next page token (if
    such pages exist) and the results as an array of line items. Each
    line item contains the line item id (must be unique), item sku, 
    customer name, line item total (in gold), and timestamp of the order.
    Your results must be paginated, the max results you can return at any
    time is 5 total line items.
    """

    return {
        "previous": "",
        "next": "",
        "results": [
            {
                "line_item_id": 1,
                "item_sku": "1 oblivion potion",
                "customer_name": "Scaramouche",
                "line_item_total": 50,
                "timestamp": "2021-01-01T00:00:00Z",
            }
        ],
    }


class Customer(BaseModel):
    customer_name: str
    character_class: str
    level: int

@router.post("/visits/{visit_id}")
def post_visits(visit_id: int, customers: list[Customer]):
    """
    Which customers visited the shop today?
    """
    print(customers)

    return "OK"

carts = {}
cart_id_counter = 0

@router.post("/")
def create_cart(new_cart: Customer):
    """Create a new cart with a unique identifier for a specific customer."""
    global cart_id_counter  # Use the global variable to keep track of the last used ID
    cart_id_counter += 1  # Increment the cart ID counter to get a new unique ID
    cart_id = cart_id_counter  # Use the incremented counter as the new cart ID

    # Store the cart with customer details and an initially empty dictionary of items
    carts[cart_id] = {
        "customer": new_cart.dict(),
        "items": {}
    }
    return {"cart_id": cart_id}  # Respond with only the cart_id as per API spec


class CartItem(BaseModel):
    quantity: int

@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """Update the quantity of an item in the cart."""
    if cart_id not in carts:
        return {"success": False}
    
    if "items" not in carts[cart_id]:
        carts[cart_id]["items"] = {}
    
    carts[cart_id]["items"][item_sku] = cart_item.quantity
    return {"success": True}


class CartCheckout(BaseModel):
    payment: str     

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    print(f"DEBUG CHECKOUT: {cart_id} {cart_checkout}")

    # Hardcoding potion prices and types
    potion_details = {
        "green": {"price": 100},
        "red": {"price": 100},
        "blue": {"price": 100}
    }

    # Get current inventory for all potions
    with db.engine.connect() as connection:
        sql_query = """
        SELECT num_green_potions, num_red_potions, num_blue_potions
        FROM global_inventory
        WHERE num_green_potions > 0 OR num_red_potions > 0 OR num_blue_potions > 0;
        """
        result = connection.execute(sqlalchemy.text(sql_query))
        inventory_data = result.fetchone()

    # Handle no inventory data
    if not inventory_data:
        raise HTTPException(status_code=400, detail="Insufficient potion inventory available")

    num_green_potions, num_red_potions, num_blue_potions = inventory_data

    if num_green_potions < 1 or num_red_potions < 1 or num_blue_potions < 1:
        raise HTTPException(status_code=400, detail="Not all potion types are available for checkout")

    # Proceed with selling one of each type of potion
    with db.engine.begin() as connection:
        total_gold_paid = 0
        for potion_type, details in potion_details.items():
            # Update potion count for each type
            connection.execute(
                sqlalchemy.text(
                    f"UPDATE global_inventory SET num_{potion_type}_potions = num_{potion_type}_potions - 1"
                )
            )
            # total gold paid
            total_gold_paid += details["price"]
        
        # update gold amount by adding the total potion prices
        connection.execute(
            sqlalchemy.text(
                "UPDATE global_inventory SET gold = gold + {}"
            ), {'total_price': total_gold_paid}
        )

    return {
        "total_potions_bought": {"green": 1, "red": 1, "blue": 1},
        "total_gold_paid": total_gold_paid
    }