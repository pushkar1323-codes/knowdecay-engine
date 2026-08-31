# Security Documentation

## Authentication Flow
The API utilizes a dual-token JWT architecture:
1. **Registration/Login**: Client provides credentials and receives an access token and a refresh token.
2. **Access Token**: Short-lived, stateless JWT used for immediate API access.
3. **Token Refresh**: Client submits the refresh token to obtain a new access token and a rotated refresh token.
4. **Logout**: Invalidates the active refresh token.

## JWT Implementation
- **Algorithm**: `HS256`
- **Access Tokens**: Fully stateless, containing user identity and role. Configurable expiry (default: 30 minutes).
- **Secret Validation**: `JWT_SECRET_KEY` must be ≥32 characters in non-testing environments, strictly enforced at startup.

## Refresh Token Security
- **Storage**: Stored in the database exclusively as `SHA-256` hashes. Plaintext tokens are never persisted.
- **Rotation**: Tokens are rotated on every use.
- **Revocation**: Tokens are explicitly revoked upon user logout or password changes.

## Password Security
- Passwords are hashed using **bcrypt**.
- The cost factor is configurable via environment variables (default: 12 rounds).

## Role-Based Access Control (RBAC)
Authorization is handled via a 5-tier hierarchical model:
1. `super_admin`
2. `institution_admin`
3. `teacher`
4. `student`
5. `api_client`

**Enforcement:**
Roles are verified using dependency injection via `get_current_user`, `require_role`, and `require_any_role`. Higher tiers implicitly inherit the permissions of lower tiers.

## Additional Protections
- **CORS**: Fully configurable via environment variables, but disabled by default to ensure secure defaults.
- **Structured Logging**: Employs a `SecretFilter` to redact value-adjacent patterns (e.g., `password=`, `bearer`, etc.) from logs.
- **Secrets Management**: All sensitive data is injected via environment variables. The `.env` file is gitignored, and `.env.example` contains only safe placeholders.

## 🔮 Future Security Roadmap
- Rate limiting implementation.
- API keys for programmatic access.
- Multi-Factor Authentication (MFA).
- OAuth2 / Single Sign-On (SSO).
- SCIM for enterprise identity provisioning.
