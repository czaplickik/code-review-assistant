# Expected: java-02-category-crud
Stack: Java 21 / Spring Boot 3
Change source: uncommitted vs HEAD (+ untracked)

- 15 files: 10 untracked (new `category` feature, migration, 2 test classes) + 5 modified (product entity/DTOs/service/test). ~590 added lines, 6 deleted.

## Expected review mode
`ai-review-only` — standard CRUD feature that copies the product feature's structure (constructor injection, `DomainException` subclasses, DTO mapping via mapper in the service package, `Pageable`, Bean Validation, admin endpoints under `/api/admin/**` with `@PreAuthorize("hasRole('ADMIN')")`), one additive migration and a nullable FK on products. No security config, no contract break, no event, no existing migration touched. Must NOT be `build+tests+static` (new feature with a relation and a migration) nor `ai+human-critical-paths`.

## Expected top files (ordered, approximate)
1. `src/main/java/com/example/shop/category/service/CategoryService.java` — business rules: duplicate-name check (case-insensitive), slug generated once and kept stable on rename, soft delete, `requireActive` used by product
2. `src/main/resources/db/migration/V3__create_categories.sql` — new table + `uq_categories_name_lower` + `ALTER TABLE products ADD COLUMN category_id` FK (nullable) + index; additive
3. `src/main/java/com/example/shop/product/service/ProductService.java` — new dependency on `CategoryService` (cross-feature, service-to-service as conventions require); assigns category on create/update
4. `src/main/java/com/example/shop/product/domain/Product.java` — new `@ManyToOne(fetch = LAZY)` to `Category`; `getCategoryId()` reads the FK without initialising the proxy (no N+1 when listing)
5. `src/main/java/com/example/shop/category/controller/CategoryController.java` — reads `/api/categories` (authenticated), writes `/api/admin/categories` (ADMIN); paged with default sort
6. `src/main/java/com/example/shop/product/dto/ProductDto.java` — additive field `categoryId` (non-breaking)
7. `src/main/java/com/example/shop/product/dto/UpsertProductRequest.java` — additive optional `@Positive Long categoryId`
8. `src/main/java/com/example/shop/category/repository/CategoryRepository.java` — derived queries only
9. `src/test/java/com/example/shop/category/service/CategoryServiceTest.java`, `src/test/java/com/example/shop/category/controller/CategoryControllerTest.java`, `src/test/java/com/example/shop/product/service/ProductServiceTest.java` — new and extended tests, `should_<behaviour>_when_<condition>` naming

## Must-detect signals
- [ ] core_logic (1–2): new CRUD feature with pagination, validation and a relation — `src/main/java/com/example/shop/category/service/CategoryService.java`
- [ ] data_integrity (1–2): new migration adding a table + nullable FK column (additive, not an edit of V1/V2) — `src/main/resources/db/migration/V3__create_categories.sql`
- [ ] contracts (1): additive response/request fields — `src/main/java/com/example/shop/product/dto/ProductDto.java`, `src/main/java/com/example/shop/product/dto/UpsertProductRequest.java`
- [ ] tests: new feature covered by service + web-slice tests (create, duplicate, rename keeps slug, paging, not-found, deactivate; 201/403/400/200) — `CategoryServiceTest.java`, `CategoryControllerTest.java`
- [ ] conventions: no deviation expected (constructor injection, `BusinessRuleException`/`ResourceNotFoundException`, DTOs returned to controllers, SLF4J key=value logs)
- Nice-to-have (minor, not required): duplicate-name race is only caught by `uq_categories_name_lower` → `DataIntegrityViolationException` → 500 via the generic handler; `/api/categories` requires login while `/api/products` is public (product decision, no `SecurityConfig` change); `CategoryService.requireActive` returns an entity to another service (allowed: service-to-service).
- Pre-existing, not introduced: `ProductServiceTest.should_generate_slug_from_name_when_creating_product` still expects `"Wireless-Mouse"` (fails on `develop` too; fixed in java-01). Must not be reported as a weakening introduced by this change.

## Traps (must NOT rank high)
- `src/main/java/com/example/shop/category/dto/CategoryDto.java` — plain record, no logic
- `src/main/java/com/example/shop/category/dto/UpsertCategoryRequest.java` — record with validation annotations only
- `src/main/java/com/example/shop/category/service/CategoryMapper.java` — field-by-field mapping
- `src/main/java/com/example/shop/category/domain/Category.java` — entity with trivial getters and two mutators
- `src/main/java/com/example/shop/category/repository/CategoryRepository.java` — derived query methods only (rank 8 is acceptable; must not be top 5)

## Plan vs implementation (only for scenarios with docs)
- n/a (no docs)
