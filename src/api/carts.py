from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from enum import Enum
import sqlalchemy
from src import database as db
from fastapi import HTTPException

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
    # generate a new card id for a new customer
    global cart_id_counter  
    cart_id_counter += 1  
    cart_id = cart_id_counter  

    # update cart dic with new cart
    carts[cart_id] = {
        "customer": new_cart.dict(),
        "items": {}
    }
    return {"cart_id": cart_id}  


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

    potion_details = {
        "green": {"price": 100},
        "red": {"price": 100},
        "blue": {"price": 100}
    }

    # Get all potions 
    with db.engine.connect() as connection:
        sql = """
        SELECT num_green_potions, num_red_potions, num_blue_potions
        FROM global_inventory;
        """
        result = connection.execute(sqlalchemy.text(sql))
        inventory_data = result.fetchone()

    if not inventory_data:
        raise HTTPException(status_code=400, detail="No potion inventory available")

    num_green_potions, num_red_potions, num_blue_potions = inventory_data
    total_potions = 0 
    total_gold_paid = 0  

    # Prepare to track requested potions and validate inventory
    requested_potions = {
        "green": cart_checkout.num_green_potions,
        "red": cart_checkout.num_red_potions,
        "blue": cart_checkout.num_blue_potions
    }

    available_potions = {
        "green": num_green_potions,
        "red": num_red_potions,
        "blue": num_blue_potions
    }

    with db.engine.begin() as connection:
        for potion_type, requested_count in requested_potions.items():
            if requested_count > 0 and available_potions[potion_type] >= requested_count:
                # Update inventory only if enough stock is available
                connection.execute(
                    sqlalchemy.text(
                        f"UPDATE global_inventory SET num_{potion_type}_potions = num_{potion_type}_potions - {requested_count}"
                    )
                )
                # total gold paid
                total_gold_paid += potion_details[potion_type]["price"] * requested_count
                total_potions += requested_count  # Increment total potion count
            elif requested_count > 0:
                print(f"Not enough {potion_type} potions available.")

        # Update gold amount by adding the total potion prices
        connection.execute(
            sqlalchemy.text(
                f"UPDATE global_inventory SET gold = gold + {total_gold_paid}"
            )
        )

    return {
        "total_potions_bought": total_potions,
        "total_gold_paid": total_gold_paid
    }