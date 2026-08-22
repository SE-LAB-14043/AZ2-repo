from store.models import Order
from store.notification import ConsoleEmailSender, ConsoleSmsSender
from store.payment import PaymentProcessor
from store.pricing import DiscountCalculator
from store.protocols import EmailSender, OrderStorage, SmsSender
from store.storage import MySqlDatabase


def validate_order(order: Order) -> None:
    if not order.item_count:
        raise ValueError("Order has no items")
    if not order.payment_method:
        raise ValueError("Order has no payment method")


class PricingEngine:
    def __init__(self, discount_calculator: DiscountCalculator):
        self.discount_calculator = discount_calculator

    def calculate_total(self, order: Order) -> tuple[float, float, float, float]:
        subtotal = order.subtotal
        discount = self.discount_calculator.calculate(order)
        shipping = 5.0 if subtotal < 100 else 0.0
        total = round(subtotal - discount + shipping, 2)
        return subtotal, discount, shipping, total


class ReceiptPrinter:
    def print_receipt(self, order, subtotal, discount, shipping, total, receipt):
        print(f"--- Receipt for order {order.id} ---")
        for item in order.items:
            print(f"  {item.name:20s} x{item.quantity}  ${item.line_total:.2f}")
        print(f"  Subtotal    ${subtotal:.2f}")
        print(f"  Discount   -${discount:.2f}")
        print(f"  Shipping    ${shipping:.2f}")
        print(f"  TOTAL       ${total:.2f}")
        print(f"  Payment     {receipt}")


class OrderService:
    def __init__(
        self,
        discount_calculator: DiscountCalculator | None = None,
        payment_processor: PaymentProcessor | None = None,
        email_sender: EmailSender | None = None,
        sms_sender: SmsSender | None = None,
        database: OrderStorage | None = None,
    ):
        self.discount_calculator = discount_calculator or DiscountCalculator()
        self.payment_processor = payment_processor or PaymentProcessor()
        self.email_sender = email_sender or ConsoleEmailSender()
        self.sms_sender = sms_sender or ConsoleSmsSender()
        self.database = database or MySqlDatabase()
        self.pricing = PricingEngine(self.discount_calculator)
        self.receipt_printer = ReceiptPrinter()

    def process_order(self, order: Order, notify: bool = True) -> Order:
        validate_order(order)
        subtotal, discount, shipping, total = self.pricing.calculate_total(order)
        receipt = self.payment_processor.process(order, total)
        order.status = "paid"
        self.database.save_order(order)
        if notify:
            message = f"Order {order.id} total ${total:.2f} ({receipt})"
            self.email_sender.send_email(order.customer, message)
            self.sms_sender.send_sms(order.customer, message)
        self.receipt_printer.print_receipt(order, subtotal, discount, shipping, total, receipt)
        return order
