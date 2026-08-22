from store.models import Order
from store.protocols import PaymentStrategy


class CreditCardPayment:
    def process(self, order: Order, amount: float) -> str:
        card = order.customer.credit_card
        print(f"[payment] Charging card {card} {amount:.2f}")
        return f"paid_by_credit_card:{amount:.2f}"


class PaypalPayment:
    def process(self, order: Order, amount: float) -> str:
        email = order.customer.email
        print(f"[payment] Charging PayPal {email} {amount:.2f}")
        return f"paid_by_paypal:{amount:.2f}"


class BitcoinPayment:
    def process(self, order: Order, amount: float) -> str:
        address = order.customer.bitcoin_address
        print(f"[payment] Charging BTC {address} {amount:.2f}")
        return f"paid_by_bitcoin:{amount:.2f}"


class PaymentProcessor:
    def __init__(self):
        self._strategies: dict[str, PaymentStrategy] = {
            "credit_card": CreditCardPayment(),
            "paypal": PaypalPayment(),
            "bitcoin": BitcoinPayment(),
        }

    def process(self, order: Order, amount: float) -> str:
        method = order.payment_method
        strategy = self._strategies.get(method)
        if strategy is None:
            raise ValueError(f"Unknown payment method: {method!r}")
        return strategy.process(order, amount)
