# Security review — .NET specifics

- **Authorization**: `[Authorize]` on controller vs `[AllowAnonymous]` on action (anonymous
  wins); fallback policy set or not; resource-based checks (`IAuthorizationService.AuthorizeAsync`
  / handlers) for ownership — role checks alone on `/{id}` routes are IDOR.
- **Minimal APIs**: `RequireAuthorization()` on the group vs `AllowAnonymous()` on an endpoint.
- **Middleware order**: `UseAuthentication` → `UseAuthorization` before endpoint mapping;
  exception handler first; CORS before auth for preflight.
- **JWT**: `TokenValidationParameters` — `ValidateIssuer`, `ValidateAudience`, `ValidateLifetime`,
  `ValidateIssuerSigningKey` all true, small `ClockSkew`, keys from configuration/secret store.
- **Webhooks**: signature/HMAC verified with constant-time comparison **before** any side
  effect; timestamp/replay protection; anonymous webhook responses must not leak data.
- **Over-posting**: binding request bodies directly to EF entities; DTOs exposing `Id`,
  `OwnerId`, `Role`, `Status`, prices.
- **Validation**: FluentValidation/DataAnnotations registered and actually executed; length
  limits consistent with the database column sizes.
- **Queries**: `FromSqlRaw`/`ExecuteSqlRaw` with interpolation or concatenation
  (`FromSqlInterpolated` is safe), dynamic LINQ from strings.
- **Serialization**: `TypeNameHandling` other than `None` (Newtonsoft), `BinaryFormatter`.
- **Errors**: `UseDeveloperExceptionPage` outside Development, ProblemDetails exposing
  exception messages.
- **HttpClient**: `new HttpClient()` per call, `ServerCertificateCustomValidationCallback`
  returning true, URLs from input (SSRF).
- **Secrets**: connection strings / keys in appsettings committed to git instead of user
  secrets / environment / vault.
- **Logging**: structured logging of whole request objects with personal data or tokens.
