# Office Helpdesk (Helpdesk LAN)

An internal IT helpdesk for the office network.
- **Employees** (no login) report problems, get a ticket number, track progress and read published solutions.
- **Admins** (password login) answer tickets, change status and priority, add private notes and publish answers.

Runs on one Windows computer. Other office PCs open it in a browser. Internet is needed only during installation.

---

## 1. Requirements
- Windows Server or Windows 10/11 that stays switched on.
- Python 3.12 or newer from python.org. During installation, tick **"Add python.exe to PATH"**.
- A static IP address for this computer (for example `192.168.1.100`).
- Optional but recommended: **NSSM** (https://nssm.cc/download), to run the helpdesk as a Windows service.

## 2. Install (one time)
1. Copy the whole `HelpdeskLAN` folder to the server, for example `C:\HelpdeskLAN`.
2. Open the **`scripts`** folder. All the setup files are there.
3. Double-click **`install.bat`**. It creates `venv\` and downloads Flask and Waitress.
4. Double-click **`create_admin.bat`** and choose a username and a password of at least 12 characters.
5. Right-click **`setup_firewall.bat`**, choose **Run as administrator**, and enter your office range (e.g. `192.168.1.0/24`).

## 3. Start the helpdesk
**Option A – permanent (recommended):**
copy `nssm.exe` (from the NSSM zip, `win64` folder) into the `HelpdeskLAN` folder, then right-click
**`scripts\install_service.bat`** and choose **Run as administrator**. The helpdesk now runs in the background and starts
automatically when Windows starts. To remove it later, use `scripts\uninstall_service.bat`.

**Option B – testing:** double-click **`scripts\start_server.bat`**. The helpdesk runs while that window is open.

Do not run both at the same time, because they use the same port (5000).

## 4. Addresses
| Who | Address |
|---|---|
| Employees | `http://SERVER-IP:5000` |
| Admin panel | `http://SERVER-IP:5000/admin` |

Find SERVER-IP with `ipconfig` on the server (IPv4 Address).

## 5. Backups
- Right-click **`scripts\schedule_backup.bat`** and choose **Run as administrator**. It schedules a backup every day at 23:00 and runs the first one immediately.
- Backups go to the `backups\` folder (one folder per day, newest 30 kept). Each contains `helpdesk.db` and `uploads\`.
- To back up to another drive or a NAS, edit `scripts\backup.bat` and set `HELPDESK_BACKUP_DIR`.
- Admins can also click **Back up now** under **Settings**.
- **To restore:** stop the service (or close `scripts\start_server.bat`), copy `helpdesk.db` from a backup into `data\`,
  copy its `uploads\` folder back, then start the helpdesk again.

## 6. Everyday admin tasks
| Task | How |
|---|---|
| Answer a ticket | All tickets → click the ticket → write the answer → set the status → Save |
| Share an answer with everyone | Keep "Publish on the shared Solutions board" ticked and set the status to **Resolved** |
| Keep an answer private | Untick "Publish". The employee still sees the answer on their Track page |
| Private notes | Use "Internal notes" on the ticket. Employees never see them |
| Change your password | Settings → Change my password |
| Forgotten password or locked account | Run `scripts\create_admin.bat` and enter the same username to reset it |
| Add another admin | Run `scripts\create_admin.bat` with a new username |

After 5 wrong passwords, an account is locked for 15 minutes.

## 7. Folder contents
| Item | Purpose |
|---|---|
| `app\` | **All the code**: `app.py` (pages and rules), `db.py` (database setup), `requirements.txt`, `templates\` (page designs) and `static\` (styles) |
| `scripts\` | **All the Windows setup scripts** (`.bat` files) |
| `data\helpdesk.db` | **All tickets** (created automatically) |
| `data\secret_key` | Keeps admins signed in across restarts. Keep it private |
| `uploads\` | Screenshots attached by employees |
| `backups\`, `logs\` | Daily backups and logs |
| `docs\` | The full documentation (Word file) |
| `design\` | The original clickable mock-ups (not used by the app) |
| `PROJECT_PLAN.md` | The project plan |

The folders `venv\`, `data\`, `uploads\`, `backups\` and `logs\` are created automatically next to `app\`,
so your data is always kept separate from the code.

## 8. Security notes
- Keep port 5000 closed to the internet. The firewall rule allows only your office range.
- This setup uses plain HTTP, so passwords are not encrypted on the network. Until HTTPS is added (planned for
  Version 2, using IIS), sign in to the admin panel only from wired office PCs.
- Only server administrators should have access to the `data`, `uploads` and `backups` folders.
- Uploads are limited to JPG, PNG and PDF files up to 5 MB, and only admins can download them.
- Ticket numbers run in order (HD-0001, HD-0002…). The Track page shows the subject, department, description and
  answer, but **never the employee's name, phone or location**. The Solutions board shows no personal details.

## 9. Settings you can change (environment variables)
| Variable | Default | Meaning |
|---|---|---|
| `HELPDESK_NAME` | `Office Helpdesk` | Name shown at the top of every page |
| `HELPDESK_BACKUP_DIR` | `backups\` | Where backups are saved |
| `HELPDESK_DATA_DIR` / `HELPDESK_UPLOAD_DIR` | `data\` / `uploads\` | Storage locations |
| `HTTPS_ONLY` | `0` | Set to `1` only after HTTPS is configured |

For the service, set them with `nssm set HelpdeskLAN AppEnvironmentExtra NAME=value`. Otherwise, add
`set NAME=value` to `scripts\start_server.bat`.

## 10. Troubleshooting
| Problem | Fix |
|---|---|
| Other PCs can't open the page | Check the firewall rule, that the service is running (`services.msc` → Helpdesk LAN) and that you're using the right IP |
| "Please run scripts\install.bat first" | Run `scripts\install.bat` |
| Port 5000 already in use | The service is probably already running. Don't also run `scripts\start_server.bat` |
| Errors | See `logs\service.log` and `logs\backup.log` |
