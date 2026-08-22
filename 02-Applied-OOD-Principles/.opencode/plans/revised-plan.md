# Revised Refactoring Plan — SOLID Violations

## What Changed from the Original Plan

| # | Change | Why |
|---|---|---|
| 1 | BundleOrder step now explicitly documents the behavior change as a **bug fix**, not "identical behavior" | The bundle currently computes $5.00 (wrong). After the fix it computes $1463.98 (correct). This is a correctness improvement, not a behavior preservation. |
| 2 | `PaymentStrategy` and `DiscountRule` protocols are defined **once** in `store/protocols.py` and imported everywhere | Avoids duplicate definitions in `payment.py` and `protocols.py`. Single source of truth. |
| 3 | Concrete discount rules (`VipDiscount`, etc.) stay in `pricing.py` | Only the protocol goes to `protocols.py`. Concrete implementations stay with their module. |
| 4 | SRP helpers (`validate_order`, `PricingEngine`, `ReceiptPrinter`) remain in `order_service.py` | No new modules. Keeps the project simple. |
| 5 | Clarified that `main.py` needs no changes in any step | Backward-compatible defaults in `OrderService.__init__` mean existing callers work unchanged. |

---

## Scope

Fixes **8 definite violations** identified in `solid-result.md`. Skips possible violations/smells (SRP 1.2, SRP 1.3, OCP 2.3, ISP 4.3). Each step is independently testable.

---

## Step 1 — Fix BundleOrder LSP (Finding 3.2) — BUG FIX

**Files:** `models.py`, `order_service.py`

**Current problem:** `BundleOrder` inherits `Order` but hardcodes `items=[]` (models.py:49). Inherited `subtotal` returns 0.0, `item_count` returns 0. The bundle containing two orders worth $1829.98 currently pays only $5.00 (shipping on a $0 subtotal). `OrderService` uses `isinstance(order, BundleOrder)` at line 17 as a workaround to bypass validation — proof the substitution is broken.

**Principle:** Liskov Substitution Principle

**Refactoring technique:** Override inherited properties in subclass

**Changes:**

1. **`models.py` — `BundleOrder` class** (after line 50): Add property overrides:
   ```python
   @property
   def subtotal(self) -> float:
       return round(sum(o.subtotal for o in self.orders), 2)

   @property
   def item_count(self) -> int:
       return sum(o.item_count for o in self.orders)
   ```

2. **`order_service.py` — `OrderService.process_order`** (line 17): Remove the `isinstance` workaround. Replace with:
   ```python
   if not order.item_count:
       raise ValueError("Order has no items")
   ```
   After the override, `order.item_count` returns the correct aggregated count, so bundles pass validation naturally.

**Expected result — BEHAVIOR CHANGE (bug fix):**

Before (incorrect):
```
Subtotal    $0.00
Discount   -$0.00
Shipping    $5.00
TOTAL       $5.00
```

After (correct):
```
Subtotal    $1829.98
Discount   -$366.00
Shipping    $0.00
TOTAL       $1463.98
```

This is a **bug fix**, not behavior preservation. The previous output was wrong because `BundleOrder.subtotal` always returned 0.

**Risks:**
- Low. The `isinstance` removal changes validation behavior — previously bundles always passed validation (via the isinstance bypass). Now they pass via correct `item_count`. Same outcome, cleaner path.
- The `items` field on `BundleOrder` is still `[]`. Code that iterates `bundle.items` directly will see nothing. The bundle's items are accessed via `bundle.orders`.

**Test:** Run `python -m store.main`. Verify bundle receipt shows the corrected totals above.

---

## Step 2 — Fix Notification ISP + LSP (Findings 3.1 + 4.1)

**Files:** `notification.py`, `order_service.py`

**Current problem:** `NotificationService` forces all consumers to depend on 3 methods (`send_email`, `send_sms`, `send_push`). `SmsOnlyNotifier` raises `NotImplementedError` on 2 of them. `OrderService` only uses `send_email` and `send_sms` — never `send_push`.

**Principle:** Interface Segregation Principle + Liskov Substitution Principle

**Refactoring technique:** Interface Segregation (split fat interface) + Replace Inheritance with Composition

**Changes:**

1. **`notification.py` — Replace monolithic classes with per-channel protocols and concrete implementations:**
   ```python
   from typing import Protocol

   class EmailSender(Protocol):
       def send_email(self, customer, message: str) -> None: ...

   class SmsSender(Protocol):
       def send_sms(self, customer, message: str) -> None: ...

   class PushSender(Protocol):
       def send_push(self, customer, message: str) -> None: ...


   class ConsoleEmailSender:
       def send_email(self, customer, message: str) -> None:
           print(f"[email] to {customer.email}: {message}")


   class ConsoleSmsSender:
       def send_sms(self, customer, message: str) -> None:
           print(f"[sms] to {customer.phone}: {message}")


   class ConsolePushSender:
       def send_push(self, customer, message: str) -> None:
           print(f"[push] to {customer.name}: {message}")
   ```
   Delete `NotificationService` and `SmsOnlyNotifier` entirely. An SMS-only notifier is simply a `ConsoleSmsSender` — no inheritance needed.

2. **`order_service.py` — Update imports and constructor:**
   ```python
   from store.notification import ConsoleEmailSender, ConsoleSmsSender
   ```
   In `__init__`:
   ```python
   self.email_sender = ConsoleEmailSender()
   self.sms_sender = ConsoleSmsSender()
   ```
   In `process_order` (lines 38-39), change:
   ```python
   self.email_sender.send_email(order.customer, message)
   self.sms_sender.send_sms(order.customer, message)
   ```

**Expected result:** Identical notification output — no behavior change:
```
[email] to alice@example.com: Order 101 total $819.99 (paid_by_credit_card:819.99)
[sms] to 555-0100: Order 101 total $819.99 (paid_by_credit_card:819.99)
```

**Risks:**
- Medium. `NotificationService` and `SmsOnlyNotifier` are deleted. Any code referencing them directly breaks. Only `OrderService` uses them — blast radius is contained.
- `SmsOnlyNotifier` disappears. Its equivalent is composing a `ConsoleSmsSender` where needed — cleaner than inheritance.

**Test:** Run `python -m store.main`. Verify notification lines match baseline.

---

## Step 3 — Fix Payment OCP (Finding 2.1)

**Files:** `payment.py`, new `store/protocols.py`

**Current problem:** `PaymentProcessor.process` is a 5-branch `if/elif` chain. Adding cash required editing this method. Each new payment method requires another edit.

**Principle:** Open/Closed Principle

**Refactoring technique:** Strategy Pattern + Registry

**Changes:**

1. **New file `store/protocols.py`** — Define `PaymentStrategy` protocol (single source of truth):
   ```python
   from typing import Protocol
   from store.models import Order

   class PaymentStrategy(Protocol):
       def process(self, order: Order, amount: float) -> str: ...
   ```

2. **`payment.py` — Define per-method strategy classes and rewrite `PaymentProcessor`:**
   ```python
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


   class CashPayment:
       def process(self, order: Order, amount: float) -> str:
           print(f"[payment] Cash payment of {amount:.2f}")
           return f"paid_by_cash:{amount:.2f}"


   class PaymentProcessor:
       def __init__(self):
           self._strategies: dict[str, PaymentStrategy] = {
               "credit_card": CreditCardPayment(),
               "paypal": PaypalPayment(),
               "bitcoin": BitcoinPayment(),
               "cash": CashPayment(),
           }

       def process(self, order: Order, amount: float) -> str:
           method = order.payment_method
           strategy = self._strategies.get(method)
           if strategy is None:
               raise ValueError(f"Unknown payment method: {method!r}")
           return strategy.process(order, amount)
   ```

**Expected result:** Identical payment output for all 4 methods. `PaymentProcessor.process(order, amount)` signature unchanged — `order_service.py` needs no changes in this step.

**Risks:**
- Low-Medium. Public API preserved. Internal implementation encapsulated.
- Adding a new payment method: create a class, add one line to `_strategies` dict. No existing method modification.

**Test:** Run `python -m store.main`. Verify all 4 payment outputs match baseline.

---

## Step 4 — Fix Discount OCP (Finding 2.2)

**Files:** `pricing.py`, `store/protocols.py`

**Current problem:** `DiscountCalculator.calculate` is a 4-branch `if/elif` chain. Adding a new rule requires modifying this method.

**Principle:** Open/Closed Principle

**Refactoring technique:** Strategy Pattern + Chain of Responsibility

**Changes:**

1. **`store/protocols.py`** — Add `DiscountRule` protocol (single source of truth, imported by `pricing.py`):
   ```python
   from store.models import Order

   class DiscountRule(Protocol):
       def is_applicable(self, order: Order) -> bool: ...
       def calculate(self, order: Order) -> float: ...
   ```

2. **`pricing.py` — Define per-rule classes and rewrite `DiscountCalculator`:**
   ```python
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
   ```

**Expected result:** Identical discount output for all demo orders:
- Laptop (VIP): $205.00 discount
- Books (regular, 4 items): $0.00 discount
- Headphones (regular, 1 item): $0.00 discount
- Bundle (VIP, aggregated): $366.00 discount (20% of $1829.98)

**Risks:**
- Low-Medium. `DiscountCalculator.calculate(order) -> float` signature preserved. `order_service.py` calls it the same way.
- First-match-wins priority preserved (VIP > bulk > coupon) — same iteration order as the original if/elif chain.
- The new `__init__` accepts an optional `rules` list — free DIP improvement.

**Test:** Run `python -m store.main`. Verify discount amounts match baseline.

---

## Step 5 — Fix DIP + SRP for OrderService (Findings 5.1 + 5.2 + 1.1)

**Files:** `store/protocols.py`, `order_service.py`, `notification.py`

**Current problem:** `OrderService` instantiates all 4 concrete dependencies inline (DIP). `process_order` performs 6 responsibilities in one method (SRP). No abstractions exist anywhere (systemic DIP).

**Principle:** Dependency Inversion Principle + Single Responsibility Principle

**Refactoring technique:** Constructor Injection + Extract Class + Introduce Protocol

**Changes:**

1. **`store/protocols.py`** — Add remaining abstractions (`PaymentStrategy` and `DiscountRule` already exist from Steps 3-4):
   ```python
   class EmailSender(Protocol):
       def send_email(self, customer, message: str) -> None: ...

   class SmsSender(Protocol):
       def send_sms(self, customer, message: str) -> None: ...

   class OrderStorage(Protocol):
       def save_order(self, order) -> None: ...
   ```
   Note: `EmailSender` and `SmsSender` are defined here AND in `notification.py`. To avoid duplication, define them once in `protocols.py` and import in `notification.py`:
   ```python
   # notification.py
   from store.protocols import EmailSender, SmsSender

   class ConsoleEmailSender:
       def send_email(self, customer, message: str) -> None:
           print(f"[email] to {customer.email}: {message}")

   class ConsoleSmsSender:
       def send_sms(self, customer, message: str) -> None:
           print(f"[sms] to {customer.phone}: {message}")
   ```

2. **`order_service.py` — Add constructor injection with backward-compatible defaults:**
   ```python
   from store.protocols import EmailSender, SmsSender, OrderStorage
   from store.pricing import DiscountCalculator
   from store.payment import PaymentProcessor
   from store.notification import ConsoleEmailSender, ConsoleSmsSender
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
   ```
   `process_order` is now a thin orchestrator: 10 lines of delegation, no inline logic.

**Expected result:** Identical output for all demo orders. `main.py` unchanged — `OrderService()` with no args uses all defaults.

**Risks:**
- Medium. Largest change — restructures `OrderService` and introduces `protocols.py` + helpers.
- `PricingEngine`, `ReceiptPrinter`, and `validate_order` stay in `order_service.py` (no new modules). Can be split later if needed.
- Backward compatibility preserved via default arguments — existing callers don't break.
- The `notification.py` protocols (`EmailSender`, `SmsSender`) are now imported from `protocols.py` rather than defined locally. `notification.py` becomes a concrete implementations file only.

**Test:** Run `python -m store.main`. Verify complete output matches the Step 1 corrected baseline.

---

## Final Output (after all 5 steps)

```
>>> Checkout a simple order
[payment] Charging card 4111 1111 1111 1111 819.99
[email] to alice@example.com: Order 101 total $819.99 (paid_by_credit_card:819.99)
[sms] to 555-0100: Order 101 total $819.99 (paid_by_credit_card:819.99)
--- Receipt for order 101 ---
  Laptop               x1  $999.99
  Mouse                x1  $25.00
  Subtotal    $1024.99
  Discount   -$205.00
  Shipping    $0.00
  TOTAL       $819.99
  Payment     paid_by_credit_card:819.99

>>> Checkout a bundle of two orders
[payment] Charging card 4111 1111 1111 1111 1463.98
[email] to alice@example.com: Order 103 total $1463.98 (paid_by_credit_card:1463.98)
[sms] to 555-0100: Order 103 total $1463.98 (paid_by_credit_card:1463.98)
--- Receipt for order 103 ---
  Subtotal    $1829.98
  Discount   -$366.00
  Shipping    $0.00
  TOTAL       $1463.98
  Payment     paid_by_credit_card:1463.98

>>> Checkout a cash payment order
[payment] Cash payment of 84.99
[email] to bob@example.com: Order 104 total $84.99 (paid_by_cash:84.99)
[sms] to 555-0199: Order 104 total $84.99 (paid_by_cash:84.99)
--- Receipt for order 104 ---
  Headphones           x1  $79.99
  Subtotal    $79.99
  Discount   -$0.00
  Shipping    $5.00
  TOTAL       $84.99
  Payment     paid_by_cash:84.99
```

---

## Summary

| Step | Principle Fixed | Files Changed | Behavior Change | Risk |
|---|---|---|---|---|
| 1 | LSP (BundleOrder) | `models.py`, `order_service.py` | **Bug fix:** Bundle total $5.00 → $1463.98 | Low |
| 2 | ISP + LSP (Notification) | `notification.py`, `order_service.py` | None | Medium |
| 3 | OCP (Payment) | `payment.py`, new `protocols.py` | None | Low-Medium |
| 4 | OCP (Discount) | `pricing.py`, `protocols.py` | None | Low-Medium |
| 5 | DIP + SRP (OrderService) | `order_service.py`, `protocols.py`, `notification.py` | None | Medium |

**Violations fixed:** 8 definite violations (OCP×2, LSP×2, ISP×1, DIP×2, SRP×1)

**Violations skipped:** 4 possible violations/smells (SRP 1.2, SRP 1.3, OCP 2.3, ISP 4.3)

**Behavior changes:** 1 bug fix (Step 1 — BundleOrder subtotal/item_count)
