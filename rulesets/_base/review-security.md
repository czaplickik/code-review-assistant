# Security review checklist (all stacks)

Goal: find exploitable weaknesses introduced or exposed by the change. Report what an attacker
could do, not style. Use the stack-specific checklist listed next to this one.

## How to work

1. Inventory the **entry points** touched by the change (HTTP endpoints, message consumers,
   scheduled jobs, webhooks, file/CLI inputs) — the candidates list them. For each, trace the
   input to where it is used (DB, external call, file system, response, log).
2. Read the security configuration once (filter chain / auth setup / policies) to know the
   defaults that apply to the new code.
3. Read the security requirements in the spec (roles, ownership, data classification) if a
   spec is listed in the batch header — a violation of them is a security finding.
4. Confirm or dismiss every candidate.

## What to check

| Category | Look for |
|---|---|
| `authz` | Missing or wrong role/policy; **ownership checks (IDOR)** on resources addressed by id; privilege escalation; checks only in UI; authorization done after the side effect; anonymous endpoints |
| `authn` | Token validation (signature, expiry, issuer/audience), session/refresh handling, remember-me, password hashing parameters, auth bypass via config |
| `input_validation` | Missing validation at trust boundaries (size, range, format, enum), mass assignment / over-posting into entities, trusting client-supplied ids, prices, roles |
| `injection` | SQL/JPQL/LINQ raw strings, command execution, path traversal, LDAP, template/expression injection, header injection, XML external entities |
| `secrets` | Hard-coded credentials, keys, tokens; secrets in config committed to the repo; secrets in exceptions or responses |
| `crypto` | Weak algorithms, static IVs/salts, homemade crypto, disabled certificate validation, insecure randomness for tokens |
| `data_exposure` | Entities or internal fields returned by APIs, PII in responses, verbose error messages, stack traces, missing filtering of other tenants' data |
| `ssrf` | Server-side requests to URLs influenced by input; redirects; webhooks calling back |
| `deserialization` | Polymorphic deserialization of untrusted input, unsafe binary formats |
| `config` | CORS wildcards with credentials, CSRF disabled for cookie auth, permissive security headers, debug endpoints, actuator/swagger exposure |
| `dependencies` | New or upgraded packages: necessity, maintenance, known vulnerable versions (state that versions could not be checked online) |
| `logging` | Passwords, tokens, card data, PII in logs; missing audit trail where the spec requires one |

## Severity

- `blocker` — exploitable now: auth bypass, IDOR on sensitive data or money, injection,
  exposed secret, authentication weakened.
- `major` — weakness that needs one more mistake or condition to exploit, missing defence
  in depth on a sensitive path, sensitive data in logs.
- `minor` — hardening opportunity with low impact.
- `info` — question or assumption to confirm.

Describe the attack in one sentence ("any authenticated customer can POST a refund for another
customer's order by changing orderId"). `verified` only when the code path is shown end to end.
