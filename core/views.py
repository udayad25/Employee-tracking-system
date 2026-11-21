"""Page views and JSON endpoints for the Employee Management system."""

import json
import logging
import os
from datetime import date
from functools import wraps

import oracledb
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from database import execute, query

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def get_request_data(request):
    """Read a JSON request body. Return an empty dictionary for invalid JSON."""
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def current_user(request):
    """Return the small set of user details needed by the frontend."""
    return {
        "id": request.session.get("user_id"),
        "name": request.session.get("name"),
        "role": request.session.get("role"),
        "username": request.session.get("username"),
    }


def login_required_api(view_function):
    """Require a signed-in user before an API view can run."""

    @wraps(view_function)
    def wrapper(request, *args, **kwargs):
        if not request.session.get("user_id"):
            return JsonResponse({"error": "Please sign in to continue."}, status=401)
        return view_function(request, *args, **kwargs)

    return wrapper


def admin_required(view_function):
    """Require an administrator account before an API view can run."""

    @wraps(view_function)
    def wrapper(request, *args, **kwargs):
        if not request.session.get("user_id"):
            return JsonResponse({"error": "Please sign in to continue."}, status=401)

        if request.session.get("role") != "ADMIN":
            return JsonResponse(
                {"error": "Administrator access is required for this action."},
                status=403,
            )

        return view_function(request, *args, **kwargs)

    return wrapper


def handle_oracle_errors(view_function):
    """Return a friendly response instead of exposing database errors."""

    @wraps(view_function)
    def wrapper(request, *args, **kwargs):
        try:
            return view_function(request, *args, **kwargs)
        except oracledb.Error:
            logger.exception("Oracle database operation failed")
            return JsonResponse(
                {
                    "error": (
                        "The database could not complete this request. "
                        "Check the Oracle connection and database schema."
                    )
                },
                status=503,
            )
        except RuntimeError as error:
            logger.exception("Application configuration error")
            return JsonResponse({"error": str(error)}, status=503)

    return wrapper


def write_audit_log(request, action, target_id=None, details=None):
    """Record administrator actions for traceability."""
    if request.session.get("role") != "ADMIN":
        return

    execute(
        """
        INSERT INTO audit_logs (admin_id, action, target_id, details)
        VALUES (:admin_id, :action, :target_id, :details)
        """,
        {
            "admin_id": request.session["user_id"],
            "action": action,
            "target_id": str(target_id) if target_id is not None else None,
            "details": details,
        },
    )


def valid_date(value):
    """Return True when a value is a valid YYYY-MM-DD date."""
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Regular HTML pages
# ---------------------------------------------------------------------------


def index(request):
    """Send visitors to the dashboard or sign-in page."""
    if request.session.get("user_id"):
        return redirect("dashboard")
    return redirect("login")


def login_view(request):
    """Authenticate an employee or administrator using the Oracle user table."""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        try:
            user = query(
                """
                SELECT user_id, username, password_hash, full_name, role, is_active
                FROM users
                WHERE LOWER(username) = LOWER(:username)
                """,
                {"username": username},
                one=True,
            )
        except (oracledb.Error, RuntimeError):
            logger.exception("Unable to look up the user during sign in")
            messages.error(
                request,
                "Unable to connect to the Oracle database. Check your .env settings.",
            )
            return render(request, "login.html", status=503)

        if (
            user
            and int(user["is_active"]) == 1
            and check_password(password, user["password_hash"])
        ):
            # Flush the old session before creating a new authenticated session.
            request.session.flush()
            request.session.update(
                {
                    "user_id": user["user_id"],
                    "username": user["username"],
                    "name": user["full_name"],
                    "role": user["role"],
                }
            )
            return redirect("dashboard")

        messages.error(request, "Invalid username or password, or the account is disabled.")

    return render(request, "login.html")


@require_POST
def logout_view(request):
    """End the current session."""
    request.session.flush()
    return redirect("login")


def dashboard(request):
    """Render the single-page dashboard after checking the session."""
    if not request.session.get("user_id"):
        return redirect("login")

    return render(request, "dashboard.html", {"user": current_user(request)})


def setup_admin(request):
    """Create the first administrator account during local project setup."""
    if os.getenv("ALLOW_ADMIN_SETUP", "0") != "1":
        return HttpResponse(
            "Administrator setup is disabled. Set ALLOW_ADMIN_SETUP=1 temporarily.",
            status=403,
        )

    try:
        admin_count = query(
            "SELECT COUNT(*) AS total FROM users WHERE role = 'ADMIN'",
            one=True,
        )["total"]
    except (oracledb.Error, RuntimeError):
        logger.exception("Unable to check existing administrator accounts")
        return HttpResponse(
            "Unable to connect to Oracle. Check your .env settings and schema.",
            status=503,
        )

    if admin_count:
        return HttpResponse(
            "An administrator already exists. Disable ALLOW_ADMIN_SETUP in .env.",
            status=403,
        )

    if request.method == "POST":
        full_name = request.POST.get("name", "").strip()
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if not full_name or not username or len(password) < 8:
            messages.error(
                request,
                "Enter your name, username and a password with at least 8 characters.",
            )
            return redirect("setup_admin")

        try:
            execute(
                """
                INSERT INTO users (username, password_hash, full_name, role)
                VALUES (:username, :password_hash, :full_name, 'ADMIN')
                """,
                {
                    "username": username,
                    "password_hash": make_password(password),
                    "full_name": full_name,
                },
            )
        except oracledb.IntegrityError:
            messages.error(request, "That username is already in use. Choose another one.")
            return redirect("setup_admin")
        except (oracledb.Error, RuntimeError):
            logger.exception("Unable to create the first administrator")
            messages.error(request, "Could not create the account. Check the Oracle connection.")
            return render(request, "setup_admin.html", status=503)

        messages.success(request, "Administrator account created. You can now sign in.")
        return redirect("login")

    return render(request, "setup_admin.html")


# ---------------------------------------------------------------------------
# Dashboard API: account and summary
# ---------------------------------------------------------------------------


@handle_oracle_errors
@require_http_methods(["GET"])
@login_required_api
def me(request):
    return JsonResponse(current_user(request))


@handle_oracle_errors
@require_http_methods(["GET"])
@login_required_api
def summary(request):
    """Return dashboard statistics for the signed-in user."""
    user_id = request.session["user_id"]

    if request.session["role"] == "ADMIN":
        result = query(
            """
            SELECT
                (SELECT COUNT(*) FROM users
                 WHERE role = 'EMPLOYEE' AND is_active = 1) AS employees,
                (SELECT COUNT(*) FROM attendance
                 WHERE attendance_date = TRUNC(SYSDATE)
                   AND status = 'PRESENT') AS present,
                (SELECT COUNT(*) FROM attendance
                 WHERE attendance_date = TRUNC(SYSDATE)
                   AND status = 'ABSENT') AS absent,
                (SELECT COUNT(*) FROM leave_requests
                 WHERE status = 'PENDING') AS pending_leaves,
                (SELECT COUNT(*) FROM employee_tasks
                 WHERE status <> 'COMPLETED') AS open_tasks
            FROM dual
            """,
            one=True,
        )
    else:
        result = query(
            """
            SELECT
                (SELECT COUNT(*) FROM employee_tasks
                 WHERE assignee_id = :user_id AND status <> 'COMPLETED') AS open_tasks,
                (SELECT COUNT(*) FROM leave_requests
                 WHERE user_id = :user_id AND status = 'PENDING') AS pending_leaves,
                (SELECT COUNT(*) FROM attendance
                 WHERE user_id = :user_id
                   AND attendance_date = TRUNC(SYSDATE)
                   AND check_in IS NOT NULL) AS checked_in,
                (SELECT NVL(SUM(total_working_hours), 0) FROM attendance
                 WHERE user_id = :user_id
                   AND attendance_date = TRUNC(SYSDATE)) AS hours_today,
                NVL((SELECT casual_remaining + sick_remaining
                     FROM leave_balances WHERE user_id = :user_id), 0) AS leave_balance
            FROM dual
            """,
            {"user_id": user_id},
            one=True,
        )

    return JsonResponse(result or {}, json_dumps_params={"default": str})


# ---------------------------------------------------------------------------
# Employee and department management
# ---------------------------------------------------------------------------


@handle_oracle_errors
@require_http_methods(["GET", "POST"])
@admin_required
def employees(request):
    if request.method == "GET":
        rows = query(
            """
            SELECT
                employee.user_id AS id,
                employee.username,
                employee.full_name AS name,
                employee.role,
                employee.phone,
                employee.email,
                department.name AS department
            FROM users employee
            LEFT JOIN departments department
                ON department.department_id = employee.department_id
            WHERE employee.role = 'EMPLOYEE'
              AND employee.is_active = 1
            ORDER BY employee.full_name
            """
        )
        return JsonResponse(rows, safe=False, json_dumps_params={"default": str})

    data = get_request_data(request)
    full_name = str(data.get("name", "")).strip()
    username = str(data.get("username", "")).strip()
    password = data.get("password", "")

    if not full_name or not username or len(password) < 8:
        return JsonResponse(
            {"error": "Name, username and a password of at least 8 characters are required."},
            status=400,
        )

    department = None
    department_name = str(data.get("department", "")).strip()
    if department_name:
        department = query(
            "SELECT department_id FROM departments WHERE name = :name",
            {"name": department_name},
            one=True,
        )
        if not department:
            return JsonResponse({"error": "The selected department does not exist."}, status=400)

    try:
        execute(
            """
            INSERT INTO users (
                username, password_hash, full_name, role,
                department_id, phone, email
            )
            VALUES (
                :username, :password_hash, :full_name, 'EMPLOYEE',
                :department_id, :phone, :email
            )
            """,
            {
                "username": username,
                "password_hash": make_password(password),
                "full_name": full_name,
                "department_id": department["department_id"] if department else None,
                "phone": str(data.get("phone", "")).strip() or None,
                "email": str(data.get("email", "")).strip() or None,
            },
        )
    except oracledb.IntegrityError:
        return JsonResponse({"error": "That username is already in use."}, status=409)

    # Give every new employee an initial leave balance row for the dashboard.
    new_employee = query(
        "SELECT user_id FROM users WHERE username = :username",
        {"username": username},
        one=True,
    )
    execute(
        "INSERT INTO leave_balances (user_id) VALUES (:user_id)",
        {"user_id": new_employee["user_id"]},
    )

    write_audit_log(request, "Created employee", username)
    return JsonResponse({"message": "Employee account created successfully."}, status=201)


@handle_oracle_errors
@require_http_methods(["DELETE"])
@admin_required
def delete_employee(request, uid):
    affected_rows = execute(
        """
        UPDATE users
        SET is_active = 0
        WHERE user_id = :user_id AND role = 'EMPLOYEE' AND is_active = 1
        """,
        {"user_id": uid},
    )

    if not affected_rows:
        return JsonResponse({"error": "Employee not found or already deactivated."}, status=404)

    write_audit_log(request, "Deactivated employee", uid)
    return JsonResponse({"message": "Employee account deactivated."})


@handle_oracle_errors
@require_http_methods(["GET", "POST"])
@login_required_api
def departments(request):
    if request.method == "GET":
        rows = query("SELECT department_id AS id, name FROM departments ORDER BY name")
        return JsonResponse(rows, safe=False)

    if request.session.get("role") != "ADMIN":
        return JsonResponse({"error": "Administrator access is required."}, status=403)

    name = str(get_request_data(request).get("name", "")).strip()
    if not name:
        return JsonResponse({"error": "Enter a department name."}, status=400)

    try:
        execute("INSERT INTO departments (name) VALUES (:name)", {"name": name})
    except oracledb.IntegrityError:
        return JsonResponse({"error": "That department already exists."}, status=409)

    write_audit_log(request, "Added department", name)
    return JsonResponse({"message": "Department created successfully."}, status=201)


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------


@handle_oracle_errors
@require_http_methods(["GET"])
@login_required_api
def attendance(request):
    if request.session["role"] == "ADMIN":
        rows = query(
            """
            SELECT
                attendance.attendance_id AS id,
                employee.full_name AS employee,
                attendance.attendance_date,
                attendance.check_in,
                attendance.check_out,
                attendance.status,
                attendance.total_working_hours AS hours
            FROM attendance
            JOIN users employee ON employee.user_id = attendance.user_id
            ORDER BY attendance.attendance_date DESC, attendance.check_in DESC
            FETCH FIRST 200 ROWS ONLY
            """
        )
    else:
        rows = query(
            """
            SELECT
                attendance_id AS id,
                attendance_date,
                check_in,
                check_out,
                status,
                total_working_hours AS hours
            FROM attendance
            WHERE user_id = :user_id
            ORDER BY attendance_date DESC
            FETCH FIRST 90 ROWS ONLY
            """,
            {"user_id": request.session["user_id"]},
        )

    return JsonResponse(rows, safe=False, json_dumps_params={"default": str})


@handle_oracle_errors
@require_POST
@login_required_api
def checkin(request):
    user_id = request.session["user_id"]
    existing_record = query(
        """
        SELECT attendance_id
        FROM attendance
        WHERE user_id = :user_id AND attendance_date = TRUNC(SYSDATE)
        """,
        {"user_id": user_id},
        one=True,
    )

    if existing_record:
        return JsonResponse(
            {"error": "An attendance record already exists for today."},
            status=409,
        )

    execute(
        """
        INSERT INTO attendance (user_id, attendance_date, check_in, status)
        VALUES (:user_id, TRUNC(SYSDATE), SYSTIMESTAMP, 'PRESENT')
        """,
        {"user_id": user_id},
    )
    return JsonResponse({"message": "Your check-in time has been recorded."})


@handle_oracle_errors
@require_POST
@login_required_api
def checkout(request):
    user_id = request.session["user_id"]
    record = query(
        """
        SELECT attendance_id
        FROM attendance
        WHERE user_id = :user_id
          AND attendance_date = TRUNC(SYSDATE)
          AND check_in IS NOT NULL
          AND check_out IS NULL
        """,
        {"user_id": user_id},
        one=True,
    )

    if not record:
        return JsonResponse(
            {"error": "No open check-in was found for today."},
            status=400,
        )

    execute(
        """
        UPDATE attendance
        SET check_out = SYSTIMESTAMP,
            total_working_hours = ROUND(
                (CAST(SYSTIMESTAMP AS DATE) - CAST(check_in AS DATE)) * 24,
                2
            )
        WHERE attendance_id = :attendance_id
        """,
        {"attendance_id": record["attendance_id"]},
    )
    return JsonResponse({"message": "Your check-out time has been recorded."})


# ---------------------------------------------------------------------------
# Task management
# ---------------------------------------------------------------------------


@handle_oracle_errors
@require_http_methods(["GET", "POST"])
@login_required_api
def tasks(request):
    if request.method == "GET":
        sql = """
            SELECT
                task.task_id AS id,
                task.title,
                task.description,
                task.status,
                task.progress,
                task.deadline,
                employee.full_name AS employee
            FROM employee_tasks task
            JOIN users employee ON employee.user_id = task.assignee_id
        """
        params = {}

        if request.session["role"] != "ADMIN":
            sql += " WHERE task.assignee_id = :user_id"
            params["user_id"] = request.session["user_id"]

        sql += " ORDER BY task.deadline NULLS LAST, task.task_id DESC"
        rows = query(sql, params)
        return JsonResponse(rows, safe=False, json_dumps_params={"default": str})

    if request.session.get("role") != "ADMIN":
        return JsonResponse({"error": "Administrator access is required."}, status=403)

    data = get_request_data(request)
    title = str(data.get("title", "")).strip()
    assignee_id = data.get("assignee_id")
    deadline = data.get("deadline") or None

    if not title or not assignee_id:
        return JsonResponse({"error": "Task title and assigned employee are required."}, status=400)

    if deadline and not valid_date(deadline):
        return JsonResponse({"error": "Enter a valid task deadline."}, status=400)

    try:
        assignee_id = int(assignee_id)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Choose a valid employee."}, status=400)

    employee = query(
        "SELECT user_id FROM users WHERE user_id = :user_id AND role = 'EMPLOYEE' AND is_active = 1",
        {"user_id": assignee_id},
        one=True,
    )
    if not employee:
        return JsonResponse({"error": "The selected employee account was not found."}, status=404)

    execute(
        """
        INSERT INTO employee_tasks (
            title, description, assignee_id, status,
            progress, deadline, created_by
        )
        VALUES (
            :title, :description, :assignee_id, 'PENDING',
            0, TO_DATE(:deadline, 'YYYY-MM-DD'), :created_by
        )
        """,
        {
            "title": title,
            "description": str(data.get("description", "")).strip() or None,
            "assignee_id": int(assignee_id),
            "deadline": deadline,
            "created_by": request.session["user_id"],
        },
    )

    write_audit_log(request, "Assigned task", assignee_id, title)
    return JsonResponse({"message": "Task assigned successfully."}, status=201)


@handle_oracle_errors
@require_http_methods(["PATCH"])
@login_required_api
def update_task(request, tid):
    data = get_request_data(request)
    status = data.get("status")

    if status not in {"PLANNED", "PENDING", "IN_PROGRESS", "COMPLETED"}:
        return JsonResponse({"error": "Choose a valid task status."}, status=400)

    try:
        progress = int(data.get("progress", 0))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Progress must be a whole number."}, status=400)

    if not 0 <= progress <= 100:
        return JsonResponse({"error": "Progress must be between 0 and 100."}, status=400)

    if request.session["role"] == "ADMIN":
        affected_rows = execute(
            """
            UPDATE employee_tasks
            SET status = :status, progress = :progress
            WHERE task_id = :task_id
            """,
            {"status": status, "progress": progress, "task_id": tid},
        )
    else:
        affected_rows = execute(
            """
            UPDATE employee_tasks
            SET status = :status, progress = :progress
            WHERE task_id = :task_id AND assignee_id = :user_id
            """,
            {
                "status": status,
                "progress": progress,
                "task_id": tid,
                "user_id": request.session["user_id"],
            },
        )

    if not affected_rows:
        return JsonResponse({"error": "Task not found or you cannot update it."}, status=404)

    return JsonResponse({"message": "Task updated successfully."})


@handle_oracle_errors
@require_POST
@login_required_api
def log_task(request, tid):
    data = get_request_data(request)

    try:
        minutes = int(data.get("minutes", 0))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Enter the number of minutes as a whole number."}, status=400)

    if minutes < 1:
        return JsonResponse({"error": "Duration must be at least one minute."}, status=400)

    task = query(
        "SELECT assignee_id FROM employee_tasks WHERE task_id = :task_id",
        {"task_id": tid},
        one=True,
    )
    if not task:
        return JsonResponse({"error": "Task not found."}, status=404)

    if (
        request.session["role"] != "ADMIN"
        and task["assignee_id"] != request.session["user_id"]
    ):
        return JsonResponse({"error": "You cannot add time to another employee's task."}, status=403)

    execute(
        """
        INSERT INTO task_logs (task_id, user_id, duration_minutes, note)
        VALUES (:task_id, :user_id, :minutes, :note)
        """,
        {
            "task_id": tid,
            "user_id": request.session["user_id"],
            "minutes": minutes,
            "note": str(data.get("note", "")).strip() or None,
        },
    )
    return JsonResponse({"message": "Work time saved."}, status=201)


# ---------------------------------------------------------------------------
# Leave requests
# ---------------------------------------------------------------------------


@handle_oracle_errors
@require_http_methods(["GET", "POST"])
@login_required_api
def leaves(request):
    if request.method == "GET":
        sql = """
            SELECT
                leave_request.leave_id AS id,
                employee.full_name AS employee,
                leave_request.start_date,
                leave_request.end_date,
                leave_request.leave_type,
                leave_request.reason,
                leave_request.status
            FROM leave_requests leave_request
            JOIN users employee ON employee.user_id = leave_request.user_id
        """
        params = {}

        if request.session["role"] != "ADMIN":
            sql += " WHERE leave_request.user_id = :user_id"
            params["user_id"] = request.session["user_id"]

        sql += " ORDER BY leave_request.created_at DESC"
        rows = query(sql, params)
        return JsonResponse(rows, safe=False, json_dumps_params={"default": str})

    data = get_request_data(request)
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    leave_type = data.get("leave_type")
    allowed_leave_types = {"SICK", "CASUAL", "ANNUAL", "MATERNITY", "PATERNITY"}

    if not valid_date(start_date) or not valid_date(end_date):
        return JsonResponse({"error": "Enter valid start and end dates."}, status=400)

    if date.fromisoformat(end_date) < date.fromisoformat(start_date):
        return JsonResponse({"error": "The end date cannot be before the start date."}, status=400)

    if leave_type not in allowed_leave_types:
        return JsonResponse({"error": "Choose a valid leave type."}, status=400)

    execute(
        """
        INSERT INTO leave_requests (
            user_id, start_date, end_date, leave_type, reason, status
        )
        VALUES (
            :user_id,
            TO_DATE(:start_date, 'YYYY-MM-DD'),
            TO_DATE(:end_date, 'YYYY-MM-DD'),
            :leave_type,
            :reason,
            'PENDING'
        )
        """,
        {
            "user_id": request.session["user_id"],
            "start_date": start_date,
            "end_date": end_date,
            "leave_type": leave_type,
            "reason": str(data.get("reason", "")).strip() or None,
        },
    )
    return JsonResponse({"message": "Leave request submitted."}, status=201)


@handle_oracle_errors
@require_http_methods(["PATCH"])
@admin_required
def review_leave(request, lid):
    status = get_request_data(request).get("status")
    if status not in {"APPROVED", "REJECTED"}:
        return JsonResponse({"error": "Choose approve or reject."}, status=400)

    affected_rows = execute(
        """
        UPDATE leave_requests
        SET status = :status,
            reviewed_by = :reviewed_by,
            reviewed_at = SYSTIMESTAMP
        WHERE leave_id = :leave_id AND status = 'PENDING'
        """,
        {
            "status": status,
            "reviewed_by": request.session["user_id"],
            "leave_id": lid,
        },
    )

    if not affected_rows:
        return JsonResponse({"error": "Pending leave request not found."}, status=404)

    write_audit_log(request, f"Leave request {status.lower()}", lid)
    return JsonResponse({"message": f"Leave request {status.lower()} successfully."})


# ---------------------------------------------------------------------------
# Notifications, reports, announcements and audit history
# ---------------------------------------------------------------------------


@handle_oracle_errors
@require_http_methods(["GET"])
@login_required_api
def notifications(request):
    rows = query(
        """
        SELECT
            notification_id AS id,
            title,
            message,
            created_at,
            is_read
        FROM notifications
        WHERE user_id = :user_id
        ORDER BY created_at DESC
        FETCH FIRST 50 ROWS ONLY
        """,
        {"user_id": request.session["user_id"]},
    )
    return JsonResponse(rows, safe=False, json_dumps_params={"default": str})


@handle_oracle_errors
@require_POST
@login_required_api
def mark_notification(request, nid):
    affected_rows = execute(
        """
        UPDATE notifications
        SET is_read = 1
        WHERE notification_id = :notification_id AND user_id = :user_id
        """,
        {
            "notification_id": nid,
            "user_id": request.session["user_id"],
        },
    )

    if not affected_rows:
        return JsonResponse({"error": "Notification not found."}, status=404)

    return JsonResponse({"message": "Notification marked as read."})


@handle_oracle_errors
@require_http_methods(["GET"])
@admin_required
def reports(request):
    rows = query(
        """
        SELECT
            TO_CHAR(attendance_date, 'YYYY-MM') AS month,
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'PRESENT' THEN 1 ELSE 0 END) AS present,
            ROUND(
                100 * SUM(CASE WHEN status = 'PRESENT' THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0),
                1
            ) AS attendance_rate
        FROM attendance
        WHERE attendance_date >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -5)
        GROUP BY TO_CHAR(attendance_date, 'YYYY-MM')
        ORDER BY month
        """
    )
    return JsonResponse(rows, safe=False)


@handle_oracle_errors
@require_http_methods(["GET"])
@login_required_api
def payroll(request):
    """Explain that payroll needs confirmed salary rules before implementation."""
    return JsonResponse(
        {
            "notice": (
                "The original project contains a payroll screen, but it does not "
                "define salary components, deductions, tax rules or stored payslips. "
                "Those business rules must be agreed before payroll calculations "
                "can be implemented safely."
            )
        }
    )


@handle_oracle_errors
@require_http_methods(["GET"])
@login_required_api
def announcements(request):
    rows = query(
        """
        SELECT
            announcement_id AS id,
            title,
            message,
            priority,
            created_at
        FROM announcements
        ORDER BY created_at DESC
        FETCH FIRST 30 ROWS ONLY
        """
    )
    return JsonResponse(rows, safe=False, json_dumps_params={"default": str})


@handle_oracle_errors
@require_http_methods(["GET"])
@admin_required
def audit_logs(request):
    rows = query(
        """
        SELECT
            audit.audit_id AS id,
            administrator.full_name AS admin,
            audit.action,
            audit.target_id,
            audit.details,
            audit.created_at
        FROM audit_logs audit
        LEFT JOIN users administrator ON administrator.user_id = audit.admin_id
        ORDER BY audit.created_at DESC
        FETCH FIRST 100 ROWS ONLY
        """
    )
    return JsonResponse(rows, safe=False, json_dumps_params={"default": str})
