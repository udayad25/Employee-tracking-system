/**
 * Frontend behaviour for the EMTS dashboard.
 *
 * The page layout is rendered by Django templates. This file handles API
 * requests, navigation, tables, forms and small dashboard interactions.
 */

const currentUser = window.EMTS_USER;
const isAdmin = currentUser.role === "ADMIN";

const select = (selector) => document.querySelector(selector);
const selectAll = (selector) => [...document.querySelectorAll(selector)];

/** Escape text before placing database values inside HTML strings. */
function escapeHtml(value) {
    const characters = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    };

    return String(value ?? "").replace(/[&<>"']/g, (character) => characters[character]);
}

/** Read the CSRF token rendered by Django into the modal form. */
function getCsrfToken() {
    const tokenInput = document.querySelector("[name=csrfmiddlewaretoken]");
    return tokenInput ? tokenInput.value : "";
}

/** Format Oracle date/time values for display. */
function formatDateTime(value) {
    if (!value) {
        return "—";
    }

    const normalizedValue = String(value).replace(" ", "T");
    const parsedDate = new Date(normalizedValue);

    if (Number.isNaN(parsedDate.getTime())) {
        return escapeHtml(value);
    }

    return parsedDate.toLocaleString([], {
        dateStyle: "medium",
        timeStyle: "short",
    });
}

/** Display a temporary success or error message. */
function showToast(message, isError = false) {
    const toast = select("#toast");
    toast.textContent = message;
    toast.className = `toast show${isError ? " error" : ""}`;

    window.setTimeout(() => {
        toast.className = "toast";
    }, 3500);
}

/** Send a request to a Django JSON endpoint. */
async function apiRequest(path, options = {}) {
    const headers = {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
        ...(options.headers || {}),
    };

    const response = await fetch(`/api${path}`, {
        credentials: "same-origin",
        ...options,
        headers,
    });

    let responseData = {};
    try {
        responseData = await response.json();
    } catch (error) {
        // Some server errors may return an HTML response instead of JSON.
        responseData = {};
    }

    if (!response.ok) {
        throw new Error(responseData.error || "The request could not be completed.");
    }

    return responseData;
}

function statusPill(status) {
    const safeStatus = String(status || "—");
    const className = safeStatus.toLowerCase().replace(/[^a-z0-9_-]/g, "");
    const label = escapeHtml(safeStatus.replaceAll("_", " "));

    return `<span class="pill ${className}">${label}</span>`;
}

function showEmptyRow(columnCount, message) {
    return `<tr><td class="empty-cell" colspan="${columnCount}">${escapeHtml(message)}</td></tr>`;
}

// ---------------------------------------------------------------------------
// Navigation and page setup
// ---------------------------------------------------------------------------

function loadPage(pageName) {
    const pageLoaders = {
        overview: loadOverview,
        attendance: loadAttendance,
        tasks: loadTasks,
        leaves: loadLeaves,
        employees: loadEmployees,
        departments: loadDepartments,
        reports: loadReports,
        notifications: loadNotifications,
        audit: loadAuditLog,
        payroll: loadPayroll,
    };

    const loader = pageLoaders[pageName];
    if (loader) {
        loader();
    }
}

function navigateTo(pageName) {
    selectAll(".page").forEach((page) => {
        page.classList.toggle("active", page.id === pageName);
    });

    selectAll(".nav-item").forEach((button) => {
        button.classList.toggle("active", button.dataset.page === pageName);
    });

    const firstName = currentUser.name.split(" ")[0];
    const pageTitle = pageName === "overview"
        ? `Good afternoon, ${firstName}`
        : pageName.charAt(0).toUpperCase() + pageName.slice(1);

    select("#pageTitle").textContent = pageTitle;
    select("#crumb").textContent = pageName.charAt(0).toUpperCase() + pageName.slice(1);

    if (window.innerWidth < 800) {
        select("#sidebar").classList.remove("open");
    }

    loadPage(pageName);
}

selectAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => navigateTo(button.dataset.page));
});

selectAll("[data-go]").forEach((button) => {
    button.addEventListener("click", () => navigateTo(button.dataset.go));
});

select("#mobileMenu").addEventListener("click", () => {
    select("#sidebar").classList.toggle("open");
});

if (!isAdmin) {
    selectAll(".admin-only").forEach((element) => {
        element.style.display = "none";
    });
} else {
    selectAll(".employee-only").forEach((element) => {
        element.style.display = "none";
    });
}

select("#today").textContent = new Date().toLocaleDateString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
});

// ---------------------------------------------------------------------------
// Overview dashboard
// ---------------------------------------------------------------------------

function createStatCard(label, value, description, icon, theme) {
    return `
        <article class="stat-card">
            <div class="stat-top">
                <span>${escapeHtml(label)}</span>
                <span class="stat-icon ${theme}">${icon}</span>
            </div>
            <strong>${escapeHtml(value ?? 0)}</strong>
            <small>${escapeHtml(description)}</small>
        </article>
    `;
}

async function loadOverview() {
    try {
        const summary = await apiRequest("/summary/");

        if (isAdmin) {
            select("#stats").innerHTML = [
                createStatCard("Total employees", summary.employees, "Active employee accounts", "♙", "lavender"),
                createStatCard("Present today", summary.present, "Attendance marked today", "◷", "mint"),
                createStatCard("Absent today", summary.absent, "Recorded as absent", "⌁", "peach"),
                createStatCard("Pending approvals", summary.pending_leaves, "Leave requests to review", "▧", "blue"),
            ].join("");
        } else {
            select("#stats").innerHTML = [
                createStatCard("Open tasks", summary.open_tasks, "Tasks still in progress", "▤", "lavender"),
                createStatCard("Checked in", summary.checked_in ? "Yes" : "Not yet", "Today's attendance", "◷", "mint"),
                createStatCard("Hours today", summary.hours_today, "Recorded working hours", "◴", "blue"),
                createStatCard("Leave balance", summary.leave_balance ?? "—", "Casual + sick days", "▧", "peach"),
            ].join("");
        }

        const announcements = await apiRequest("/announcements/");
        select("#announcements").innerHTML = announcements.length
            ? announcements.slice(0, 4).map((announcement) => `
                <div class="announcement">
                    <b>${escapeHtml(announcement.title)}</b>
                    <p>${escapeHtml(announcement.message)}</p>
                    <small>${escapeHtml(announcement.priority)} · ${formatDateTime(announcement.created_at)}</small>
                </div>
            `).join("")
            : '<div class="empty-state">No announcements yet.</div>';
    } catch (error) {
        showToast(error.message, true);
    }
}

// ---------------------------------------------------------------------------
// Attendance
// ---------------------------------------------------------------------------

async function loadAttendance() {
    try {
        const rows = await apiRequest("/attendance/");

        select("#attendanceHead").innerHTML = isAdmin
            ? "<th>Employee</th><th>Date</th><th>Check in</th><th>Check out</th><th>Status</th><th>Hours</th>"
            : "<th>Date</th><th>Check in</th><th>Check out</th><th>Status</th><th>Hours</th>";

        select("#attendanceRows").innerHTML = rows.length
            ? rows.map((row) => `
                <tr>
                    ${isAdmin ? `<td><b>${escapeHtml(row.employee)}</b></td>` : ""}
                    <td>${escapeHtml(row.attendance_date)}</td>
                    <td>${formatDateTime(row.check_in)}</td>
                    <td>${formatDateTime(row.check_out)}</td>
                    <td>${statusPill(row.status)}</td>
                    <td>${escapeHtml(row.hours ?? "—")}</td>
                </tr>
            `).join("")
            : showEmptyRow(isAdmin ? 6 : 5, "No attendance records found.");
    } catch (error) {
        showToast(error.message, true);
    }
}

select("#checkinBtn").addEventListener("click", async () => {
    try {
        const result = await apiRequest("/attendance/checkin/", {
            method: "POST",
            body: "{}",
        });
        showToast(result.message);
        loadAttendance();
        loadOverview();
    } catch (error) {
        showToast(error.message, true);
    }
});

select("#checkoutBtn").addEventListener("click", async () => {
    try {
        const result = await apiRequest("/attendance/checkout/", {
            method: "POST",
            body: "{}",
        });
        showToast(result.message);
        loadAttendance();
        loadOverview();
    } catch (error) {
        showToast(error.message, true);
    }
});

select("#refreshAttendance").addEventListener("click", loadAttendance);

// ---------------------------------------------------------------------------
// Tasks
// ---------------------------------------------------------------------------

async function loadTasks() {
    try {
        const tasks = await apiRequest("/tasks/");
        select("#taskCount").textContent = `${tasks.length} tasks`;

        select("#taskList").innerHTML = tasks.length
            ? tasks.map((task) => `
                <article class="task-card">
                    <div class="task-main">
                        <div>
                            <h4>${escapeHtml(task.title)}</h4>
                            <p>${escapeHtml(task.description || "No description provided.")}</p>
                            <small>
                                ${isAdmin ? `Assigned to ${escapeHtml(task.employee)} · ` : ""}
                                Deadline: ${escapeHtml(task.deadline || "Not set")}
                            </small>
                        </div>
                        ${statusPill(task.status)}
                    </div>
                    <div class="progress-row">
                        <span>Progress</span>
                        <b>${escapeHtml(task.progress ?? 0)}%</b>
                    </div>
                    <div class="progress">
                        <i style="width: ${Math.max(0, Math.min(100, Number(task.progress) || 0))}%"></i>
                    </div>
                    <div class="task-controls">
                        <select data-status="${task.id}" aria-label="Task status">
                            <option value="PLANNED" ${task.status === "PLANNED" ? "selected" : ""}>Planned</option>
                            <option value="PENDING" ${task.status === "PENDING" ? "selected" : ""}>Pending</option>
                            <option value="IN_PROGRESS" ${task.status === "IN_PROGRESS" ? "selected" : ""}>In progress</option>
                            <option value="COMPLETED" ${task.status === "COMPLETED" ? "selected" : ""}>Completed</option>
                        </select>
                        <input type="number" min="0" max="100" value="${Number(task.progress) || 0}" data-progress="${task.id}" aria-label="Progress percentage">
                        <button class="secondary small-btn" type="button" data-update-task="${task.id}">Update</button>
                        <button class="secondary small-btn" type="button" data-log-task="${task.id}">Log time</button>
                    </div>
                </article>
            `).join("")
            : '<div class="empty-state">No tasks assigned yet.</div>';
    } catch (error) {
        showToast(error.message, true);
    }
}

// ---------------------------------------------------------------------------
// Leave requests
// ---------------------------------------------------------------------------

async function loadLeaves() {
    try {
        const leaveRequests = await apiRequest("/leaves/");

        select("#leaveHead").innerHTML = isAdmin
            ? "<th>Employee</th><th>Dates</th><th>Type</th><th>Reason</th><th>Status</th><th>Action</th>"
            : "<th>Dates</th><th>Type</th><th>Reason</th><th>Status</th>";

        select("#leaveRows").innerHTML = leaveRequests.length
            ? leaveRequests.map((leave) => `
                <tr>
                    ${isAdmin ? `<td>${escapeHtml(leave.employee)}</td>` : ""}
                    <td>${escapeHtml(leave.start_date)} – ${escapeHtml(leave.end_date)}</td>
                    <td>${escapeHtml(leave.leave_type)}</td>
                    <td>${escapeHtml(leave.reason)}</td>
                    <td>${statusPill(leave.status)}</td>
                    ${isAdmin ? `
                        <td>
                            ${leave.status === "PENDING" ? `
                                <button class="text-action" type="button" data-leave="${leave.id}" data-decision="APPROVED">Approve</button>
                                <button class="text-action danger" type="button" data-leave="${leave.id}" data-decision="REJECTED">Reject</button>
                            ` : "—"}
                        </td>
                    ` : ""}
                </tr>
            `).join("")
            : showEmptyRow(isAdmin ? 6 : 4, "No leave requests found.");
    } catch (error) {
        showToast(error.message, true);
    }
}

// ---------------------------------------------------------------------------
// Employees and departments
// ---------------------------------------------------------------------------

async function loadEmployees() {
    try {
        const employees = await apiRequest("/employees/");

        select("#employeeRows").innerHTML = employees.length
            ? employees.map((employee) => `
                <tr data-employee-row>
                    <td><b>${escapeHtml(employee.name)}</b></td>
                    <td>${escapeHtml(employee.username)}</td>
                    <td>${escapeHtml(employee.department || "—")}</td>
                    <td>${escapeHtml(employee.phone || "—")}</td>
                    <td>
                        <button class="text-action danger" type="button" data-delete-employee="${employee.id}">
                            Deactivate
                        </button>
                    </td>
                </tr>
            `).join("")
            : showEmptyRow(5, "No employees found.");
    } catch (error) {
        showToast(error.message, true);
    }
}

async function loadDepartments() {
    try {
        const departments = await apiRequest("/departments/");

        select("#departmentList").innerHTML = departments.length
            ? departments.map((department) => `
                <div class="department-card">
                    <span class="quick-icon lavender">⌂</span>
                    <b>${escapeHtml(department.name)}</b>
                    <small>Department</small>
                </div>
            `).join("")
            : '<div class="empty-state">No departments created yet.</div>';
    } catch (error) {
        showToast(error.message, true);
    }
}

// ---------------------------------------------------------------------------
// Reports, notifications, audit log and payroll information
// ---------------------------------------------------------------------------

async function loadReports() {
    try {
        const reports = await apiRequest("/reports/");

        select("#reportChart").innerHTML = reports.length
            ? reports.map((report) => `
                <div class="bar-row">
                    <span>${escapeHtml(report.month)}</span>
                    <div class="bar-track">
                        <i style="width: ${Math.max(0, Math.min(100, Number(report.attendance_rate) || 0))}%"></i>
                    </div>
                    <b>${escapeHtml(report.attendance_rate ?? 0)}%</b>
                </div>
            `).join("")
            : '<div class="empty-state">No attendance data available yet.</div>';
    } catch (error) {
        showToast(error.message, true);
    }
}

async function loadNotifications() {
    try {
        const notifications = await apiRequest("/notifications/");

        select("#notificationList").innerHTML = notifications.length
            ? notifications.map((notification) => `
                <div class="notification ${Number(notification.is_read) ? "read" : ""}">
                    <div>
                        <b>${escapeHtml(notification.title)}</b>
                        <p>${escapeHtml(notification.message)}</p>
                        <small>${formatDateTime(notification.created_at)}</small>
                    </div>
                    ${Number(notification.is_read) ? "" : `
                        <button class="text-action" type="button" data-read="${notification.id}">
                            Mark as read
                        </button>
                    `}
                </div>
            `).join("")
            : '<div class="empty-state">No notifications yet.</div>';
    } catch (error) {
        showToast(error.message, true);
    }
}

async function loadAuditLog() {
    try {
        const entries = await apiRequest("/audit/");

        select("#auditRows").innerHTML = entries.length
            ? entries.map((entry) => `
                <tr>
                    <td>${escapeHtml(entry.admin)}</td>
                    <td>${escapeHtml(entry.action)}</td>
                    <td>${escapeHtml(entry.target_id)}</td>
                    <td>${escapeHtml(entry.details)}</td>
                    <td>${formatDateTime(entry.created_at)}</td>
                </tr>
            `).join("")
            : showEmptyRow(5, "No audit events yet.");
    } catch (error) {
        showToast(error.message, true);
    }
}

async function loadPayroll() {
    try {
        const result = await apiRequest("/payroll/");
        select("#payrollInfo").innerHTML = `
            <div class="notice-box">
                <b>Payroll module needs business rules</b>
                <p>${escapeHtml(result.notice)}</p>
            </div>
        `;
    } catch (error) {
        showToast(error.message, true);
    }
}

// ---------------------------------------------------------------------------
// Modal forms
// ---------------------------------------------------------------------------

const modal = select("#modal");
const modalBody = select("#modalBody");

select("#modalCloseButton").addEventListener("click", () => modal.close());
select("#modalCancelButton").addEventListener("click", () => modal.close());

function openModal(title, fieldsHtml, saveRecord) {
    select("#modalTitle").textContent = title;
    modalBody.innerHTML = fieldsHtml;
    modal.showModal();

    select("#modalForm").onsubmit = async (event) => {
        event.preventDefault();

        const formData = new FormData(event.currentTarget);
        const values = Object.fromEntries(formData.entries());
        delete values.csrfmiddlewaretoken;

        try {
            const result = await saveRecord(values);
            modal.close();
            showToast(result.message || "Saved successfully.");
            loadPage(select(".page.active").id);
            loadOverview();
        } catch (error) {
            showToast(error.message, true);
        }
    };
}

select("#newEmployeeBtn").addEventListener("click", async () => {
    try {
        const departments = await apiRequest("/departments/");
        const departmentOptions = departments.map((department) => `
            <option value="${escapeHtml(department.name)}">${escapeHtml(department.name)}</option>
        `).join("");

        openModal(
            "Add employee",
            `
                <label>Full name<input name="name" maxlength="150" required></label>
                <label>Username<input name="username" maxlength="80" required></label>
                <label>Temporary password<input name="password" type="password" minlength="8" required></label>
                <label>Department
                    <select name="department">
                        <option value="">Not assigned</option>
                        ${departmentOptions}
                    </select>
                </label>
                <label>Phone<input name="phone" maxlength="30"></label>
                <label>Email<input name="email" type="email" maxlength="150"></label>
            `,
            (values) => apiRequest("/employees/", {
                method: "POST",
                body: JSON.stringify(values),
            }),
        );
    } catch (error) {
        showToast(error.message, true);
    }
});

select("#newDepartmentBtn").addEventListener("click", () => {
    openModal(
        "Add department",
        '<label>Department name<input name="name" maxlength="100" required></label>',
        (values) => apiRequest("/departments/", {
            method: "POST",
            body: JSON.stringify(values),
        }),
    );
});

select("#newTaskBtn").addEventListener("click", async () => {
    try {
        const employees = await apiRequest("/employees/");
        const employeeOptions = employees.map((employee) => `
            <option value="${employee.id}">${escapeHtml(employee.name)}</option>
        `).join("");

        openModal(
            "Assign a task",
            `
                <label>Task title<input name="title" maxlength="180" required></label>
                <label>Description<textarea name="description"></textarea></label>
                <label>Assign to<select name="assignee_id" required>${employeeOptions}</select></label>
                <label>Deadline<input name="deadline" type="date"></label>
            `,
            (values) => apiRequest("/tasks/", {
                method: "POST",
                body: JSON.stringify(values),
            }),
        );
    } catch (error) {
        showToast(error.message, true);
    }
});

select("#applyLeaveBtn").addEventListener("click", () => {
    openModal(
        "Apply for leave",
        `
            <label>Leave type
                <select name="leave_type">
                    <option value="CASUAL">Casual</option>
                    <option value="SICK">Sick</option>
                    <option value="ANNUAL">Annual</option>
                    <option value="MATERNITY">Maternity</option>
                    <option value="PATERNITY">Paternity</option>
                </select>
            </label>
            <label>Start date<input type="date" name="start_date" required></label>
            <label>End date<input type="date" name="end_date" required></label>
            <label>Reason<textarea name="reason" maxlength="1000" required></textarea></label>
        `,
        (values) => apiRequest("/leaves/", {
            method: "POST",
            body: JSON.stringify(values),
        }),
    );
});

// ---------------------------------------------------------------------------
// Actions inside tables and task cards
// ---------------------------------------------------------------------------

document.addEventListener("click", async (event) => {
    const button = event.target.closest("button");
    if (!button) {
        return;
    }

    try {
        if (button.dataset.leave) {
            const leaveId = button.dataset.leave;
            await apiRequest(`/leaves/${leaveId}/`, {
                method: "PATCH",
                body: JSON.stringify({ status: button.dataset.decision }),
            });
            showToast("Leave request updated.");
            loadLeaves();
            loadOverview();
        }

        if (button.dataset.deleteEmployee) {
            const employeeId = button.dataset.deleteEmployee;
            if (window.confirm("Deactivate this employee account?")) {
                await apiRequest(`/employees/${employeeId}/`, { method: "DELETE" });
                showToast("Employee account deactivated.");
                loadEmployees();
            }
        }

        if (button.dataset.updateTask) {
            const taskId = button.dataset.updateTask;
            const status = select(`[data-status="${taskId}"]`).value;
            const progress = select(`[data-progress="${taskId}"]`).value;

            await apiRequest(`/tasks/${taskId}/`, {
                method: "PATCH",
                body: JSON.stringify({ status, progress }),
            });
            showToast("Task updated.");
            loadTasks();
        }

        if (button.dataset.logTask) {
            const taskId = button.dataset.logTask;
            openModal(
                "Log time spent",
                `
                    <label>Duration in minutes<input name="minutes" type="number" min="1" required></label>
                    <label>Note<textarea name="note" maxlength="1000"></textarea></label>
                `,
                (values) => apiRequest(`/tasks/${taskId}/log/`, {
                    method: "POST",
                    body: JSON.stringify(values),
                }),
            );
        }

        if (button.dataset.read) {
            await apiRequest(`/notifications/${button.dataset.read}/read/`, {
                method: "POST",
                body: "{}",
            });
            showToast("Notification marked as read.");
            loadNotifications();
        }
    } catch (error) {
        showToast(error.message, true);
    }
});

const employeeSearch = select("#employeeSearch");
if (employeeSearch) {
    employeeSearch.addEventListener("input", (event) => {
        const searchText = event.target.value.toLowerCase();

        selectAll("[data-employee-row]").forEach((row) => {
            row.style.display = row.textContent.toLowerCase().includes(searchText) ? "" : "none";
        });
    });
}

// Load the overview when the dashboard first opens.
loadPage("overview");
