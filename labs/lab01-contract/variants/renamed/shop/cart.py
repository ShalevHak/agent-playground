"""A shopping cart holding catalog items and quantities."""
from shop.rates import line_total, add_tax


class Cart:
    def __init__(self):
        self._lines = []

    def add(self, item, qty=1):
        if qty < 1:
            raise ValueError("quantity must be at least 1")
        self._lines.append((item, qty))

    def lines(self):
        """Yield (name, qty, total) for each line."""
        for item, qty in self._lines:
            yield item["name"], qty, line_total(item, qty)

    def subtotal(self):
        return round(sum(total for _, _, total in self.lines()), 2)

    def total(self):
        return add_tax(self.subtotal())

    def count(self):
        return sum(qty for _, qty in self._lines)
