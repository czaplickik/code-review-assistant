package com.example.shop.security;

import com.example.shop.user.domain.Role;
import java.util.Collection;
import java.util.List;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

/** Principal stored in the {@code SecurityContext} for authenticated API calls. */
public record AuthenticatedUser(Long id, String email, Role role) {

    public Collection<? extends GrantedAuthority> authorities() {
        return List.of(new SimpleGrantedAuthority("ROLE_" + role.name()));
    }

    public boolean hasRole(Role candidate) {
        return role == candidate;
    }
}
