"""Route guards."""

from __future__ import annotations

from functools import wraps

from flask import abort, jsonify, request
from flask_login import current_user, login_required


def roles_required(*roles: str):
    """
    Allow only the listed roles.  Returns JSON 403 for API paths, HTML otherwise.
    """

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(*args, **kwargs):
            role = getattr(current_user, "role", None)
            if role not in roles:
                if request.path.startswith("/api/"):
                    return (
                        jsonify(
                            {
                                "error": "forbidden",
                                "message": f"Role '{role}' may not access this resource.",
                                "required_roles": list(roles),
                            }
                        ),
                        403,
                    )
                abort(403)
            return view(*args, **kwargs)

        return wrapper

    return decorator


def admin_required(view):
    return roles_required("admin")(view)


def auditor_required(view):
    """Auditors and admins — i.e. anyone with assurance duties."""
    return roles_required("auditor", "admin")(view)


def write_required(view):
    """Admins and analysts may mutate governed objects."""
    return roles_required("admin", "analyst")(view)


def permission_required(permission: str):
    from app.security.rbac import has_permission

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(*args, **kwargs):
            if not has_permission(permission):
                if request.path.startswith("/api/"):
                    return jsonify({"error": "forbidden", "permission": permission}), 403
                abort(403)
            return view(*args, **kwargs)

        return wrapper

    return decorator
