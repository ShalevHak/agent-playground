"""Render carts as plain-text receipts."""


def money(amount):
    return "$%.2f" % amount


def receipt(cart):
    rows = ["%-20s x%-3d %10s" % (name, qty, money(total))
            for name, qty, total in cart.lines()]
    rows.append("-" * 36)
    rows.append("%-25s %10s" % ("Subtotal", money(cart.subtotal())))
    rows.append("%-25s %10s" % ("Total (with tax)", money(cart.total())))
    return "\n".join(rows)
