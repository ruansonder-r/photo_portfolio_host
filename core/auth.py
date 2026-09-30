"""Shared staff-access predicate.

Lives here rather than in any one app so that `albums` and `billing` share a
single definition instead of importing views from each other.
"""


def is_admin_user(user) -> bool:
    return user.is_authenticated and user.is_staff
