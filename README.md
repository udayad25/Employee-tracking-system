# Employee Management and Tracking System (EMTS)

EMTS is a browser-based employee management application built with **Python, Django, Oracle Database, HTML, CSS and JavaScript**. It provides separate administrator and employee workspaces for everyday employee and task management.

The code is organized so that the backend, database queries, HTML templates, CSS and JavaScript can be opened and understood as separate files.

## Technology stack

| Part | Technology |
| --- | --- |
| Backend | Python 3.10+ and Django 5.2 |
| Database | Oracle Database 12c or later |
| Oracle driver | python-oracledb (Thin mode) |
| Frontend | HTML5, CSS3 and JavaScript |
| Database tool | Oracle SQL Developer |
| Editor | VS Code or PyCharm |

## Features

### Administrator

- Sign in with an administrator account.
- View a summary of employee and attendance activity.
- Create and deactivate employee accounts.
- Create departments.
- View team attendance history.
- Assign tasks and review task progress.
- Review and approve or reject leave requests.
- View attendance reports and administrative audit history.

### Employee

- Sign in with an employee account.
- View a personal dashboard.
- Check in and check out for the day.
- View personal attendance history.
- View assigned tasks, update task status and progress, and log time.
- Submit leave requests and view their status.
- View announcements and notifications.

> **Current scope:** Payroll is a placeholder because the source project does not define salary components, deductions, tax rules or payroll records. The Oracle schema also includes a few tables reserved for future modules; not every table currently has a screen or API endpoint.

## Project structure

```text
EMTS_Django_Oracle_Web/
|
|-- core/
|   |-- __init__.py
|   |-- apps.py
|   `-- views.py              # Page views, API endpoints and validation
|
|-- database/
|   `-- schema.sql            # Oracle tables and indexes
|
|-- emts_project/
|   |-- __init__.py
|   |-- settings.py            # Django configuration
|   |-- urls.py                # URL routes
|   `-- wsgi.py
|
|-- static/
|   |-- css/
|   |   `-- style.css          # Page layout and responsive styles
|   `-- js/
|       `-- app.js             # Dashboard interactions and API calls
|
|-- templates/
|   |-- login.html
|   |-- setup_admin.html
|   `-- dashboard.html
|
|-- .env.example
|-- .gitignore
|-- database.py                # Oracle connection pool and SQL helpers
|-- manage.py
|-- requirements.txt
`-- README.md
```

## Requirements

Install the following before running the application:

1. Python 3.10 or later.
2. Oracle Database (for example, Oracle Database Free or XE) with a service name.
3. Oracle SQL Developer or SQLcl to run the schema script.
4. VS Code or another Python editor.

The `python-oracledb` driver uses Thin mode by default. For a standard Oracle Database connection, Oracle Instant Client is not normally required.

## Setup on Windows

### 1. Download the project

Clone the repository or download it as a ZIP file. Open the extracted project folder in VS Code.

### 2. Create a virtual environment

Open the VS Code terminal in the project directory and run:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt instead:

```bat
.venv\Scripts\activate.bat
```

### 3. Install Python packages

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Oracle connection details

Copy `.env.example` to a new file named `.env` in the project root. Update these values with your own Oracle details:

```env
ORACLE_USER=your_oracle_username
ORACLE_PASSWORD=your_oracle_password
ORACLE_DSN=localhost:1521/FREEPDB1
```

Examples of common Oracle service names are `localhost:1521/FREEPDB1` and `localhost:1521/XEPDB1`. Use the service name configured in your own Oracle installation.

Keep `.env` private. It is ignored by Git and must never be committed to GitHub.

### 5. Create the database tables

1. Open Oracle SQL Developer.
2. Connect using the Oracle user that will own the EMTS tables.
3. Open `database/schema.sql`.
4. Run the complete script once.
5. Confirm that the tables were created successfully.

The schema uses Oracle identity columns and SQL features available in Oracle Database 12c and later.

### 6. Create the first administrator

Make sure `.env` contains:

```env
ALLOW_ADMIN_SETUP=1
```

Start the Django server:

```bash
python manage.py runserver
```

Open this address in your browser:

```text
http://127.0.0.1:8000/setup-admin/
```

Create the first administrator account. After the account is created, change the setting in `.env` to:

```env
ALLOW_ADMIN_SETUP=0
```

Restart the server. Do not leave the first-admin setup page enabled after setup.

### 7. Sign in

Open:

```text
http://127.0.0.1:8000/
```

Sign in using the administrator account you created. From the administrator dashboard, add employee accounts and departments. Employees can then sign in using the accounts created by the administrator.

## Useful Django commands

Run the development server:

```bash
python manage.py runserver
```

Check Django project configuration:

```bash
python manage.py check
```

Compile Python files to check for syntax errors:

```bash
python -m compileall .
```

## Database design

The main Oracle tables used by the application are:

- `USERS` — administrator and employee accounts.
- `DEPARTMENTS` — department names.
- `ATTENDANCE` — daily check-in and check-out records.
- `EMPLOYEE_TASKS` — tasks assigned to employees.
- `TASK_LOGS` — time spent on tasks.
- `LEAVE_REQUESTS` — leave applications and approval status.
- `LEAVE_BALANCES` — casual and sick leave balances.
- `NOTIFICATIONS` — employee notifications.
- `ANNOUNCEMENTS` — company announcements.
- `AUDIT_LOGS` — administrator activity history.

The application uses parameterized SQL in `database.py` with `python-oracledb`. It does not use Django ORM migrations for these business tables. Run `database/schema.sql` in Oracle SQL Developer to create them.

## Security notes

- Passwords are stored as Django password hashes, not plain text.
- Database values are passed using Oracle bind variables.
- Django CSRF protection is enabled for forms and API requests.
- Employee and administrator API permissions are checked on the server.
- The `.env` file must not be uploaded to GitHub.
- The included settings are intended for local development. Before deployment, use a strong `SECRET_KEY`, set `DEBUG=0`, configure `ALLOWED_HOSTS`, enable secure cookies over HTTPS and use a production-ready web server.

## Android emulator note

This is a responsive **web application**, not a native Android APK. To view it in an Android emulator, run the server on your computer using:

```bash
python manage.py runserver 0.0.0.0:8000
```

Then open `http://10.0.2.2:8000/` in the emulator browser.

## Developer

**Uday Shankar**  
GitHub: [@udayad25](https://github.com/udayad25)

---

This project is intended for learning and demonstration. Test it with a development Oracle database before using real employee information.
