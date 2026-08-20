# AGENTS.md

## What this is

Small Python lab project: an e-commerce order-processing demo under `store/`. No external dependencies, no tests, no CI.

## Run

```bash
python -m store.main
```

All code lives in `store/`. Imports use the `store.` package prefix (e.g. `from store.models import Order`).

## Structure

- `models.py` — dataclasses: `Customer`, `OrderItem`, `Order`, `BundleOrder`
- `pricing.py` — `DiscountCalculator` (VIP 20%, bulk 10%, coupon 10%)
- `payment.py` — `PaymentProcessor` (credit_card / paypal / bitcoin)
- `notification.py` — `NotificationService` + `SmsOnlyNotifier`
- `storage.py` — `MySqlDatabase` (in-memory stub, not real MySQL)
- `order_service.py` — `OrderService.process_order` (validate → price → pay → save → notify → receipt)
- `main.py` — demo entry point building sample orders

## Gotchas

- `storage.MySqlDatabase` is an in-memory dict, not an actual database. No real persistence.
- `PaymentProcessor` and `NotificationService` just print to stdout — no real integrations.
- `BundleOrder` inherits `Order` but its `items` list is always empty; it delegates to child orders.
- Python 3.14 bytecode in `__pycache__/` — that's the runtime version in use.
