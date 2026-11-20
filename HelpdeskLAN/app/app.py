"""
Helpdesk LAN - internal IT helpdesk for the office network.

Code lives in HelpdeskLAN/app; data (data/, uploads/, backups/) lives one level up
in HelpdeskLAN/. The Windows scripts are in HelpdeskLAN/scripts.

Run in production with Waitress, from inside the app folder (see scripts/start_server.bat):
    waitress-serve --listen=0.0.0.0:5000 app:app

Command line tools (run from HelpdeskLAN):
    python app/app.py create-admin   create an admin or reset an admin's password
    python app/app.py backup         back up the database and uploads now
    python app/app.py init-db        create the database tables
    python app/app.py run            local test server on http://127.0.0.1:5000
"""
import getpass
import os
import re
import secrets
import shutil
import sqlite3
import sys
import uuid
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from db import add_log, close_db, connect, get_db, init_db, now, parse_time

# ---------------------------------------------------------------- settings
APP_DIR = os.path.dirname(os.path.abspath(__file__))       # HelpdeskLAN/app  (code)
PROJECT_DIR = os.path.dirname(APP_DIR)                      # HelpdeskLAN      (data lives here)
DATA_DIR = os.environ.get("HELPDESK_DATA_DIR", os.path.join(PROJECT_DIR, "data"))
UPLOAD_DIR = os.environ.get("HELPDESK_UPLOAD_DIR", os.path.join(PROJECT_DIR, "uploads"))
BACKUP_DIR = os.environ.get("HELPDESK_BACKUP_DIR", os.path.join(PROJECT_DIR, "backups"))
DB_PATH = os.path.join(DATA_DIR, "helpdesk.db")
APP_NAME = os.environ.get("HELPDESK_NAME", "Office Helpdesk")
HTTPS_ONLY = os.environ.get("HTTPS_ONLY", "0") == "1"

STATUSES = ["Open", "In progress", "Resolved"]
PRIORITIES = ["Low", "Medium", "High", "Urgent"]
PRIORITY_HELP = {
    "Low": "Low - can wait",
    "Medium": "Medium - slowing me down",
    "High": "High - can't work properly",
    "Urgent": "Urgent - can't work at all",
}
PRIORITY_ORDER_SQL = ("CASE priority WHEN 'Urgent' THEN 0 WHEN 'High' THEN 1 "
                      "WHEN 'Medium' THEN 2 ELSE 3 END")
PUBLISHED_SQL = "status = 'Resolved' AND published = 1 AND answer <> ''"

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
UPLOAD_SIGNATURES = {
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "pdf": (b"%PDF-",),
}
UPLOAD_MIMETYPES = {"jpg": "image/jpeg", "png": "image/png", "pdf": "application/pdf"}

MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15
MIN_PASSWORD_LENGTH = 12
BACKUPS_TO_KEEP = 30

FIELD_LIMITS = {
    "name": 100, "department": 100, "phone": 50, "location": 100,
    "category": 60, "subject": 150, "description": 5000,
}

for folder in (DATA_DIR, UPLOAD_DIR):
    os.makedirs(folder, exist_ok=True)
init_db(DB_PATH)


def _load_secret_key():
    """Random key kept in data/secret_key so logins survive restarts."""
    path = os.path.join(DATA_DIR, "secret_key")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(secrets.token_hex(32))
    with open(path, encoding="utf-8") as fh:
        return fh.read().strip()


app = Flask(__name__)
app.config.update(
    SECRET_KEY=_load_secret_key(),
    DB_PATH=DB_PATH,
    MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES + 512 * 1024,  # file + form fields
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=HTTPS_ONLY,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)
app.teardown_appcontext(close_db)


# ---------------------------------------------------------------- security
def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


@app.before_request
def protect_and_load_admin():
    if request.method == "POST":
        expected = session.get("csrf_token")
        sent = request.form.get("csrf_token", "")
        if not expected or not secrets.compare_digest(expected, sent):
            abort(400, "Your session expired or the form was not valid. Please go back, reload the page and try again.")
    g.admin = None
    admin_id = session.get("admin_id")
    if admin_id:
        g.admin = get_db().execute("SELECT * FROM admins WHERE id = ?", (admin_id,)).fetchone()
        if g.admin is None:
            session.clear()


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
    )
    if request.path.startswith("/admin"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.admin is None:
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------- template helpers
@app.context_processor
def inject_globals():
    ctx = {"app_name": APP_NAME, "csrf_token": csrf_token, "admin": g.get("admin")}
    if g.get("admin") is not None:
        ctx["open_count"] = get_db().execute(
            "SELECT COUNT(*) FROM tickets WHERE status = 'Open'").fetchone()[0]
    return ctx


@app.template_filter("dt")
def format_datetime(value):
    d = parse_time(value)
    if d is None:
        return ""
    today = date.today()
    if d.date() == today:
        return "Today " + d.strftime("%H:%M")
    if d.date() == today - timedelta(days=1):
        return "Yesterday " + d.strftime("%H:%M")
    return d.strftime("%d %b %Y, %H:%M")


@app.template_filter("status_class")
def status_class(status):
    return {"Open": "b-open", "In progress": "b-progress"}.get(status, "b-resolved")


# ---------------------------------------------------------------- utilities
def like(text):
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def normalize_ticket_no(text):
    """Accept 'HD-0042', 'hd42', '42' and return 'HD-0042'."""
    m = re.fullmatch(r"\s*(?:HD)?\s*-?\s*(\d{1,7})\s*", text or "", re.IGNORECASE)
    return f"HD-{int(m.group(1)):04d}" if m else None


def distinct_values(column):
    """Previously typed categories/departments, offered as suggestions."""
    assert column in ("category", "department")
    rows = get_db().execute(
        f"SELECT MIN({column}) AS v FROM tickets GROUP BY lower(trim({column})) "
        f"ORDER BY COUNT(*) DESC LIMIT 50").fetchall()
    return [r["v"] for r in rows]


def save_upload(file_storage):
    """Validate and store an attachment. Returns (original_name, stored_name)."""
    filename = file_storage.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in UPLOAD_SIGNATURES:
        raise ValueError("Only JPG, PNG or PDF files can be attached.")
    data = file_storage.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("The attachment is larger than 5 MB.")
    if not any(data.startswith(sig) for sig in UPLOAD_SIGNATURES[ext]):
        raise ValueError("The attachment does not look like a real JPG, PNG or PDF file.")
    ext = "jpg" if ext == "jpeg" else ext
    stored = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(UPLOAD_DIR, stored), "wb") as fh:
        fh.write(data)
    original = secure_filename(filename) or f"attachment.{ext}"
    return original, stored


def get_ticket_or_404(ticket_id):
    t = get_db().execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if t is None:
        abort(404)
    return t


def run_backup():
    """Copy the database (safely, while running) and uploads into backups/."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dest = os.path.join(BACKUP_DIR, f"helpdesk_{stamp}")
    os.makedirs(dest, exist_ok=True)
    src = connect(DB_PATH)
    dst = sqlite3.connect(os.path.join(dest, "helpdesk.db"))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    shutil.copytree(UPLOAD_DIR, os.path.join(dest, "uploads"), dirs_exist_ok=True)
    old = sorted(d for d in os.listdir(BACKUP_DIR) if d.startswith("helpdesk_"))
    for name in old[:-BACKUPS_TO_KEEP]:
        shutil.rmtree(os.path.join(BACKUP_DIR, name), ignore_errors=True)
    return dest


def last_backup_time():
    if not os.path.isdir(BACKUP_DIR):
        return None
    names = sorted(d for d in os.listdir(BACKUP_DIR) if d.startswith("helpdesk_"))
    if not names:
        return None
    try:
        return datetime.strptime(names[-1], "helpdesk_%Y-%m-%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


# ================================================================ employee pages
@app.route("/")
def home():
    db = get_db()
    recent = db.execute(f"SELECT * FROM tickets WHERE {PUBLISHED_SQL} "
                        "ORDER BY resolved_at DESC LIMIT 5").fetchall()
    categories = db.execute(f"SELECT MIN(category) AS name, COUNT(*) AS n FROM tickets "
                            f"WHERE {PUBLISHED_SQL} GROUP BY lower(trim(category)) "
                            "ORDER BY n DESC LIMIT 12").fetchall()
    return render_template("home.html", recent=recent, categories=categories)


@app.route("/solutions")
def solutions():
    db = get_db()
    q = request.args.get("q", "").strip()[:100]
    category = request.args.get("category", "").strip()[:60]
    sql = f"SELECT * FROM tickets WHERE {PUBLISHED_SQL}"
    params = []
    if q:
        sql += (" AND (subject LIKE ? ESCAPE '\\' OR answer LIKE ? ESCAPE '\\' "
                "OR category LIKE ? ESCAPE '\\')")
        params += [like(q)] * 3
    if category:
        sql += " AND trim(category) = ? COLLATE NOCASE"
        params.append(category)
    items = db.execute(sql + " ORDER BY resolved_at DESC LIMIT 200", params).fetchall()
    categories = db.execute(f"SELECT MIN(category) AS name FROM tickets WHERE {PUBLISHED_SQL} "
                            "GROUP BY lower(trim(category)) ORDER BY name").fetchall()
    return render_template("solutions.html", items=items, q=q, category=category,
                           categories=categories)


@app.route("/report", methods=["GET", "POST"])
def report():
    values = {"priority": "Medium"}
    errors = {}
    if request.method == "POST":
        for field, limit in FIELD_LIMITS.items():
            values[field] = request.form.get(field, "").strip()[:limit]
        values["priority"] = request.form.get("priority", "Medium")
        if values["priority"] not in PRIORITIES:
            values["priority"] = "Medium"
        for field, label in (("name", "your name"), ("department", "your department"),
                             ("category", "a category"), ("subject", "a subject"),
                             ("description", "a description of the problem")):
            if not values[field]:
                errors[field] = f"Please enter {label}."

        upload = request.files.get("attachment")
        original = stored = None
        if not errors and upload and upload.filename:
            try:
                original, stored = save_upload(upload)
            except ValueError as exc:
                errors["attachment"] = str(exc)

        if not errors:
            db = get_db()
            ts = now()
            cur = db.execute(
                "INSERT INTO tickets (created_at, updated_at, name, department, phone, location, "
                "category, priority, subject, description, attachment_name, attachment_file) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ts, ts, values["name"], values["department"], values["phone"], values["location"],
                 values["category"], values["priority"], values["subject"], values["description"],
                 original, stored))
            ticket_no = f"HD-{cur.lastrowid:04d}"
            db.execute("UPDATE tickets SET ticket_no = ? WHERE id = ?", (ticket_no, cur.lastrowid))
            add_log(db, cur.lastrowid, f"Ticket submitted by {values['name']} ({values['department']})")
            db.commit()
            return redirect(url_for("submitted", ticket_no=ticket_no))
        if upload and upload.filename and "attachment" not in errors:
            errors["attachment"] = "Please attach the file again after fixing the errors above."

    return render_template("report.html", values=values, errors=errors,
                           priorities=PRIORITIES, priority_help=PRIORITY_HELP,
                           category_suggestions=distinct_values("category"),
                           department_suggestions=distinct_values("department"))


@app.route("/submitted/<ticket_no>")
def submitted(ticket_no):
    t = get_db().execute("SELECT * FROM tickets WHERE ticket_no = ?", (ticket_no,)).fetchone()
    if t is None:
        abort(404)
    return render_template("submitted.html", t=t)


@app.route("/track")
def track():
    raw = request.args.get("no", "").strip()[:20]
    ticket = None
    if raw:
        no = normalize_ticket_no(raw)
        if no:
            ticket = get_db().execute("SELECT * FROM tickets WHERE ticket_no = ?", (no,)).fetchone()
    return render_template("track.html", raw=raw, t=ticket)


# ================================================================ admin pages
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if g.admin is not None:
        return redirect(url_for("admin_dashboard"))
    error = None
    username = ""
    next_url = request.values.get("next", "")
    if request.method == "POST":
        db = get_db()
        username = request.form.get("username", "").strip()[:60]
        password = request.form.get("password", "")
        row = db.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
        locked_until = parse_time(row["locked_until"]) if row else None
        if locked_until and locked_until > datetime.now():
            minutes = int((locked_until - datetime.now()).total_seconds() // 60) + 1
            error = f"Too many failed attempts. Try again in {minutes} minute(s)."
        elif row and check_password_hash(row["password_hash"], password):
            db.execute("UPDATE admins SET failed_attempts = 0, locked_until = NULL, last_login = ? "
                       "WHERE id = ?", (now(), row["id"]))
            db.commit()
            session.clear()
            session.permanent = True
            session["admin_id"] = row["id"]
            if not (next_url.startswith("/admin") and not next_url.startswith("//")):
                next_url = url_for("admin_dashboard")
            return redirect(next_url)
        else:
            if row:
                failed = row["failed_attempts"] + 1
                if failed >= MAX_FAILED_LOGINS:
                    until = (datetime.now() + timedelta(minutes=LOCK_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
                    db.execute("UPDATE admins SET failed_attempts = 0, locked_until = ? WHERE id = ?",
                               (until, row["id"]))
                else:
                    db.execute("UPDATE admins SET failed_attempts = ? WHERE id = ?", (failed, row["id"]))
                db.commit()
            else:
                check_password_hash(generate_password_hash("timing"), password)  # same delay
            error = "Wrong username or password."
    no_admin = get_db().execute("SELECT COUNT(*) FROM admins").fetchone()[0] == 0
    return render_template("admin_login.html", error=error, username=username,
                           next_url=next_url, no_admin=no_admin)


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    counts = {s: 0 for s in STATUSES}
    for r in db.execute("SELECT status, COUNT(*) AS n FROM tickets GROUP BY status"):
        counts[r["status"]] = r["n"]
    month_start = date.today().replace(day=1).strftime("%Y-%m-%d 00:00:00")
    resolved_month = db.execute(
        "SELECT created_at, resolved_at FROM tickets WHERE status = 'Resolved' AND resolved_at >= ?",
        (month_start,)).fetchall()
    hours = [(parse_time(r["resolved_at"]) - parse_time(r["created_at"])).total_seconds() / 3600
             for r in resolved_month]
    avg_hours = sum(hours) / len(hours) if hours else None
    received_month = db.execute("SELECT COUNT(*) FROM tickets WHERE created_at >= ?",
                                (month_start,)).fetchone()[0]
    attention = db.execute(
        f"SELECT * FROM tickets WHERE status <> 'Resolved' ORDER BY {PRIORITY_ORDER_SQL}, created_at "
        "LIMIT 8").fetchall()
    activity = db.execute(
        "SELECT l.action, l.created_at, t.id, t.ticket_no FROM ticket_log l "
        "JOIN tickets t ON t.id = l.ticket_id ORDER BY l.id DESC LIMIT 10").fetchall()
    return render_template("admin_dashboard.html", counts=counts, resolved_month=len(resolved_month),
                           avg_hours=avg_hours, received_month=received_month,
                           attention=attention, activity=activity)


@app.route("/admin/tickets")
@admin_required
def admin_tickets():
    db = get_db()
    status = request.args.get("status", "")
    priority = request.args.get("priority", "")
    category = request.args.get("category", "").strip()[:60]
    q = request.args.get("q", "").strip()[:100]
    sql, params = "SELECT * FROM tickets WHERE 1=1", []
    if status in STATUSES:
        sql += " AND status = ?"
        params.append(status)
    if priority in PRIORITIES:
        sql += " AND priority = ?"
        params.append(priority)
    if category:
        sql += " AND trim(category) = ? COLLATE NOCASE"
        params.append(category)
    if q:
        sql += (" AND (ticket_no LIKE ? ESCAPE '\\' OR subject LIKE ? ESCAPE '\\' OR name LIKE ? ESCAPE '\\' "
                "OR department LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\')")
        params += [like(q)] * 5
    tickets = db.execute(sql + " ORDER BY created_at DESC LIMIT 300", params).fetchall()
    counts = {s: 0 for s in STATUSES}
    for r in db.execute("SELECT status, COUNT(*) AS n FROM tickets GROUP BY status"):
        counts[r["status"]] = r["n"]
    return render_template("admin_tickets.html", tickets=tickets, counts=counts,
                           total=sum(counts.values()), status=status, priority=priority,
                           category=category, q=q, statuses=STATUSES, priorities=PRIORITIES,
                           categories=distinct_values("category"))


@app.route("/admin/tickets/<int:ticket_id>")
@admin_required
def admin_ticket(ticket_id):
    db = get_db()
    t = get_ticket_or_404(ticket_id)
    if not t["viewed"]:
        db.execute("UPDATE tickets SET viewed = 1 WHERE id = ?", (ticket_id,))
        add_log(db, ticket_id, f"Opened by {g.admin['username']}")
        db.commit()
    notes = db.execute("SELECT * FROM notes WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall()
    log = db.execute("SELECT * FROM ticket_log WHERE ticket_id = ? ORDER BY id DESC",
                     (ticket_id,)).fetchall()
    is_image = (t["attachment_file"] or "").endswith((".jpg", ".png"))
    return render_template("admin_ticket.html", t=t, notes=notes, log=log, is_image=is_image,
                           statuses=STATUSES, priorities=PRIORITIES)


@app.route("/admin/tickets/<int:ticket_id>/update", methods=["POST"])
@admin_required
def admin_ticket_update(ticket_id):
    db = get_db()
    t = get_ticket_or_404(ticket_id)
    answer = request.form.get("answer", "").strip()[:10000]
    status = request.form.get("status", t["status"])
    priority = request.form.get("priority", t["priority"])
    published = 1 if request.form.get("published") == "1" else 0
    if status not in STATUSES or priority not in PRIORITIES:
        abort(400)

    in_progress_at, resolved_at = t["in_progress_at"], t["resolved_at"]
    ts = now()
    changes = []
    if status != t["status"]:
        changes.append(f"Status changed from {t['status']} to {status}")
        if status == "In progress" and not in_progress_at:
            in_progress_at = ts
        if status == "Resolved":
            resolved_at = ts
        else:
            resolved_at = None
        if status == "Open":
            in_progress_at = None
    if priority != t["priority"]:
        changes.append(f"Priority changed from {t['priority']} to {priority}")
    if answer != t["answer"]:
        changes.append("Answer added" if not t["answer"] else "Answer updated")
    was_public = t["status"] == "Resolved" and t["published"] and t["answer"]
    is_public = status == "Resolved" and published and answer
    if is_public and not was_public:
        changes.append("Published on the Solutions board")
    elif was_public and not is_public:
        changes.append("Removed from the Solutions board")

    db.execute("UPDATE tickets SET answer = ?, status = ?, priority = ?, published = ?, "
               "in_progress_at = ?, resolved_at = ?, updated_at = ? WHERE id = ?",
               (answer, status, priority, published, in_progress_at, resolved_at, ts, ticket_id))
    for c in changes:
        add_log(db, ticket_id, f"{c} ({g.admin['username']})")
    db.commit()

    if not changes:
        flash("Nothing changed.", "info")
    elif status == "Resolved" and not answer:
        flash("Saved. Note: the ticket is resolved without an answer, so it won't appear on the Solutions board.", "warn")
    elif is_public:
        flash("Saved. The answer is now visible on the Solutions board.", "success")
    else:
        flash("Ticket updated.", "success")
    return redirect(url_for("admin_ticket", ticket_id=ticket_id))


@app.route("/admin/tickets/<int:ticket_id>/note", methods=["POST"])
@admin_required
def admin_ticket_note(ticket_id):
    get_ticket_or_404(ticket_id)
    text = request.form.get("text", "").strip()[:2000]
    if text:
        db = get_db()
        db.execute("INSERT INTO notes (ticket_id, text, author, created_at) VALUES (?, ?, ?, ?)",
                   (ticket_id, text, g.admin["username"], now()))
        add_log(db, ticket_id, f"Internal note added ({g.admin['username']})")
        db.commit()
        flash("Note added.", "success")
    return redirect(url_for("admin_ticket", ticket_id=ticket_id) + "#notes")


@app.route("/admin/tickets/<int:ticket_id>/delete", methods=["POST"])
@admin_required
def admin_ticket_delete(ticket_id):
    db = get_db()
    t = get_ticket_or_404(ticket_id)
    if t["attachment_file"]:
        try:
            os.remove(os.path.join(UPLOAD_DIR, t["attachment_file"]))
        except OSError:
            pass
    db.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
    db.commit()
    flash(f"Ticket {t['ticket_no']} was deleted.", "success")
    return redirect(url_for("admin_tickets"))


@app.route("/admin/tickets/<int:ticket_id>/attachment")
@admin_required
def admin_attachment(ticket_id):
    t = get_ticket_or_404(ticket_id)
    stored = t["attachment_file"]
    if not stored:
        abort(404)
    ext = stored.rsplit(".", 1)[-1]
    inline = request.args.get("inline") == "1" and ext in ("jpg", "png")
    return send_from_directory(UPLOAD_DIR, stored, mimetype=UPLOAD_MIMETYPES.get(ext),
                               as_attachment=not inline, download_name=t["attachment_name"])


@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    errors = {}
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not check_password_hash(g.admin["password_hash"], current):
            errors["current_password"] = "Current password is wrong."
        elif len(new) < MIN_PASSWORD_LENGTH:
            errors["new_password"] = f"Use at least {MIN_PASSWORD_LENGTH} characters."
        elif new != confirm:
            errors["confirm_password"] = "The two new passwords do not match."
        else:
            db = get_db()
            db.execute("UPDATE admins SET password_hash = ? WHERE id = ?",
                       (generate_password_hash(new), g.admin["id"]))
            db.commit()
            flash("Your password was changed.", "success")
            return redirect(url_for("admin_settings"))

    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    upload_files = [f for f in os.listdir(UPLOAD_DIR) if not f.startswith(".")]
    upload_size = sum(os.path.getsize(os.path.join(UPLOAD_DIR, f)) for f in upload_files)
    info = {
        "last_backup": last_backup_time(),
        "db_size": db_size, "upload_count": len(upload_files), "upload_size": upload_size,
        "backup_dir": BACKUP_DIR, "address": request.host_url.rstrip("/"),
        "min_password": MIN_PASSWORD_LENGTH,
    }
    return render_template("admin_settings.html", errors=errors, info=info)


@app.route("/admin/backup", methods=["POST"])
@admin_required
def admin_backup():
    try:
        dest = run_backup()
        flash(f"Backup created: {os.path.basename(dest)}", "success")
    except OSError as exc:
        flash(f"Backup failed: {exc}", "warn")
    return redirect(url_for("admin_settings"))


# ---------------------------------------------------------------- errors
@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(413)
@app.errorhandler(500)
def handle_error(err):
    code = getattr(err, "code", 500)
    messages = {
        400: "Something was wrong with that request.",
        404: "We couldn't find that page.",
        413: "The attachment is too large. The maximum size is 5 MB.",
        500: "Something went wrong on the server. Please try again.",
    }
    detail = getattr(err, "description", None) if code == 400 else None
    return render_template("error.html", code=code, message=detail or messages.get(code, messages[500])), code


# ---------------------------------------------------------------- command line
def cli_create_admin():
    conn = connect(DB_PATH)
    try:
        username = input("Admin username [admin]: ").strip() or "admin"
        existing = conn.execute("SELECT id FROM admins WHERE username = ?", (username,)).fetchone()
        if existing:
            answer = input(f"'{username}' already exists. Reset its password? (y/n): ").strip().lower()
            if answer != "y":
                print("Nothing changed.")
                return
        while True:
            pw = getpass.getpass(f"Password (at least {MIN_PASSWORD_LENGTH} characters, hidden): ")
            if len(pw) < MIN_PASSWORD_LENGTH:
                print(f"Too short. Use at least {MIN_PASSWORD_LENGTH} characters.")
                continue
            if getpass.getpass("Type the password again: ") != pw:
                print("The passwords do not match. Try again.")
                continue
            break
        if existing:
            conn.execute("UPDATE admins SET password_hash = ?, failed_attempts = 0, locked_until = NULL "
                         "WHERE id = ?", (generate_password_hash(pw), existing["id"]))
            print(f"Password for '{username}' was reset.")
        else:
            conn.execute("INSERT INTO admins (username, password_hash, created_at) VALUES (?, ?, ?)",
                         (username, generate_password_hash(pw), now()))
            print(f"Admin '{username}' created.")
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "create-admin":
        cli_create_admin()
    elif command == "backup":
        print("Backup created:", run_backup())
    elif command == "init-db":
        print("Database ready:", DB_PATH)
    elif command == "run":
        app.run(host="127.0.0.1", port=5000, debug=False)
    else:
        print(__doc__)
