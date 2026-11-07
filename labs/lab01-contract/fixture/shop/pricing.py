"""Price calculation for catalog items."""

BULK_THRESHOLD = 10
BULK_DISCOUNT = 0.10
TAX_RATE = 0.17


def unit_price(item):
    """Return the list price of one unit, in dollars."""
    return float(item["price"])


def line_total(item, qty):
    """Return the total for `qty` units of `item`, discount applied."""
    total = unit_price(item) * qty
    if qty > BULK_THRESHOLD:
        total = total * (1 - BULK_DISCOUNT)
    return round(total, 2)


def add_tax(amount):
    """Return `amount` with sales tax added."""
    return round(amount * (1 + TAX_RATE), 2)
