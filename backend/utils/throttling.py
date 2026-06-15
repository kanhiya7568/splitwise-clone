"""
Custom throttle classes.

Design decisions:
- Two-tier throttling: burst (per minute) and sustained (per hour).
  This prevents both sudden abuse and gradual over-use.
- Rates set in base.py REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].
- Unauthenticated users only get the 'anon' rate (applied to auth endpoints).
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class UserBurstRateThrottle(UserRateThrottle):
    """
    Short-window throttle: 30 requests/minute per authenticated user.
    Prevents rapid-fire attacks even within the hourly limit.
    """
    scope = "user_burst"


class UserSustainedRateThrottle(UserRateThrottle):
    """
    Long-window throttle: 100 requests/hour per authenticated user.
    Matches the approved NFR-04 specification.
    """
    scope = "user_sustained"


class AnonBurstRateThrottle(AnonRateThrottle):
    """
    Throttle for unauthenticated endpoints (register, login, token refresh).
    20 requests/hour per IP address.
    """
    scope = "anon"
