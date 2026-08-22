# Refactoring Plan — SOLID Violations

## Scope

Fixes only **8 definite violations** identified in `solid-result.md`. Skips possible violations/smells (SRP 1.2, SRP 1.3, OCP 2.3, ISP 4.3) unless they are naturally resolved by fixing a definite violation. Preserves all existing runtime behavior — output must match before/after.

## Execution Order

Each step is independently testable. Run `python -m store.main` after every step and verify output matches the baseline.

---

## Step 1 — Fix BundleOrder LSP (Finding 3.2)

**Files:** `models.py`, `order_service.py`

**Problem:** `BundleOrder` inherits `Order` but hardcodes `items=[]`. `subtotal` returns 0, `item_count` returns 0. The bundle in the demo computes $5.00 (just shipping) instead of $1829.98. `OrderService` uses `isinstance(order, BundleOrder)` at line 17 as a workaround — proof the substitution is broken.

**Principle:** Liskov Substitution Principle

**Refactoring technique:** Override inherited properties in subclass

**Changes:**

1. **`models.py` — `BundleOrder`** (after line 50): Add `subtotal` and `item_count` property overrides that aggregate across `self.orders`:
   ```python
   @property
   def subtotal(self) -> float:
       return round(sum(o.subtotal for o in self.orders), 2)

   @property
   def item_count(self) -> int:
       return sum(o.item_count for o in self.orders)
   ```

2. **`order_service.py` — `OrderService.process_order`** (line 17): Remove the `isinstance` workaround. The validation becomes a simple check on `item_count`:
   ```python
   if not order.item_count:
       raise ValueError("Order has no items")
   ```

**Expected result:** Bundle receipt shows correct totals:
```
Subtotal    $1829.98
Discount   -$366.00   (VIP 20% of 1829.98)
Shipping    $0.00     (subtotal >= 100)
TOTAL       $1463.98
```

**Risks:**
- Low. The `isinstance` removal changes validation behavior — previously bundles always passed validation (via the isinstance bypass). Now they pass via correct `item_count`. Same outcome, cleaner path.
- The `items` field on `BundleOrder` is still `[]`. Code that iterates `bundle.items` will see nothing. This is acceptable — the bundle's items are accessed via `bundle.orders`.

**Test:** Run `python -m store.main`. Compare bundle output before/after.

---

## Step 2 — Fix Notification ISP + LSP (Findings 3.1 + 4.1)

**Files:** `notification.py`, `order_service.py`

**Problem:** `NotificationService` forces all consumers to depend on 3 methods (`send_email`, `send_sms`, `send_push`). `SmsOnlyNotifier` raises `NotImplementedError` on 2 of them. `OrderService` only uses 2 of 3.

**Principle:** Interface Segregation Principle + Liskov Substitution Principle

**Refactoring technique:** Interface Segregation (split fat interface) + Replace Inheritance with Composition

**Changes:**

1. **`notification.py` — Replace the monolithic class with per-channel protocols and concrete implementations:**
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
   Delete `NotificationService` and `SmsOnlyNotifier` entirely. They are replaced by composing the per-channel classes. An `SmsOnlyNotifier` equivalent is simply a `ConsoleSmsSender` — no inheritance needed.

2. **`order_service.py` — Update imports and constructor:**
   ```python
   from store.notification import ConsoleEmailSender, ConsoleSmsSender
   ```
   Update `__init__`:
   ```python
   self.email_sender = ConsoleEmailSender()
   self.sms_sender = ConsoleSmsSender()
   ```
   Update `process_order` (lines 38-39):
   ```python
   self.email_sender.send_email(order.customer, message)
   self.sms_sender.send_sms(order.customer, message)
   ```

**Expected result:** Identical notification output in demo:
```
[email] to alice@example.com: Order 101 total $819.99 (paid_by_credit_card:819.99)
[sms] to 555-0100: Order 101 total $819.99 (paid_by_credit_card:819.99)
```

**Risks:**
- Medium. This is a breaking change to `notification.py` — any code using `NotificationService` or `SmsOnlyNotifier` directly will break. In this project, only `OrderService` uses them, so the blast radius is contained.
- The old `SmsOnlyNotifier` class disappears. If external code referenced it, it would need updating. Acceptable for a lab project.

**Test:** Run `python -m store.main`. Verify notification lines match baseline exactly.

---

## Step 3 — Fix Payment OCP (Finding 2.1)

**Files:** `payment.py`, `order_service.py`

**Problem:** `PaymentProcessor.process` is a 5-branch `if/elif` chain. Adding cash required editing this method. Each new payment method will require another edit.

**Principle:** Open/Closed Principle

**Refactoring technique:** Strategy Pattern + Registry

**Changes:**

1. **`payment.py` — Define strategy protocol and per-method implementations:**
   ```python
   from typing import Protocol
   from store.models import Order

   class PaymentStrategy(Protocol):
       def process(self, order: Order, amount: float) -> str: ...


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
   ```

2. **`payment.py` — Rewrite `PaymentProcessor` as a registry-based dispatcher:**
   ```python
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

**Expected result:** Identical payment output for all 4 methods. The `process` method signature is unchanged, so `order_service.py` needs no changes.

**Risks:**
- Low-Medium. The public API (`PaymentProcessor.process`) is preserved — `order_service.py` calls it the same way. Internal implementation changes are encapsulated.
- Adding a new payment method now means: create a class, add one line to `__init__`. No existing method modification.
- The registry dict is hardcoded in `__init__`. For a lab project this is fine; a production system might load strategies dynamically.

**Test:** Run `python -m store.main`. Verify all 4 payment outputs match baseline.

---

## Step 4 — Fix Discount OCP (Finding 2.2)

**Files:** `pricing.py`, `order_service.py`

**Problem:** `DiscountCalculator.calculate` is a 4-branch `if/elif` chain. Adding a new rule requires modifying this method.

**Principle:** Open/Closed Principle

**Refactoring technique:** Strategy Pattern + Chain of Responsibility

**Changes:**

1. **`pricing.py` — Define rule protocol and per-rule implementations:**
   ```python
   from typing import Protocol
   from store.models import Order

   class DiscountRule(Protocol):
       def is_applicable(self, order: Order) -> bool: ...
       def calculate(self, order: Order) -> float: ...


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
   ```

2. **`pricing.py` — Rewrite `DiscountCalculator` as a rule engine:**
   ```python
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
- Low-Medium. The `calculate(order) -> float` signature is preserved. `order_service.py` calls it the same way.
- The new `__init__` accepts an optional `rules` list — this is a DIP improvement (injectable rules) that comes free with the OCP fix.
- The old code had a subtle priority: VIP > bulk > coupon (first match wins). The new code preserves this by iterating in the same order and returning on first match.

**Test:** Run `python -m store.main`. Verify discount amounts match baseline.

---

## Step 5 — Fix DIP + SRP for OrderService (Findings 5.1 + 5.2 + 1.1)

**Files:** `order_service.py`, `main.py`, new `store/protocols.py`

**Problem:** `OrderService` instantiates all 4 concrete dependencies inline (DIP). `process_order` performs 6 responsibilities (SRP). No abstractions exist anywhere in the project (systemic DIP).

**Principle:** Dependency Inversion Principle + Single Responsibility Principle

**Refactoring technique:** Constructor Injection + Extract Class + Introduce Protocol

**Changes:**

1. **New file `store/protocols.py` — Define all abstractions in one place:**
   ```python
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

   class OrderStorage(Protocol):
       def save_order(self, order) -> None: ...
   ```

2. **`order_service.py` — Add constructor injection with defaults:**
   ```python
   from store.protocols import EmailSender, SmsSender, OrderStorage
   from store.pricing import DiscountCalculator

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
   ```
   Defaults preserve backward compatibility — `main.py` still calls `OrderService()` with no args.

3. **`order_service.py` — Extract SRP steps from `process_order`:**

   a. **Extract validation** as a module-level function:
   ```python
   def validate_order(order: Order) -> None:
       if not order.item_count:
           raise ValueError("Order has no items")
       if not order.payment_method:
           raise ValueError("Order has no payment method")
   ```

   b. **Extract `PricingEngine`** — wrap the pricing logic:
   ```python
   class PricingEngine:
       def __init__(self, discount_calculator: DiscountCalculator):
           self.discount_calculator = discount_calculator

       def calculate_total(self, order: Order) -> tuple[float, float, float, float]:
           subtotal = order.subtotal
           discount = self.discount_calculator.calculate(order)
           shipping = 5.0 if subtotal < 100 else 0.0
           total = round(subtotal - discount + shipping, 2)
           return subtotal, discount, shipping, total
   ```

   c. **Extract `ReceiptPrinter`** (move `_print_receipt`):
   ```python
   class ReceiptPrinter:
       def print(self, order, subtotal, discount, shipping, total, receipt):
           print(f"--- Receipt for order {order.id} ---")
           for item in order.items:
               print(f"  {item.name:20s} x{item.quantity}  ${item.line_total:.2f}")
           print(f"  Subtotal    ${subtotal:.2f}")
           print(f"  Discount   -${discount:.2f}")
           print(f"  Shipping    ${shipping:.2f}")
           print(f"  TOTAL       ${total:.2f}")
           print(f"  Payment     {receipt}")
   ```

   d. **`process_order` becomes a thin orchestrator:**
   ```python
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
       self.receipt_printer.print(order, subtotal, discount, shipping, total, receipt)
       return order
   ```

4. **`main.py` — No changes needed.** `OrderService()` with no args uses all defaults. Backward compatible.

**Expected result:** Identical output for all demo orders. `main.py` unchanged.

**Risks:**
- Medium. This is the largest change — it restructures `OrderService` and introduces a new file.
- The `PricingEngine` class, `validate_order` function, and `ReceiptPrinter` class live in `order_service.py` (not separate files) to avoid over-engineering. They can be split later if needed.
- `PaymentProcessor` and `DiscountCalculator` are already refactored in Steps 3-4. This step wires them in via injection.
- Backward compatibility is preserved via default arguments — existing callers don't break.

**Test:** Run `python -m store.main`. Verify complete output matches baseline exactly.

---

## Baseline Output (for verification)

After Step 1 (BundleOrder fix), the corrected output:
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

Steps 2-5 preserve this corrected output.

---

## Summary

| Step | Principle Fixed | Files Changed | Risk | Verification |
|---|---|---|---|---|
| 1 | LSP (BundleOrder) | `models.py`, `order_service.py` | Low | Bundle total changes from $5.00 → $1463.98 (bug fix) |
| 2 | ISP + LSP (Notification) | `notification.py`, `order_service.py` | Medium | Notification output identical |
| 3 | OCP (Payment) | `payment.py` | Low-Medium | All 4 payment outputs identical |
| 4 | OCP (Discount) | `pricing.py` | Low-Medium | Discount amounts identical |
| 5 | DIP + SRP (OrderService) | `order_service.py`, new `protocols.py` | Medium | Complete output identical to Step 1 |

**Violations fixed:** 8 definite violations (OCP×2, LSP×2, ISP×1, DIP×2, SRP×1)

**Violations skipped:** 4 possible violations/smells (SRP 1.2, SRP 1.3, OCP 2.3, ISP 4.3) — low severity, not worth the abstraction cost at this project's scale.
