# Expected: java-05-large-refactor
Stack: Java 21 / Spring Boot 3
Change source: uncommitted vs HEAD (+ untracked)

- `prepare.py` inflates the base with 48 catalogue entities × {Dto, Mapper, Service, Controller} = 192 Java files under `com.example.shop.catalog.<area>` plus `V3__catalog_read_models.sql`, all committed on `develop`.
- `generate.py` then applies, uncommitted: (1) SLF4J logger fields → Lombok `@Slf4j` in every class with a logger (192 catalog classes minus DTOs/mappers, plus 8 base classes), (2) package rename `common.util` → `common.support` (`Slugs`, `Texts` moved; imports updated in every DTO/mapper/service that used them), (3) Lombok in `pom.xml`, new `lombok.config`, `conventions.md` updated to allow `@Slf4j`.
- Result: 204 tracked files modified/deleted (`git diff HEAD --name-only`) + 3 untracked (`common/support/Slugs.java`, `common/support/Texts.java`, `lombok.config`).
- Exactly 3 real behaviour changes are hidden in the noise (applied by `generate.py` on top of the mechanical edit of the same files).

## Expected review mode
`ai+human-critical-paths` — >95% of the diff is mechanical and should be classified as such, but three files contain real changes to authorization, transactional integrity and a business constant; those need a human. Must NOT be `build+tests+static` (the hidden changes compile and pass the existing tests) and should not be `human-only` for 200 mechanical files.

## Expected top files (ordered, approximate)
The 3 hidden files MUST be in the top 5.
1. `src/main/java/com/example/shop/catalog/wishlist/WishlistEntryService.java` — `delete(id, currentUserId)` no longer loads `user_id` and no longer throws `ForbiddenOperationException`; it now runs `DELETE … WHERE id = :id` for any id (IDOR: any customer deletes any customer's wishlist entries); `currentUserId` only survives in the log line; the unused import was removed so the diff looks like cleanup [CRITICAL]
2. `src/main/java/com/example/shop/catalog/bundle/BundleService.java` — `@Transactional` removed from `replaceItems` (DELETE all items + N INSERTs + UPDATE item_count), import removed alongside the Lombok import churn; a failure mid-way leaves an emptied/partial bundle with a wrong count [CRITICAL]
3. `src/main/java/com/example/shop/catalog/promotion/PromotionCampaignService.java` — `MAX_DISCOUNT_PERCENT` 30 → 50 while its Javadoc still says "never more than the checkout discount cap (BR-7)"; `OrderService.MAX_DISCOUNT_PERCENT` and the V2 `CHECK (discount_percent BETWEEN 0 AND 30)` stay at 30 [CRITICAL]
4. `pom.xml` — new Lombok dependency + `maven-compiler-plugin` annotation processor path
5. `docs/architecture/conventions.md` — convention changed: Lombok now allowed for `@Slf4j`, logger rule rewritten

## Must-detect signals
- [ ] security: ownership check removed from a delete in a user-scoped service — `src/main/java/com/example/shop/catalog/wishlist/WishlistEntryService.java`
- [ ] data_integrity: `@Transactional` removed from a multi-write method — `src/main/java/com/example/shop/catalog/bundle/BundleService.java`
- [ ] core_logic: business constant (max campaign discount) 30% → 50%, contradicts BR-7 — `src/main/java/com/example/shop/catalog/promotion/PromotionCampaignService.java`
- [ ] config_infra: build change (Lombok + annotation processing) — `pom.xml`
- [ ] conventions: documented convention changed to permit Lombok — `docs/architecture/conventions.md`
- [ ] the remaining ~200 files classified as mechanical (logger → `@Slf4j`, import rename); `Slugs`/`Texts` recognised as moves (package line only) despite high fan-in
- [ ] scale: all 207 changed paths processed without truncation

## Traps (must NOT rank high)
- `src/main/java/com/example/shop/order/service/OrderService.java` — core file, logger change only
- `src/main/java/com/example/shop/payment/PaymentClient.java` — integration file, logger change only
- `src/main/java/com/example/shop/security/JwtService.java`, `src/main/java/com/example/shop/security/RefreshTokenService.java` — security files, logger change only
- `src/main/java/com/example/shop/common/support/Slugs.java`, `src/main/java/com/example/shop/common/support/Texts.java` (and the deleted `common/util/*`) — high fan-in, package move only
- Decoys with similar shape that did NOT change behaviour: `catalog/wishlist/WishlistService.java`, `catalog/wishlist/WishlistShareService.java`, `catalog/wishlist/WishlistReminderService.java` (ownership checks intact), `catalog/review/ProductReviewService.java` (`approve` multi-write still `@Transactional`), `catalog/inventory/StockLevelService.java` (`adjust` still `@Transactional`)
- Any other `catalog/**` Dto/Mapper/Controller file — mechanical import/logger edits

## Plan vs implementation (only for scenarios with docs)
- n/a (no plan; `conventions.md` change is a doc edit, not a plan)
