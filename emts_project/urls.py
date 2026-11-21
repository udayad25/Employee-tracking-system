"""URL routes for the EMTS application."""

from django.urls import path

from core import views

urlpatterns = [
    path("", views.index, name="index"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("setup-admin/", views.setup_admin, name="setup_admin"),
    # API routes used by the dashboard's JavaScript.
    path("api/me/", views.me, name="api_me"),
    path("api/summary/", views.summary, name="api_summary"),
    path("api/employees/", views.employees, name="api_employees"),
    path("api/employees/<int:uid>/", views.delete_employee, name="api_delete_employee"),
    path("api/departments/", views.departments, name="api_departments"),
    path("api/attendance/", views.attendance, name="api_attendance"),
    path("api/attendance/checkin/", views.checkin, name="api_checkin"),
    path("api/attendance/checkout/", views.checkout, name="api_checkout"),
    path("api/tasks/", views.tasks, name="api_tasks"),
    path("api/tasks/<int:tid>/", views.update_task, name="api_update_task"),
    path("api/tasks/<int:tid>/log/", views.log_task, name="api_log_task"),
    path("api/leaves/", views.leaves, name="api_leaves"),
    path("api/leaves/<int:lid>/", views.review_leave, name="api_review_leave"),
    path("api/notifications/", views.notifications, name="api_notifications"),
    path(
        "api/notifications/<int:nid>/read/",
        views.mark_notification,
        name="api_mark_notification",
    ),
    path("api/reports/", views.reports, name="api_reports"),
    path("api/payroll/", views.payroll, name="api_payroll"),
    path("api/announcements/", views.announcements, name="api_announcements"),
    path("api/audit/", views.audit_logs, name="api_audit_logs"),
]
