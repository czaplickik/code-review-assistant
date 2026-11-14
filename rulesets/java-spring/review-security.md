# Security review — Java / Spring specifics

- **Method security**: `@PreAuthorize` needs `@EnableMethodSecurity`; expressions referencing
  beans (`@orderSecurity.isOwner(#id, authentication)`) must use the right parameter name;
  `hasRole('X')` alone on `/{id}` resources is an IDOR unless ownership is checked elsewhere.
- **Filter chain order**: the first matching `requestMatchers` wins; a broad `permitAll()` or
  `authenticated()` above a specific rule silently overrides it. `HttpMethod`-less matchers
  cover every verb.
- **CSRF** may be disabled only for stateless token APIs; with cookie/session auth it must
  stay on.
- **JWT**: `parseSignedClaims`/`verifyWith` with a key from config (not a literal); expiry
  always checked; algorithm not taken from the token header; clock skew small.
- **Passwords**: `BCryptPasswordEncoder` strength ≥ 10 (12 typical), never `NoOpPasswordEncoder`,
  `DelegatingPasswordEncoder` ids unchanged.
- **Mass assignment**: request DTOs bound with `@RequestBody` must not be JPA entities or
  contain fields like `role`, `ownerId`, `price`, `status` the client must not set.
- **Validation**: `@Valid` on `@RequestBody`; `@Validated` on the class for `@PathVariable`
  / `@RequestParam` constraints; size limits on strings and collections.
- **Queries**: JPQL/native queries with `+` concatenation or `String.format`; Spring Data
  `@Query` with SpEL from user input; `Sort` built from raw request strings.
- **Jackson**: `enableDefaultTyping` / `@JsonTypeInfo(use = CLASS)` on input types.
- **Errors**: `server.error.include-stacktrace`, `include-message` not `always` in prod
  profiles; `@ExceptionHandler` must not echo internal messages.
- **Actuator / Swagger**: exposure (`management.endpoints.web.exposure.include`) and auth.
- **Outbound HTTP**: URLs or hosts built from input (SSRF); TLS verification disabled.
- **Logging**: `log.info("... {}", request)` dumping whole DTOs with personal data or tokens.
