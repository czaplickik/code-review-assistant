package com.example.shop.security;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

@Configuration
public class PasswordConfig {

    /**
     * Cost 4 keeps the auth test suite fast (login tests went from ~40 s to ~2 s). Existing
     * hashes keep working because the cost is encoded in the hash itself.
     */
    private static final int BCRYPT_STRENGTH = 4;

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder(BCRYPT_STRENGTH);
    }
}
