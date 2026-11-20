# Helpdesk LAN Application – Development Plan

## Context
`~/Downloads/Helpdesk LAN Application.docx` describes an internal IT helpdesk website that
runs on an office Windows Server. Employees use it over the office network to report problems,
and one admin answers them. The document is missing the actual application code (`app.py`) and
several operational pieces: auto-start, backups, upload rules and email alerts.
We've already built clickable design templates in `design/`
(`design/user.html` = employee side, `design/admin.html` = admin side, `design/index.html` = combined preview).
This plan turns those templates into a working application.

**Project folder:**
`~/Downloads/nblithd/HelpdeskLAN/`. This plan is `PROJECT_PLAN.md`;
the `design/` subfolder holds copies of the three page templates.

---

## 1. Goal
A simple, offline helpdesk for 10–30 employees:
- Employees report problems without logging in, get a ticket number, track progress and read solutions.
- Admins log in, reply, change status and publish useful answers to a shared Solutions board.

## 2. Scope

**Version 1 (must have)**, matching the templates:
- Employee: Home, Solutions board (with search and category filter), Report form (with screenshot upload), Confirmation with ticket number, Track ticket.
- Admin: Login, Dashboard, All tickets (with filters), Ticket detail (answer, status, priority, publish, internal notes, history), Settings (categories, departments, change password).
- Operations: runs as a Windows service, daily automatic backup, firewall rule.

**Version 2 (nice to have, later):**
- Reports page (charts), CSV export, "Did this solve it?" feedback, quick-reply templates,
  multiple admins, email notifications (needs your mail server details), HTTPS through IIS.

## 3. Technology
| Part | Choice | Why |
|---|---|---|
| Language | Python 3.12+ | As in the document; simple to maintain |
| Web framework | Flask | Small and well known |
| Web server | Waitress | Production-ready on Windows |
| Database | SQLite (a single file) | No database server to install |
| Pages | Flask (Jinja) templates in `app/templates/`, built from `design/user.html` / `design/admin.html` | No separate frontend build; works offline |
| Auto-start | NSSM (Windows service wrapper) | Survives reboots and closed windows |
| Backups | Windows Task Scheduler + `scripts/backup.bat` | Built into Windows |

## 4. Project folder layout (final app)
```
HelpdeskLAN/
├── app/                   # ALL CODE
│   ├── app.py             # routes and logic
│   ├── db.py              # database setup and queries
│   ├── requirements.txt
│   ├── templates/         # employee + admin pages (from design/)
│   └── static/            # CSS, JS (all local, no internet)
├── scripts/               # ALL WINDOWS SCRIPTS
│   ├── install.bat  create_admin.bat  setup_firewall.bat  start_server.bat
│   ├── install_service.bat  uninstall_service.bat   # Windows service via NSSM
│   └── backup.bat  schedule_backup.bat              # nightly backup via Task Scheduler
├── docs/                  # documentation (Word)
├── design/                # original mock-ups
├── data/helpdesk.db       # database (created automatically)
├── uploads/               # screenshots
├── backups/               # daily copies
├── README.md              # admin guide
└── PROJECT_PLAN.md
```

## 5. Data model
- **tickets**: ticket_no (HD-0001), created_at, name, department, phone, location, category,
  priority, subject, description, attachment, status (Open / In progress / Resolved),
  answer, published (yes/no), resolved_at
- **ticket_log**: ticket_id, action, timestamp (feeds the History panel)
- **notes**: ticket_id, text, created_at (admin-only)
- **admins**: username, password_hash, last_login
- **categories**, **departments**: editable lists for the Settings page

## 6. Security
- Admin passwords stored as hashes (never as plain text), with a minimum of 12 characters.
- Lock login for 15 minutes after 5 wrong attempts.
- Protection against forged form submissions (CSRF tokens) on every form.
- Uploads limited to JPG, PNG and PDF up to 5 MB, renamed to random names, and downloadable by admins only.
- Firewall allows only the office subnet; port 5000 is never exposed to the internet.
- Track page shows a ticket only when the exact number is entered; employee names are never shown on the public board.
- HTTPS through IIS in Version 2. Until then, the admin should log in only from wired office PCs.

## 7. Phases and timeline (estimate)
| Phase | Work | Duration |
|---|---|---|
| 0. Decisions | You confirm: categories, departments, priorities, required fields, company name/logo, server details | 1–2 days (your input) |
| 1. Core app | Database, employee pages, ticket creation and tracking | 2 days |
| 2. Admin side | Login, dashboard, ticket detail, settings, notes, history | 2 days |
| 3. Windows setup | Install scripts, Windows service, firewall, backup task, README | 1 day |
| 4. Testing | Test on a Mac/PC, then on the real server from 2–3 office PCs and a phone | 1 day |
| 5. Go-live | Install on the server, create the admin, announce to staff, one-page user guide | ½ day |
| 6. Version 2 | Reports, email alerts, HTTPS, etc. (as you choose) | Later |

## 8. What I need from you (Phase 0)
1. Server: Windows Server or a normal Windows PC? Its IP address? Can it stay on 24/7?
2. Categories, departments and priority levels (or keep the template's).
3. Which employee form fields are required: name, department, phone, location?
4. Company name, logo and colours.
5. Number of admins.
6. Which Version 2 features you want, if any.

## 9. Testing (checklist)
- An employee submits a ticket and receives a number; Track shows it as Open.
- The admin sees it on the dashboard, answers it, marks it Resolved and publishes it; it then appears on Solutions.
- An unpublished answer is visible on Track but not on Solutions.
- Wrong admin passwords cause a lockout; an oversized or disallowed upload is rejected.
- After a server reboot, the helpdesk comes back automatically.
- The nightly backup file appears, and restoring it works.
- Pages open from another office PC and from a phone.

## 10. Risks
| Risk | Mitigation |
|---|---|
| The server is switched off | Run as a Windows service; tell staff the server must stay on; use a UPS |
| Data loss | Daily backups to a second disk or NAS, and one test restore |
| Password read over Wi-Fi (plain HTTP) | Add HTTPS in Version 2; until then, admin uses a wired PC |
| Scope creep | Freeze Version 1 to the templates; everything else goes to Version 2 |
