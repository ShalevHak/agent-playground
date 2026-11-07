from shop.cart import Cart
from shop.formatting import receipt

PEN = {"name": "pen", "price": 2.0}


def test_small_order_full_price():
    cart = Cart()
    cart.add(PEN, 3)
    assert cart.subtotal() == 6.0


def test_large_order_discounted():
    cart = Cart()
    cart.add(PEN, 20)
    assert cart.subtotal() == 36.0


def test_rejects_zero_quantity():
    cart = Cart()
    try:
        cart.add(PEN, 0)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_receipt_has_total():
    cart = Cart()
    cart.add(PEN, 1)
    assert "Total" in receipt(cart)
