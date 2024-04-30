from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from enum import Enum
import sqlalchemy
from src import database as db
from fastapi import HTTPException
from datetime import datetime

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
    if sort_order == search_sort_order.desc:
        order = "DESC"
    else:
        order = "ASC"

    sql_to_execute = f"""
    SELECT
        cart.customer_name,
        ci.item_sku,
        ci.quantity,
        ci.cart_id,
        cart.created_at AS timestamp
    FROM
        cart_items ci
    JOIN
        carts cart ON ci.cart_id = cart_id
    WHERE
        (:customer_name = '' AND :potion_sku = '') OR
        (:customer_name != '' AND :potion_sku != '' AND cart.customer_name ILIKE :customer_name AND ci.item_sku ILIKE :potion_sku) OR
        (:customer_name = '' AND ci.item_sku ILIKE :potion_sku) OR
        (:potion_sku = '' AND cart.customer_name ILIKE :customer_name)
    ORDER BY
        {sort_col.value} {order}, ci.cart_id ASC
    LIMIT
        5 OFFSET :cur_page
    """

    cur_page = int(search_page) * 5  # Pagination is set to 5 items per page

    return_list = []
    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text(sql_to_execute), {
            "cur_page": cur_page, 
            "customer_name": f'%{customer_name}%', 
            "potion_sku": f'%{potion_sku}%'
        })
        for row in result:
            plural = "s" if row.quantity > 1 else ""
            return_list.append({
                "cart_id": row.cart_id,
                "item_sku": f"{row.quantity} {row.item_sku.replace('_', ' ')}{plural}",
                "customer_name": row.customer_name,
                "timestamp": row.timestamp.isoformat(),
            })

    next_page = str(int(search_page) + 1) if len(return_list) == 5 else ""
    previous_page = str(int(search_page) - 1) if int(search_page) > 0 else ""

    return {
        "previous": previous_page,
        "next": next_page,
        "results": return_list,
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

@router.post("/")
def create_cart(new_cart: Customer):
    """Create a new cart with a unique identifier for a specific customer."""

    sql = """
    INSERT INTO carts (created_at, character_class, customer_name, level)
    VALUES (:created_at, :character_class, :customer_name, :level)
    RETURNING id;
    """
    try:
        with db.engine.connect() as connection:
            result = connection.execute(sqlalchemy.text(sql), {
                'created_at': datetime.now(),
                'character_class': new_cart.character_class,
                'customer_name': new_cart.customer_name,
                'level': new_cart.level
            })
            connection.commit()
            cart_id = result.fetchone()[0]
            print(f"DEBUG: CREATE CART: {cart_id}")
            return {"cart_id": cart_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to create cart") from e


class CartItem(BaseModel):
    quantity: int

@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """Update the quantity of an item in the cart."""

    validate_cart_sql="""
    SELECT EXISTS(SELECT 1 FROM carts WHERE id = :cart_id);
    """
    
    new_cart_item_sql = """
        INSERT INTO cart_items (cart_id, quantity, item_sku, potion_id, created_at) 
        SELECT :cart_id, :quantity, :item_sku, potions.id, :created_at
        FROM potions WHERE potions.sku = :item_sku
        """
    try:
        with db.engine.connect() as connection:

            # validate cart id
            connection.execute(sqlalchemy.text(validate_cart_sql), {'cart_id': cart_id})

            # set item quanity in cart
            connection.execute(sqlalchemy.text(new_cart_item_sql), {
                'cart_id': cart_id,
                'quantity': cart_item.quantity,
                'item_sku': item_sku,
                'created_at': datetime.now()
            })
            connection.commit()
            return {"success" : True}
    except Exception as e:
        print(e)
        return {"success" : False}


class CartCheckout(BaseModel):
    payment: str     

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    print(f"DEBUG: CHECKOUT for Cart ID: {cart_id} with Payment Method: {cart_checkout.payment}")

    with db.engine.begin() as connection:
        #fetch all potions from cart_items
        cart_sql = """
            SELECT cart_items.quantity, cart_items.potion_id, potions.price
            FROM cart_items
            JOIN potions ON cart_items.potion_id = potions.id
            WHERE cart_items.cart_id = :cart_id;
        """
        result = connection.execute(sqlalchemy.text(cart_sql), {'cart_id': cart_id})
        cart_items = result.mappings().all() 
        if not cart_items:
            raise HTTPException(status_code=404, detail="Cart is empty or does not exist")

        total_gold_paid = 0

        # process items in cart
        for item in cart_items:
            quantity = item['quantity']
            price_per_potion = item['price']

            total_cost = price_per_potion * quantity
            total_gold_paid += total_cost

            # update potion inventory
            update_potions = """
            INSERT INTO potion_ledger (potion_id, quantity_change) VALUES(:potion_id, :quantity_change)
            """
            connection.execute(sqlalchemy.text(update_potions), {
                'potion_id': item['potion_id'],
                'quantity_change': -quantity
            })

        # update gold
        if total_gold_paid > 0:
            connection.execute(sqlalchemy.text("INSERT INTO gold_ledger (quantity_change) VALUES (:quantity_change)"), {'quantity_change': total_gold_paid})

    return {
        "total_potions_bought": sum(item['quantity'] for item in cart_items),
        "total_gold_paid": total_gold_paid
    }