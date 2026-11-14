package com.example.shop.security;

import com.example.shop.user.service.UserService;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    public record LoginRequest(@NotBlank @Email String email, @NotBlank String password, boolean rememberMe) {
    }

    public record RefreshRequest(@NotBlank String refreshToken) {
    }

    public record TokenResponse(String accessToken, String refreshToken, long expiresInSeconds) {
    }

    private final UserService userService;
    private final JwtService jwtService;
    private final RefreshTokenService refreshTokenService;

    public AuthController(UserService userService, JwtService jwtService, RefreshTokenService refreshTokenService) {
        this.userService = userService;
        this.jwtService = jwtService;
        this.refreshTokenService = refreshTokenService;
    }

    @PostMapping("/login")
    public TokenResponse login(@Valid @RequestBody LoginRequest request, HttpServletResponse response) {
        AuthenticatedUser user = userService.authenticate(request.email(), request.password());
        String accessToken = jwtService.issueAccessToken(user, request.rememberMe());
        if (request.rememberMe()) {
            // web shop keeps the session in a cookie so that users stay logged in across browser restarts
            Cookie cookie = new Cookie(JwtAuthFilter.REMEMBER_ME_COOKIE, accessToken);
            cookie.setHttpOnly(true);
            cookie.setPath("/");
            cookie.setMaxAge((int) jwtService.rememberMeTtlSeconds());
            response.addCookie(cookie);
        }
        return new TokenResponse(
                accessToken,
                refreshTokenService.issue(user.id()),
                request.rememberMe() ? jwtService.rememberMeTtlSeconds() : jwtService.accessTokenTtlSeconds());
    }

    @PostMapping("/refresh")
    public TokenResponse refresh(@Valid @RequestBody RefreshRequest request) {
        RefreshTokenService.Rotation rotation = refreshTokenService.rotate(request.refreshToken());
        AuthenticatedUser user = userService.loadPrincipal(rotation.userId());
        return new TokenResponse(jwtService.issueAccessToken(user), rotation.refreshToken(), jwtService.accessTokenTtlSeconds());
    }

    @PostMapping("/logout")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void logout(@Valid @RequestBody RefreshRequest request) {
        refreshTokenService.revoke(request.refreshToken());
    }
}
