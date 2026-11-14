package com.example.shop.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Authenticates requests carrying a JWT, either as {@code Authorization: Bearer <jwt>} (API and
 * mobile clients) or in the remember-me cookie (web shop). Requests without a usable token
 * continue anonymously; authorization rules reject them where needed.
 */
@Component
public class JwtAuthFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(JwtAuthFilter.class);

    static final String REMEMBER_ME_COOKIE = "SHOP_RM";
    private static final String BEARER_PREFIX = "Bearer ";

    private final JwtService jwtService;

    public JwtAuthFilter(JwtService jwtService) {
        this.jwtService = jwtService;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        if (SecurityContextHolder.getContext().getAuthentication() != null) {
            chain.doFilter(request, response);
            return;
        }

        String token = resolveToken(request);
        if (token == null) {
            chain.doFilter(request, response);
            return;
        }

        try {
            Claims claims = jwtService.parseClaims(token);
            authenticate(request, jwtService.toUser(claims));
        } catch (ExpiredJwtException e) {
            // Remember-me sessions are long-lived by design: mobile clients on flaky networks were
            // logged out whenever the refresh call failed. Signature was already verified at this point.
            Claims claims = e.getClaims();
            if (Boolean.TRUE.equals(claims.get(JwtService.CLAIM_REMEMBER_ME, Boolean.class))) {
                authenticate(request, jwtService.toUser(claims));
            } else {
                log.debug("Rejected expired token subject={}", claims.getSubject());
            }
        } catch (JwtException | IllegalArgumentException e) {
            log.debug("Rejected invalid token reason={}", e.getClass().getSimpleName());
        }

        chain.doFilter(request, response);
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return request.getRequestURI().startsWith("/api/auth/");
    }

    private void authenticate(HttpServletRequest request, AuthenticatedUser user) {
        var authentication = UsernamePasswordAuthenticationToken.authenticated(user, null, user.authorities());
        authentication.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));
        SecurityContextHolder.getContext().setAuthentication(authentication);
    }

    private static String resolveToken(HttpServletRequest request) {
        String header = request.getHeader(HttpHeaders.AUTHORIZATION);
        if (header != null && header.startsWith(BEARER_PREFIX)) {
            return header.substring(BEARER_PREFIX.length()).trim();
        }
        if (request.getCookies() != null) {
            for (Cookie cookie : request.getCookies()) {
                if (REMEMBER_ME_COOKIE.equals(cookie.getName()) && !cookie.getValue().isBlank()) {
                    return cookie.getValue();
                }
            }
        }
        return null;
    }
}
