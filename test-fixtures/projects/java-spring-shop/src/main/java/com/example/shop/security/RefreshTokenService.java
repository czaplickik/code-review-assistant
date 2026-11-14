package com.example.shop.security;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Clock;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Base64;
import java.util.HexFormat;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Opaque, rotating refresh tokens. Only the SHA-256 hash is stored. Re-use of an already
 * rotated token is treated as theft and revokes every token of that user.
 */
@Service
public class RefreshTokenService {

    private static final Logger log = LoggerFactory.getLogger(RefreshTokenService.class);
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final int TOKEN_BYTES = 32;

    private final JdbcClient jdbc;
    private final JwtProperties properties;
    private final Clock clock;

    public RefreshTokenService(JdbcClient jdbc, JwtProperties properties, Clock clock) {
        this.jdbc = jdbc;
        this.properties = properties;
        this.clock = clock;
    }

    public record Rotation(Long userId, String refreshToken) {
    }

    private record StoredToken(Long userId, Instant expiresAt, boolean revoked) {
    }

    @Transactional
    public String issue(Long userId) {
        String raw = newRawToken();
        jdbc.sql("INSERT INTO refresh_tokens (token_hash, user_id, expires_at) VALUES (:hash, :userId, :expiresAt)")
                .param("hash", sha256(raw))
                .param("userId", userId)
                .param("expiresAt", OffsetDateTime.ofInstant(clock.instant().plus(properties.refreshTokenTtl()), ZoneOffset.UTC))
                .update();
        return raw;
    }

    // noRollbackFor: the family revocation on token re-use must survive the exception
    @Transactional(noRollbackFor = AuthenticationFailedException.class)
    public Rotation rotate(String rawToken) {
        String hash = sha256(rawToken);
        StoredToken stored = jdbc.sql("SELECT user_id, expires_at, revoked FROM refresh_tokens WHERE token_hash = :hash FOR UPDATE")
                .param("hash", hash)
                .query((rs, rowNum) -> new StoredToken(
                        rs.getLong("user_id"),
                        rs.getObject("expires_at", OffsetDateTime.class).toInstant(),
                        rs.getBoolean("revoked")))
                .optional()
                .orElseThrow(() -> new AuthenticationFailedException("Invalid refresh token"));

        if (stored.revoked()) {
            int revoked = revokeAllForUser(stored.userId());
            log.warn("Refresh token reuse detected userId={} revokedTokens={}", stored.userId(), revoked);
            throw new AuthenticationFailedException("Invalid refresh token");
        }
        if (!stored.expiresAt().isAfter(clock.instant())) {
            throw new AuthenticationFailedException("Refresh token expired");
        }

        jdbc.sql("UPDATE refresh_tokens SET revoked = TRUE WHERE token_hash = :hash").param("hash", hash).update();
        return new Rotation(stored.userId(), issue(stored.userId()));
    }

    @Transactional
    public void revoke(String rawToken) {
        jdbc.sql("UPDATE refresh_tokens SET revoked = TRUE WHERE token_hash = :hash")
                .param("hash", sha256(rawToken))
                .update();
    }

    @Transactional
    public int revokeAllForUser(Long userId) {
        return jdbc.sql("UPDATE refresh_tokens SET revoked = TRUE WHERE user_id = :userId AND revoked = FALSE")
                .param("userId", userId)
                .update();
    }

    private static String newRawToken() {
        byte[] bytes = new byte[TOKEN_BYTES];
        RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private static String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 not available", e);
        }
    }
}
