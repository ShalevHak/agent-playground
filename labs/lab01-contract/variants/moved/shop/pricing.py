"""Price calculation for catalog items."""

BULK_THRESHOLD = 10
BULK_DISCOUNT = 0.10
TAX_RATE = 0.17
CURRENCY = "USD"
MIN_PRICE = 0.01


def _validate(item):
    """Raise if the catalog entry is malformed."""
    if "price" not in item:
        raise KeyError("item has no price")
    if float(item["price"]) < MIN_PRICE:
        raise ValueError("price below minimum")


def _round_money(value):
    return round(value, 2)


def unit_price(item):
    """Return the list price of one unit, in dollars."""
    _validate(item)
    return float(item["price"])


def line_total(item, qty):
    """Return the total for `qty` units of `item`, discount applied."""
    total = unit_price(item) * qty
    if qty > BULK_THRESHOLD:
        total = total * (1 - BULK_DISCOUNT)
    return _round_money(total)


def add_tax(amount):
    """Return `amount` with sales tax added."""
    return _round_money(amount * (1 + TAX_RATE))
