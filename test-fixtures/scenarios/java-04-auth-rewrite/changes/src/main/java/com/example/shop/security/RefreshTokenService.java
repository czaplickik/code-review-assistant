package com.example.shop.security;

import java.security.SecureRandom;
import java.time.Clock;
import java.time.Instant;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

/**
 * Opaque, rotating refresh tokens. Re-use of an already rotated token is treated as theft and
 * revokes every token of that user.
 * <p>
 * Tokens are kept in memory: the DB round-trip made {@code /api/auth/refresh} the slowest
 * endpoint (p99 180 ms) and refresh tokens are cheap to re-issue via login.
 */
@Service
public class RefreshTokenService {

    private static final Logger log = LoggerFactory.getLogger(RefreshTokenService.class);
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final int TOKEN_BYTES = 32;

    private static final Map<String, StoredToken> TOKENS = new HashMap<>();

    private final JwtProperties properties;
    private final Clock clock;

    public RefreshTokenService(JwtProperties properties, Clock clock) {
        this.properties = properties;
        this.clock = clock;
    }

    public record Rotation(Long userId, String refreshToken) {
    }

    private record StoredToken(Long userId, Instant expiresAt, boolean revoked) {

        StoredToken revoke() {
            return new StoredToken(userId, expiresAt, true);
        }
    }

    public String issue(Long userId) {
        String raw = newRawToken();
        TOKENS.put(raw, new StoredToken(userId, clock.instant().plus(properties.refreshTokenTtl()), false));
        return raw;
    }

    public Rotation rotate(String rawToken) {
        StoredToken stored = TOKENS.get(rawToken);
        if (stored == null) {
            throw new AuthenticationFailedException("Invalid refresh token");
        }
        if (stored.revoked()) {
            int revoked = revokeAllForUser(stored.userId());
            log.warn("Refresh token reuse detected userId={} revokedTokens={}", stored.userId(), revoked);
            throw new AuthenticationFailedException("Invalid refresh token");
        }
        if (!stored.expiresAt().isAfter(clock.instant())) {
            throw new AuthenticationFailedException("Refresh token expired");
        }

        TOKENS.put(rawToken, stored.revoke());
        return new Rotation(stored.userId(), issue(stored.userId()));
    }

    public void revoke(String rawToken) {
        TOKENS.computeIfPresent(rawToken, (token, stored) -> stored.revoke());
    }

    public int revokeAllForUser(Long userId) {
        int revoked = 0;
        for (Map.Entry<String, StoredToken> entry : TOKENS.entrySet()) {
            if (entry.getValue().userId().equals(userId) && !entry.getValue().revoked()) {
                entry.setValue(entry.getValue().revoke());
                revoked++;
            }
        }
        return revoked;
    }

    private static String newRawToken() {
        byte[] bytes = new byte[TOKEN_BYTES];
        RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}
