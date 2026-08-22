from store.models import Order
from store.protocols import DiscountRule


class VipDiscount:
    def is_applicable(self, order: Order) -> bool:
        return order.customer.is_vip

    def calculate(self, order: Order) -> float:
        return round(order.subtotal * 0.20, 2)


class BulkDiscount:
    def is_applicable(self, order: Order) -> bool:
        return order.item_count >= 10

    def calculate(self, order: Order) -> float:
        return round(order.subtotal * 0.10, 2)


class CouponDiscount:
    def is_applicable(self, order: Order) -> bool:
        return "WELCOME10" in order.coupons

    def calculate(self, order: Order) -> float:
        return round(order.subtotal * 0.10, 2)


class DiscountCalculator:
    def __init__(self, rules: list[DiscountRule] | None = None):
        self._rules = rules or [VipDiscount(), BulkDiscount(), CouponDiscount()]

    def calculate(self, order: Order) -> float:
        for rule in self._rules:
            if rule.is_applicable(order):
                return rule.calculate(order)
        return 0.0
