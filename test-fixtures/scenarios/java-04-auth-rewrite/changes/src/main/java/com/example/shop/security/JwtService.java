package com.example.shop.security;

import com.example.shop.user.domain.Role;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.io.Decoders;
import io.jsonwebtoken.security.Keys;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.Optional;
import javax.crypto.SecretKey;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class JwtService {

    private static final Logger log = LoggerFactory.getLogger(JwtService.class);

    public static final String CLAIM_REMEMBER_ME = "rme";

    private static final String CLAIM_EMAIL = "email";
    private static final String CLAIM_ROLE = "role";
    private static final long CLOCK_SKEW_SECONDS = 30;

    private final JwtProperties properties;
    private final SecretKey signingKey;
    private final Clock clock;

    public JwtService(JwtProperties properties, Clock clock) {
        this.properties = properties;
        this.clock = clock;
        byte[] keyBytes = Decoders.BASE64.decode(properties.secret());
        if (keyBytes.length < 32) {
            throw new IllegalStateException("shop.security.jwt.secret must be at least 256 bits");
        }
        this.signingKey = Keys.hmacShaKeyFor(keyBytes);
    }

    public String issueAccessToken(AuthenticatedUser user) {
        return issueAccessToken(user, false);
    }

    public String issueAccessToken(AuthenticatedUser user, boolean rememberMe) {
        Instant now = clock.instant();
        Duration ttl = rememberMe ? properties.rememberMeTtl() : properties.accessTokenTtl();
        return Jwts.builder()
                .issuer(properties.issuer())
                .subject(String.valueOf(user.id()))
                .claim(CLAIM_EMAIL, user.email())
                .claim(CLAIM_ROLE, user.role().name())
                .claim(CLAIM_REMEMBER_ME, rememberMe)
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(ttl)))
                .signWith(signingKey)
                .compact();
    }

    public long accessTokenTtlSeconds() {
        return properties.accessTokenTtl().toSeconds();
    }

    public long rememberMeTtlSeconds() {
        return properties.rememberMeTtl().toSeconds();
    }

    /** Verifies signature and issuer and returns the claims; throws {@link JwtException} on failure. */
    public Claims parseClaims(String token) {
        return Jwts.parser()
                .verifyWith(signingKey)
                .requireIssuer(properties.issuer())
                .clock(() -> Date.from(clock.instant()))
                .clockSkewSeconds(CLOCK_SKEW_SECONDS)
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    /**
     * Validates signature, issuer and expiry. Returns empty for any invalid token; the caller
     * treats the request as anonymous and the security rules decide what that means.
     */
    public Optional<AuthenticatedUser> parse(String token) {
        try {
            return Optional.of(toUser(parseClaims(token)));
        } catch (ExpiredJwtException e) {
            log.debug("Rejected expired token subject={}", e.getClaims().getSubject());
            return Optional.empty();
        } catch (JwtException | IllegalArgumentException e) {
            log.debug("Rejected invalid token reason={}", e.getClass().getSimpleName());
            return Optional.empty();
        }
    }

    public AuthenticatedUser toUser(Claims claims) {
        return new AuthenticatedUser(
                Long.valueOf(claims.getSubject()),
                claims.get(CLAIM_EMAIL, String.class),
                Role.valueOf(claims.get(CLAIM_ROLE, String.class)));
    }
}
