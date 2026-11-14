# Expected: java-04-auth-rewrite
Stack: Java 21 / Spring Boot 3
Change source: uncommitted vs HEAD (+ untracked)

- 9 files: 8 modified + 1 untracked migration. ~135 added / 78 deleted lines. No test added or changed.

## Expected review mode
`human-only` — the change rewrites the authentication path (token validation, session storage, password hashing, public URL rules) and bulk-rewrites user roles in production data. These are L4 security boundaries and an irreversible data change; AI pre-review is welcome but cannot be the gate. `ai+human-critical-paths` is the only defensible alternative.

## Expected top files (ordered, approximate)
1. `src/main/java/com/example/shop/security/JwtAuthFilter.java` — catches `ExpiredJwtException` (L57) and authenticates anyway when the `rme` claim is true (L61): a remember-me token never expires (stolen token valid forever, logout/disable ineffective); token also read from `SHOP_RM` cookie (L91) while CSRF is disabled → cookie-authenticated CSRF [CRITICAL]
2. `src/main/resources/db/migration/V3__normalize_user_roles.sql` — `UPDATE users SET role = 'ADMIN' WHERE email LIKE '%@example-shop.com'`: mass privilege escalation by e-mail domain (no verification of who owns such addresses), plus `UPPER(TRIM(role))` on every row; no backup/rollback, conventions §8 require data-owner review [CRITICAL]
3. `src/main/java/com/example/shop/security/SecurityConfig.java` — `GET /api/orders/**` `permitAll()` (L40) "for e-mail tracking links": removes filter-chain authentication for all order reads; today only the method-level `@PreAuthorize` still protects the existing endpoints, any future GET under `/api/orders` is public [CRITICAL]
4. `src/main/java/com/example/shop/security/PasswordConfig.java` — BCrypt strength 12 → 4 (L15) in main config "for test speed" (~256× cheaper offline cracking of all new hashes); conventions §10 say override in test config only [CRITICAL]
5. `src/main/java/com/example/shop/security/RefreshTokenService.java` — refresh tokens moved from hashed DB rows to `private static final Map<String, StoredToken> TOKENS = new HashMap<>()` (L27): not thread-safe (check-then-act in `rotate` L54/L67 lets two concurrent refreshes both succeed and defeats reuse detection; iteration in `revokeAllForUser` L77 races with `issue`), raw tokens kept in memory, lost on restart, not shared between instances, unbounded growth; `@Transactional(noRollbackFor …)` and `JdbcClient` removed, `refresh_tokens` table orphaned [CRITICAL]
6. `src/main/java/com/example/shop/security/JwtService.java` — `issueAccessToken(user, rememberMe)` with 90-day access-token TTL (L51) and `rme` claim; `parseClaims`/`toUser` made public for the filter
7. `src/main/java/com/example/shop/security/AuthController.java` — sets the access token in a 90-day `SHOP_RM` cookie (L45–48) without `Secure`/`SameSite`; `LoginRequest` gains `rememberMe`
8. `src/main/resources/application.yml` — `remember-me-ttl: 90d`
9. `src/main/java/com/example/shop/security/JwtProperties.java` — new `rememberMeTtl` component

## Must-detect signals
- [ ] security: expiry check bypassed for remember-me tokens — `src/main/java/com/example/shop/security/JwtAuthFilter.java`
- [ ] security: cookie-based authentication with CSRF disabled — `JwtAuthFilter.java` / `src/main/java/com/example/shop/security/AuthController.java`
- [ ] security: `permitAll` widened to `GET /api/orders/**` — `src/main/java/com/example/shop/security/SecurityConfig.java`
- [ ] security: BCrypt cost lowered to 4 in production config — `src/main/java/com/example/shop/security/PasswordConfig.java`
- [ ] data_integrity + security: data-rewriting migration that grants ADMIN by e-mail domain — `src/main/resources/db/migration/V3__normalize_user_roles.sql`
- [ ] concurrency: static non-thread-safe `HashMap` as shared token store, check-then-act rotation — `src/main/java/com/example/shop/security/RefreshTokenService.java`
- [ ] security: refresh tokens stored raw (no hash) and in process memory — `RefreshTokenService.java`
- [ ] architecture / config_infra: state moved from DB into a JVM-local static map (breaks multi-instance deployment, lost on restart) — `RefreshTokenService.java`
- [ ] config_infra: 90-day access-token lifetime — `src/main/resources/application.yml`, `src/main/java/com/example/shop/security/JwtService.java`
- [ ] tests: authentication rewrite with no new or updated tests
- [ ] conventions: violates conventions §8 (data-rewriting migration) and §10 (BCrypt 12, expiry always validated, refresh tokens hashed)

## Traps (must NOT rank high)
With 9 files every file is inside the top 10; expressed as "must not outrank the CRITICAL files":
- `src/main/java/com/example/shop/security/JwtProperties.java` — one record component added
- `src/main/resources/application.yml` — one property line

## Plan vs implementation (only for scenarios with docs)
- n/a (no docs)
