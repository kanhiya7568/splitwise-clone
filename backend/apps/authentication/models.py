"""
Authentication app models.

No custom models are defined here.

Refresh token blacklisting is handled entirely by:
    rest_framework_simplejwt.token_blacklist

That app (already in INSTALLED_APPS) creates two tables:
    token_blacklist_outstandingtoken  — every issued refresh token
    token_blacklist_blacklistedtoken  — tokens that have been invalidated

On logout we call RefreshToken(token).blacklist() which writes to these tables.
With BLACKLIST_AFTER_ROTATION=True in SIMPLE_JWT settings, old refresh tokens
are also automatically blacklisted whenever a new token is issued via /token/refresh/.

Reference: AI_CONTEXT.md Section 14 (Authentication Design)
"""
