# Java / Spring anchors

Stack-specific calibration on top of `_base/anchors.md`.

| Situation | Dimension | Points |
|---|---|---|
| New `@RestController` + service + repository for one entity, copies an existing feature's structure | core_logic | 1 |
| Same, with `Pageable`, specifications/filters, relation mapping | core_logic | 2 |
| `@PreAuthorize("@x.isOwner(#id, principal)")` replaced by `hasRole('USER')` | security | 5, critical |
| `permitAll()` added for a GET of user/order data | security | 5, critical |
| JWT expiry/signature check skipped under a condition | security | 5, critical |
| `BCryptPasswordEncoder` strength lowered in main config | security | 4–5, critical |
| External HTTP / payment call inside a `@Transactional` method before the DB write | data_integrity | 4 (critical if money is involved) |
| `@Transactional` removed from a method doing several saves | data_integrity | 4, critical |
| Already-applied Flyway `V*__*.sql` edited | data_integrity | 4, critical (deterministic) |
| New Flyway migration adding a table | data_integrity | 1–2 |
| Migration with `UPDATE`/`DELETE` of existing rows | data_integrity | 3–4 |
| DTO field renamed (JSON property changes) / removed | contracts | 3–4 |
| Optional field added to a response DTO | contracts | 1 |
| Kafka event payload changed without a version field/topic change | contracts | 4 |
| Shared value object (e.g. `Money`) changes `equals`/rounding/arithmetic | core_logic | 4 (blast radius via fan-in) |
| Business constant changed (max discount, refund window, limits) | core_logic | 3–4 |
| `@Autowired` field injection where neighbours use constructor injection | conventions | 1–2 |
| `throw new RuntimeException` where the project has a domain exception hierarchy | conventions | 2 |
| Controller returns a JPA entity | architecture | 2–3 |
| Static `Map` used as cache / token store in a singleton bean | concurrency | 3–4 |
| `@Disabled("flaky")` on an existing business test | tests | 4 (deterministic) |
| Long (100+ line) service method mixing calculation, persistence and integration | core_logic | +1 over the base assessment, mention drift |

Spring specifics to keep in mind:
- `@Transactional` on private methods or self-invocation does not apply — say so when you see it.
- `readOnly = true` on a method that writes, or a missing `rollbackFor` for checked exceptions,
  is a data_integrity concern.
- Method security needs `@EnableMethodSecurity`; a removed enable annotation disables every
  `@PreAuthorize` in the application.
- `spring.jpa.hibernate.ddl-auto` other than `validate`/`none` in non-local profiles is critical.
