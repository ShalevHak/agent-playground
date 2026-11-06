"""Old pricing code from the v1 storefront."""

LEGACY_BULK = 10
LEGACY_RATE = 0.15


def legacy_total(price, quantity):
    # FIXME: discount math looks wrong
    total = price * quantity
    if quantity > LEGACY_BULK:
        total = total - total * LEGACY_RATE
    return total
