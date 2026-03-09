from functools import wraps
from flask import request, redirect, url_for
from flask_login import current_user


# Custom admin_required decorator
def admin_required(view_func):
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            # Redirect unauthenticated users to the login page
            return redirect(
                url_for("user.login")
            )  # Adjust 'login' to your actual login route
        elif not current_user.admin:
            # Redirect non-admin users to some unauthorized page
            return redirect(url_for("user.only_admins"))
        return view_func(*args, **kwargs)

    return decorated_view


# Custom admin or owner decorator
# Note: if no process_id is passed, the view returns the page
# If no process_id is passed, then the page has no owner
def admin_or_owner_required(view_func):
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("user.login"))

        process_id = request.form.get("process_id") or request.args.get(
            "process_id"
        )

        # If no process_id is provided, allow access
        if not process_id:
            return view_func(*args, **kwargs)

        from models.sequencing_upload import SequencingUpload

        # If process_id is provided, check ownership or admin rights
        process_data = SequencingUpload.get(process_id)
        if process_data and current_user.id == process_data["user_id"]:
            return view_func(*args, **kwargs)

        if current_user.admin:
            return view_func(*args, **kwargs)

        return redirect(url_for("user.only_admins"))

    return decorated_view


# Custom staff or owner decorator
# Note: if no process_id is passed, the view returns the page
# If no process_id is passed, then the page has no owner
def staff_or_owner_required(view_func):
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("user.login"))

        process_id = request.form.get("process_id") or request.args.get(
            "process_id"
        )

        # If no process_id is provided, allow access
        if not process_id:
            return view_func(*args, **kwargs)

        from models.sequencing_upload import SequencingUpload

        # If process_id is provided, check ownership or admin rights
        process_data = SequencingUpload.get(process_id)
        if process_data and current_user.id == process_data["user_id"]:
            return view_func(*args, **kwargs)

        if current_user.spun_staff:
            return view_func(*args, **kwargs)

        if current_user.admin:
            return view_func(*args, **kwargs)

        return redirect(url_for("user.only_staff"))

    return decorated_view


# Custom approved_required decorator
def approved_required(view_func):
    @wraps(view_func)
    def decorated_approved_view(*args, **kwargs):
        if not current_user.is_authenticated:
            # Redirect unauthenticated users to the login page
            return redirect(
                url_for("user.login")
            )  # Adjust 'login' to your actual login route
        elif not current_user.approved:
            # Redirect non-approved users to some unauthorized page
            return redirect(url_for("user.only_approved"))
        return view_func(*args, **kwargs)

    return decorated_approved_view


# Custom staff_required decorator
def staff_required(view_func):
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            # Redirect unauthenticated users to the login page
            return redirect(
                url_for("user.login")
            )  # Adjust 'login' to your actual login route
        elif not (current_user.spun_staff or current_user.admin):
            # Redirect users who are neither staff nor admin
            return redirect(url_for("user.only_staff"))
        return view_func(*args, **kwargs)

    return decorated_view
