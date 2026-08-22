from typing import Protocol

from store.models import Order


class PaymentStrategy(Protocol):
    def process(self, order: Order, amount: float) -> str: ...


class DiscountRule(Protocol):
    def is_applicable(self, order: Order) -> bool: ...
    def calculate(self, order: Order) -> float: ...


class EmailSender(Protocol):
    def send_email(self, customer, message: str) -> None: ...


class SmsSender(Protocol):
    def send_sms(self, customer, message: str) -> None: ...


class PushSender(Protocol):
    def send_push(self, customer, message: str) -> None: ...


class OrderStorage(Protocol):
    def save_order(self, order) -> None: ...
