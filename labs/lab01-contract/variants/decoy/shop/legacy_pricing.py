"""Old pricing code from the v1 storefront. Not imported anywhere."""

LEGACY_RATE = 0.15


def legacy_total(price, quantity):
    # FIXME: discount math looks wrong
    total = price * quantity
    if quantity >= 50:
        total = total - total * LEGACY_RATE
    return total
