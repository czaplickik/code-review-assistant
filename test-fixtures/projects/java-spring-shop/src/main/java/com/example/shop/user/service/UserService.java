package com.example.shop.user.service;

import com.example.shop.security.AuthenticatedUser;
import com.example.shop.security.AuthenticationFailedException;
import com.example.shop.user.domain.User;
import com.example.shop.user.repository.UserRepository;
import java.util.Optional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional(readOnly = true)
public class UserService {

    private static final Logger log = LoggerFactory.getLogger(UserService.class);

    /**
     * Hash compared against when the e-mail is unknown, so that login timing does not reveal
     * which addresses have an account.
     */
    private static final String DUMMY_HASH = "$2a$12$Cv3OuSmKXW8x2JXJt9Qe0eVgG8wqX1n3y3JwM7Hh0l2vH6c3kYb1S";

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    public UserService(UserRepository userRepository, PasswordEncoder passwordEncoder) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
    }

    public AuthenticatedUser authenticate(String email, String rawPassword) {
        Optional<User> candidate = userRepository.findByEmailIgnoreCase(email);
        boolean matches = passwordEncoder.matches(rawPassword, candidate.map(User::getPasswordHash).orElse(DUMMY_HASH));
        User usr = candidate
                .filter(u -> matches && u.isEnabled())
                .orElseThrow(() -> new AuthenticationFailedException("Invalid e-mail or password"));
        log.info("User authenticated userId={} role={}", usr.getId(), usr.getRole());
        return toPrincipal(usr);
    }

    public AuthenticatedUser loadPrincipal(Long userId) {
        User usr = userRepository.findById(userId)
                .filter(User::isEnabled)
                .orElseThrow(() -> new AuthenticationFailedException("Account is not active"));
        return toPrincipal(usr);
    }

    private static AuthenticatedUser toPrincipal(User usr) {
        return new AuthenticatedUser(usr.getId(), usr.getEmail(), usr.getRole());
    }
}
