# Expected: java-01-trivial
Stack: Java 21 / Spring Boot 3
Change source: uncommitted vs HEAD (+ untracked)

- 8 modified files, 0 untracked, 18 lines changed (+18/−18). No behaviour change in production code.

## Expected review mode
`build+tests+static` — only renames of private symbols, typo fixes in a log message / comments / README, one corrected test expectation and a one-line column fix in a dev seed script. Must NOT escalate because `Money.java` (high fan-in) or `OrderService.java` (core) appear in the diff: their diffs are a Javadoc word and a log-message word.

## Expected top files (ordered, approximate)
1. `src/test/java/com/example/shop/product/service/ProductServiceTest.java` — expected slug `"Wireless-Mouse"` → `"wireless-mouse"` (L55). This is a **correction**: `Slugs.slugify` lower-cases, so the base test was failing; it is not a weakening (assertion stays exact)
2. `scripts/seed-local-db.sh` — INSERT column list `price` → `price_amount, price_currency` (base listed 7 columns for 8 values and a non-existent column); local dev script only
3. `src/main/java/com/example/shop/product/service/ProductService.java` — private static `mapToDTO` → `toDto` (5 occurrences, no fan-in outside the class)
4. `src/main/java/com/example/shop/user/service/UserService.java` — local/parameter rename `usr` → `user` (8 occurrences)
5. `src/main/java/com/example/shop/order/service/OrderService.java` — log message typo `"Order paymnet captured"` → `"Order payment captured"` (keys unchanged)
6. `src/main/java/com/example/shop/payment/PaymentClient.java` — comment typo `Retires` → `Retries`
7. `src/main/java/com/example/shop/common/Money.java` — Javadoc typo `sumarizing` → `summarizing`
8. `README.md` — `servcie` → `service`

## Must-detect signals
- [ ] tests: assertion value changed in `ProductServiceTest` is classified as a fix (value matches `Slugs.slugify` behaviour), not as weakened — `src/test/java/com/example/shop/product/service/ProductServiceTest.java`
- [ ] conventions / mechanical: renames are private-only (no public symbol, no fan-in) — `ProductService.java`, `UserService.java`
- [ ] config_infra (low, 1): seed script fix is a dev-only script change — `scripts/seed-local-db.sh`
- [ ] no file flagged critical; `Money.java` change recognised as comment-only despite high fan-in (Order, OrderItem, OrderService, Product, ProductService, PaymentClient + 3 test classes)

## Traps (must NOT rank high)
With only 8 files every file is inside the top 10, so the trap rule is expressed as "must not be flagged critical / must not raise the mode":
- `src/main/java/com/example/shop/common/Money.java` — high fan-in, but only a Javadoc word changed
- `src/main/java/com/example/shop/order/service/OrderService.java` — core logic file, but only a log-message string changed
- `src/main/java/com/example/shop/payment/PaymentClient.java` — integration file, comment-only change

## Plan vs implementation (only for scenarios with docs)
- n/a (no docs)
