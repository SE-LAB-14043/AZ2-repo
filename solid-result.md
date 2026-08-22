# SOLID Principles Review — store/ (Post Cash Payment)

---

## 1. SRP — Single Responsibility Principle

*A class should have one, and only one, reason to change.*

### Finding 1.1 — `OrderService.process_order`

- **File:** `order_service.py:15-43`
- **Class:** `OrderService`
- **Classification:** Definite violation
- **Evidence:** The `process_order` method performs six distinct responsibilities in sequence:
  1. **Validation** (lines 17-20) — checks item presence and payment method
  2. **Pricing** (lines 23-26) — computes subtotal, discount, shipping, total
  3. **Payment** (line 29) — delegates to `PaymentProcessor`
  4. **Persistence** (lines 32-33) — updates status and saves to database
  5. **Notification** (lines 36-39) — sends email and SMS
  6. **Receipt printing** (line 42) — formats and prints output

  The cash payment addition demonstrated this: adding a new payment method required touching `PaymentProcessor` but the orchestration in `OrderService` also had to be understood and verified, even though it was not edited. A change in notification policy (e.g. no SMS for cash orders) would require editing this method.
- **Refactoring:** Extract each step into a collaborator: `OrderValidator`, `PricingEngine`, `NotificationDispatcher`, `ReceiptPrinter`. `OrderService` becomes a thin orchestrator that delegates to injected collaborators.
- **Why appropriate:** Each collaborator has a single responsibility. Changes to pricing rules, notification channels, or persistence don't risk breaking each other. Testing becomes straightforward — each collaborator can be mocked independently.

### Finding 1.2 — `OrderService._print_receipt`

- **File:** `order_service.py:45-53`
- **Class:** `OrderService`
- **Classification:** Possible violation
- **Evidence:** Receipt formatting is a private method on `OrderService`, mixing I/O formatting with orchestration logic. Changing receipt format (JSON, HTML, file output) requires editing this class.
- **Severity:** Low. The method is short and isolated. In a larger system this would matter more.
- **Refactoring:** Extract to a standalone `ReceiptPrinter` class.
- **Why appropriate:** Separates formatting concerns from orchestration.

### Finding 1.3 — `Order` dataclass

- **File:** `models.py:30-44`
- **Class:** `Order`
- **Classification:** No violation
- **Evidence:** `subtotal` and `item_count` are pure computed properties (no side effects, no external state). They derive from the object's own data. This is a standard Python dataclass pattern and does not constitute a meaningful SRP violation.
- **Refactoring:** None needed.

---

## 2. OCP — Open/Closed Principle

*Software entities should be open for extension but closed for modification.*

### Finding 2.1 — `PaymentProcessor.process`

- **File:** `payment.py:5-28`
- **Class:** `PaymentProcessor`
- **Classification:** Definite violation
- **Evidence:** Payment dispatch is a 5-branch `if/elif/elif/elif/else` chain on a raw string. The cash addition (lines 23-25) required modifying this existing, working method. Each new payment method (apple_pay, wire_transfer, etc.) will require another `elif` branch here. The class is not closed for modification.
  ```
  if   credit_card → ...
  elif paypal     → ...
  elif bitcoin    → ...
  elif cash       → ...    ← added, required editing
  else            → raise
  ```
  Each branch also accesses different `Customer` fields (`credit_card`, `email`, `bitcoin_address`, nothing for cash), meaning the method accumulates knowledge about every payment method's data requirements.
- **Refactoring:** Define a `PaymentStrategy` protocol with a `process(order, amount) -> str` method. Create concrete implementations: `CreditCardPayment`, `PaypalPayment`, `BitcoinPayment`, `CashPayment`. `PaymentProcessor` holds a `dict[str, PaymentStrategy]` and does a single lookup + delegation.
- **Why appropriate:** Adding a new payment method means creating a new class — no existing code changes. The dispatch dictionary is the only mapping point. Each strategy encapsulates its own field access (e.g. `CreditCardPayment` reads `customer.credit_card`; `CashPayment` reads nothing from the customer). The cash addition that just happened would have been a new file, not an edit to payment.py.

### Finding 2.2 — `DiscountCalculator.calculate`

- **File:** `pricing.py:5-16`
- **Class:** `DiscountCalculator`
- **Classification:** Definite violation
- **Evidence:** Discount logic is a 4-branch `if/elif/elif/else` chain:
  ```
  if   is_vip           → 20%
  elif item_count >= 10 → 10%
  elif "WELCOME10"      → 10%
  else                  → 0%
  ```
  Adding a new rule (seasonal sale, loyalty tier, referral bonus) requires modifying this method. The class is not closed for modification.
- **Refactoring:** Define a `DiscountRule` protocol with `is_applicable(order) -> bool` and `calculate_discount(order) -> float`. Create `VipDiscount`, `BulkDiscount`, `CouponDiscount` classes. `DiscountCalculator` holds a list of rules and iterates.
- **Why appropriate:** New discount rules are added as new classes. The calculator engine doesn't change when business rules change.

### Finding 2.3 — `NotificationService` channels

- **File:** `notification.py:1-9`
- **Class:** `NotificationService`
- **Classification:** Possible violation
- **Evidence:** Three channels (`send_email`, `send_sms`, `send_push`) are hardcoded in one class. Adding a new channel (e.g. `send_slack`) requires modifying this class.
- **Severity:** Low-Medium. Only 3 channels currently. The ISP violation (Finding 4.1) is the more pressing concern here.
- **Refactoring:** Extract each channel to its own class implementing a `Notifier` protocol.
- **Why appropriate:** Channels are independent. Adding Slack doesn't require touching email code.

---

## 3. LSP — Liskov Substitution Principle

*Subtypes must be substitutable for their base types without altering program correctness.*

### Finding 3.1 — `SmsOnlyNotifier`

- **File:** `notification.py:12-17`
- **Class:** `SmsOnlyNotifier`
- **Classification:** Definite violation
- **Evidence:** `SmsOnlyNotifier` inherits `NotificationService` but raises `NotImplementedError` on `send_email` (line 13-14) and `send_push` (line 16-17). Any code calling these methods on a `NotificationService` reference will crash at runtime if the object is an `SmsOnlyNotifier`.
  ```python
  notifier: NotificationService = SmsOnlyNotifier()
  notifier.send_email(cust, msg)  # raises NotImplementedError
  ```
  The parent class promises all three channels work. The subclass silently breaks that promise.
- **Refactoring:** Split into per-channel interfaces: `EmailSender`, `SmsSender`, `PushSender`. `SmsOnlyNotifier` implements only `SmsSender`. `OrderService` depends only on `EmailSender` and `SmsSender`.
- **Why appropriate:** `SmsOnlyNotifier` is honest about its capabilities. It doesn't pretend to be a full notification service. This also resolves Finding 4.1 (ISP).

### Finding 3.2 — `BundleOrder`

- **File:** `models.py:47-50`
- **Class:** `BundleOrder`
- **Classification:** Definite violation
- **Evidence:** `BundleOrder` inherits `Order` but hardcodes `items=[]` (line 49). The inherited properties `subtotal` and `item_count` always return `0.0` and `0` — semantically wrong for a bundle containing two orders worth $1829.98.
  Runtime proof from the demo output:
  ```
  Subtotal    $0.00      ← should be $1829.98
  Discount   -$0.00
  Shipping    $5.00      ← charged shipping on $0 subtotal
  TOTAL       $5.00      ← should be $1829.98
  ```
  `OrderService` works around this with `isinstance(order, BundleOrder)` at line 17 — a type check that is itself proof the substitution doesn't hold. A correct `BundleOrder` shouldn't need special-casing.
- **Refactoring:** Override `subtotal` and `item_count` in `BundleOrder` to aggregate across `self.orders`:
  ```python
  @property
  def subtotal(self) -> float:
      return sum(o.subtotal for o in self.orders)
  ```
  Better yet, process each child order independently in a bundle flow rather than treating the bundle as a single order.
- **Why appropriate:** A bundle's total should be the sum of its children. Overriding makes `BundleOrder` a proper substitutable `Order` with correct semantics, eliminating the `isinstance` hack.

### Finding 3.3 — `Order` subclasses (no violation)

- **File:** `models.py:30-44`
- **Class:** `Order`
- **Classification:** No violation
- **Evidence:** `Order` is the base class for `BundleOrder` (which violates LSP per Finding 3.2). `Order` itself has no subclasses that conform to LSP — `BundleOrder` is the only subclass and it breaks the contract. The base class design is sound; the subclass is the problem.

---

## 4. ISP — Interface Segregation Principle

*Clients should not be forced to depend on methods they do not use.*

### Finding 4.1 — `NotificationService`

- **File:** `notification.py:1-9`
- **Class:** `NotificationService`
- **Classification:** Definite violation
- **Evidence:** The class exposes three unrelated methods as a single interface:
  - `send_email` (line 2)
  - `send_sms` (line 5)
  - `send_push` (line 8)

  `OrderService` (lines 38-39) calls only `send_email` and `send_sms` — it never uses `send_push`. `SmsOnlyNotifier` is forced to explicitly reject two of three methods. The fat interface directly causes the LSP violation in Finding 3.1.
- **Refactoring:** Split into three interfaces: `EmailSender`, `SmsSender`, `PushSender`. Each is a single-method protocol. `OrderService` depends on `EmailSender` and `SmsSender` only. `SmsOnlyNotifier` implements only `SmsSender`.
- **Why appropriate:** Each interface represents one genuine capability. Clients depend only on what they use. No dead methods, no `NotImplementedError` workarounds.

### Finding 4.2 — `PaymentProcessor` (no violation)

- **File:** `payment.py:4-28`
- **Class:** `PaymentProcessor`
- **Classification:** No violation
- **Evidence:** `PaymentProcessor` has a single public method `process(order, amount)`. All callers use this one method. There are no unused methods being forced on clients. The OCP violation (Finding 2.1) is the real issue — not ISP.

### Finding 4.3 — `Customer` dataclass

- **File:** `models.py:6-14`
- **Class:** `Customer`
- **Classification:** Possible violation
- **Evidence:** `Customer` bundles identity (`id`, `name`), contact info (`email`, `phone`), and payment credentials (`credit_card`, `bitcoin_address`) in one object. `PaymentProcessor` reads `credit_card`/`bitcoin_address` but sees `email`/`phone`. `NotificationService` reads `email`/`phone` but sees `credit_card`/`bitcoin_address`.
- **Severity:** Low. This is passive data with no behavior. The coupling is minimal in a small project. Only relevant if the field set grows significantly.
- **Refactoring:** Separate into `ContactInfo`, `PaymentInfo`, `CustomerIdentity` if needed.
- **Why appropriate:** Only worth doing at scale — currently the cost of splitting outweighs the benefit.

---

## 5. DIP — Dependency Inversion Principle

*High-level modules should not depend on low-level modules. Both should depend on abstractions.*

### Finding 5.1 — `OrderService.__init__`

- **File:** `order_service.py:9-13`
- **Class:** `OrderService`
- **Classification:** Definite violation
- **Evidence:** All four dependencies are concrete classes instantiated inline:
  ```python
  self.discount_calculator = DiscountCalculator()   # line 10
  self.payment_processor = PaymentProcessor()        # line 11
  self.notification = NotificationService()          # line 12
  self.database = MySqlDatabase()                    # line 13
  ```
  `OrderService` (high-level orchestration) depends directly on every low-level implementation. There are no abstractions (no ABCs, no protocols, no interfaces) to depend on. To test with a mock payment processor, you must monkeypatch or rewrite the constructor. There is no injection point.
- **Refactoring:** Define protocols for each dependency. Accept them as constructor parameters with defaults:
  ```python
  def __init__(
      self,
      payment_processor: PaymentProcessorProtocol | None = None,
      discount_calculator: DiscountCalculatorProtocol | None = None,
      notification: NotifierProtocol | None = None,
      database: StorageProtocol | None = None,
  ):
      self.payment_processor = payment_processor or PaymentProcessor()
      self.discount_calculator = discount_calculator or DiscountCalculator()
      self.notification = notification or NotificationService()
      self.database = database or MySqlDatabase()
  ```
- **Why appropriate:** `OrderService` depends on *contracts* (what each collaborator does), not *implementations* (how it does it). Testing becomes trivial — pass mocks. Switching implementations (e.g. real MySQL) requires no changes to `OrderService`. Backward-compatible defaults mean existing callers don't need updating.

### Finding 5.2 — Systemic: no abstractions anywhere

- **File:** Entire codebase (all 7 modules)
- **Classification:** Definite violation (systemic)
- **Evidence:** Zero ABCs, zero protocols, zero abstract interfaces across the entire project:
  - `payment.py` imports `Order` (concrete model) directly
  - `pricing.py` imports `Order` (concrete model) directly
  - `notification.py` has no imports, exposes a concrete class
  - `storage.py` exposes a concrete class
  - `order_service.py` imports all four concrete classes

  Every module depends on every other module's concrete implementation. The dependency graph is a complete mesh of concrete-to-concrete couplings.
- **Refactoring:** Introduce protocols in a `protocols.py` module or within each module. Start with the four dependencies of `OrderService`, then extend to model interfaces where beneficial.
- **Why appropriate:** Python protocols are lightweight (no class hierarchy, just formalized duck typing). They provide the abstraction layer without heavyweight architecture. The cost is low — one `typing.Protocol` per interface.

---

## Summary Table

| # | Principle | Classification | Location | Evidence | Severity | Refactoring |
|---|---|---|---|---|---|---|
| 1.1 | **SRP** | Definite violation | `order_service.py` `OrderService.process_order` | 6 responsibilities in one method: validate, price, pay, persist, notify, receipt | **High** | Extract `OrderValidator`, `PricingEngine`, `NotificationDispatcher`, `ReceiptPrinter` |
| 1.2 | **SRP** | Possible violation | `order_service.py` `OrderService._print_receipt` | Receipt formatting mixed with orchestration | Low | Extract `ReceiptPrinter` class |
| 1.3 | **SRP** | No violation | `models.py` `Order` | Pure computed properties on a dataclass — standard pattern | — | None |
| 2.1 | **OCP** | Definite violation | `payment.py` `PaymentProcessor.process` | 5-branch if/elif chain; cash addition required editing existing method | **Medium-High** | `PaymentStrategy` protocol + per-method classes + registry dict |
| 2.2 | **OCP** | Definite violation | `pricing.py` `DiscountCalculator.calculate` | 4-branch if/elif chain; new rules require editing existing method | **Medium** | `DiscountRule` protocol + per-rule classes + rule list |
| 2.3 | **OCP** | Possible violation | `notification.py` `NotificationService` | Hardcoded channels; new channel requires editing class | Low-Medium | Per-channel `Notifier` classes |
| 3.1 | **LSP** | Definite violation | `notification.py` `SmsOnlyNotifier` | Raises `NotImplementedError` on parent's `send_email`/`send_push` — not substitutable | **High** | Per-channel interfaces (also fixes ISP Finding 4.1) |
| 3.2 | **LSP** | Definite violation | `models.py` `BundleOrder` | `subtotal` returns 0, `items` always empty; `isinstance` workaround in OrderService proves substitution breaks | **Medium-High** | Override `subtotal`/`item_count` to aggregate child orders |
| 3.3 | **LSP** | No violation | `models.py` `Order` | Base class is sound; only `BundleOrder` subclass is problematic | — | None (fix the subclass) |
| 4.1 | **ISP** | Definite violation | `notification.py` `NotificationService` | 3-method fat interface; `OrderService` uses 2, `SmsOnlyNotifier` rejects 2 | **Medium** | Split into `EmailSender`, `SmsSender`, `PushSender` |
| 4.2 | **ISP** | No violation | `payment.py` `PaymentProcessor` | Single public method; all callers use it | — | None |
| 4.3 | **ISP** | Possible violation | `models.py` `Customer` | All payment/contact fields visible to all consumers | Low | Separate only if project scales |
| 5.1 | **DIP** | Definite violation | `order_service.py` `OrderService.__init__` | All 4 dependencies are concrete classes; no abstractions, no injection | **High** | Protocols + constructor injection with defaults |
| 5.2 | **DIP** | Definite violation (systemic) | Entire codebase | Zero ABCs, zero protocols; every module depends on concrete implementations | **High** | Introduce protocols in `protocols.py` or per-module |

---

## Cash Payment — Specific Impact Analysis

The recent cash addition (payment.py:23-25, main.py:26-29) is a useful case study:

| What we did | What it exposed |
|---|---|
| Added `elif method == "cash"` to `PaymentProcessor.process` | **OCP violation** (Finding 2.1) — we had to modify an existing, working method to extend behavior |
| Cash needs no customer data (no card, no email, no bitcoin address) | **Design inconsistency** — the if/elif chain accesses different `Customer` fields per method. Cash accesses none. This irregularity is a symptom of the missing abstraction |
| `OrderService.process_order` needed no changes | **Accidental benefit** — but only because the orchestration doesn't inspect payment method. A different feature (e.g. cash-only discounts) would force an edit there too |
| No new files, no new classes | **OCP violation confirmed** — the architecture forces edits to existing files for new features |

---

## Recommended Refactoring Priority

| Priority | Refactoring | Fixes | Effort |
|---|---|---|---|
| 1 | Payment strategy pattern | OCP (2.1) + partial DIP (5.1) | Medium |
| 2 | Per-channel notification interfaces | ISP (4.1) + LSP (3.1) + OCP (2.3) | Low-Medium |
| 3 | `BundleOrder` property override | LSP (3.2) | Low |
| 4 | Constructor injection in `OrderService` | DIP (5.1) | Low |
| 5 | Discount rule extraction | OCP (2.2) | Medium |
| 6 | Extract `OrderService` steps | SRP (1.1) | Medium |
