from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
import hashlib
import secrets

app = FastAPI()

DB_PATH = "yoga.db"

sessions_store = {}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            verified INTEGER DEFAULT 0
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS sessions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            session_date TEXT NOT NULL,
            capacity INTEGER NOT NULL
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS reservations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )"""
    )
    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def ensure_admin():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email=?", ("admin@example.com",))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users(email, password_hash, is_admin, verified) VALUES (?, ?, 1, 1)",
            ("admin@example.com", hash_password("admin")),
        )
        conn.commit()
    conn.close()


init_db()
ensure_admin()


def create_session_token(user_id: int) -> str:
    token = secrets.token_hex(16)
    sessions_store[token] = user_id
    return token


def get_current_user(request: Request):
    token = request.cookies.get("session")
    if token and token in sessions_store:
        user_id = sessions_store[token]
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        conn.close()
        return user
    return None


@app.get("/signup", response_class=HTMLResponse)
def signup_form():
    return """
    <h2>Sign Up</h2>
    <form method='post'>
    Email:<input name='email'/><br/>
    Password:<input name='password' type='password'/><br/>
    <button type='submit'>Sign Up</button>
    </form>
    """


@app.post("/signup")
def signup(email: str = Form(...), password: str = Form(...)):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users(email, password_hash) VALUES (?, ?)",
            (email, hash_password(password)),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return HTMLResponse("Email already registered.")
    conn.close()
    return RedirectResponse("/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_form():
    return """
    <h2>Login</h2>
    <form method='post'>
    Email:<input name='email'/><br/>
    Password:<input name='password' type='password'/><br/>
    <button type='submit'>Login</button>
    </form>
    """


@app.post("/login")
def login(response: RedirectResponse, email: str = Form(...), password: str = Form(...)):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email=? AND password_hash=?",
        (email, hash_password(password)),
    ).fetchone()
    conn.close()
    if user:
        token = create_session_token(user["id"])
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie("session", token, httponly=True)
        return resp
    return HTMLResponse("Invalid credentials.")


@app.get("/logout")
def logout(request: Request):
    token = request.cookies.get("session")
    if token and token in sessions_store:
        sessions_store.pop(token)
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("session")
    return resp


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    user = get_current_user(request)
    if not user:
        return """<p>Welcome!</p><a href='/login'>Login</a> or <a href='/signup'>Sign Up</a>"""
    links = "<a href='/sessions'>View Sessions</a> | <a href='/logout'>Logout</a>"
    if user["is_admin"]:
        links = "<a href='/admin'>Admin Dashboard</a> | " + links
    return f"<p>Logged in as {user['email']}</p>{links}"


@app.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request):
    user = get_current_user(request)
    if not user or not user["is_admin"]:
        return RedirectResponse("/", status_code=303)
    conn = get_db()
    unverified = conn.execute("SELECT id, email FROM users WHERE verified=0").fetchall()
    sessions = conn.execute("SELECT * FROM sessions ORDER BY session_date").fetchall()
    conn.close()
    html = "<h2>Admin Dashboard</h2>"
    html += "<h3>Unverified Users</h3>"
    for u in unverified:
        html += f"<p>{u['email']} <a href='/verify_user/{u['id']}'>Verify</a></p>"
    html += """<h3>Create Session</h3>
    <form method='post' action='/create_session'>
    Title:<input name='title'/><br/>
    Date (YYYY-MM-DD HH:MM):<input name='date'/><br/>
    Capacity:<input name='capacity' type='number' value='10'/><br/>
    <button type='submit'>Create</button>
    </form>
    """
    html += "<h3>Existing Sessions</h3>"
    for s in sessions:
        html += f"<p>{s['id']} {s['title']} {s['session_date']} cap:{s['capacity']}</p>"
    html += "<p><a href='/'>Home</a></p>"
    return html


@app.get("/verify_user/{user_id}")
def verify_user(request: Request, user_id: int):
    user = get_current_user(request)
    if not user or not user["is_admin"]:
        return RedirectResponse("/", status_code=303)
    conn = get_db()
    conn.execute("UPDATE users SET verified=1 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin", status_code=303)


@app.post("/create_session")
def create_session_route(request: Request, title: str = Form(...), date: str = Form(...), capacity: int = Form(...)):
    user = get_current_user(request)
    if not user or not user["is_admin"]:
        return RedirectResponse("/", status_code=303)
    conn = get_db()
    conn.execute(
        "INSERT INTO sessions(title, session_date, capacity) VALUES (?, ?, ?)",
        (title, date, capacity),
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/admin", status_code=303)


@app.get("/sessions", response_class=HTMLResponse)
def list_sessions(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    conn = get_db()
    sessions = conn.execute("SELECT * FROM sessions ORDER BY session_date").fetchall()
    reservations = conn.execute(
        "SELECT session_id FROM reservations WHERE user_id=?", (user["id"],)
    ).fetchall()
    reserved_ids = {r["session_id"] for r in reservations}
    conn.close()
    html = "<h2>Yoga Sessions</h2>"
    if not user["verified"]:
        html += "<p>Your account is pending verification.</p>"
    html += "<ul>"
    for s in sessions:
        html += f"<li>{s['title']} {s['session_date']} "
        if s['id'] in reserved_ids:
            html += "(reserved)"
        elif user['verified']:
            html += f"<a href='/reserve/{s['id']}'>Reserve</a>"
        html += "</li>"
    html += "</ul>"
    html += "<p><a href='/'>Home</a></p>"
    return html


@app.get("/reserve/{session_id}")
def reserve(request: Request, session_id: int):
    user = get_current_user(request)
    if not user or not user["verified"]:
        return RedirectResponse("/sessions", status_code=303)
    conn = get_db()
    cap_row = conn.execute(
        "SELECT capacity FROM sessions WHERE id=?", (session_id,)
    ).fetchone()
    if cap_row is None:
        conn.close()
        return RedirectResponse("/sessions", status_code=303)
    count = conn.execute(
        "SELECT COUNT(*) FROM reservations WHERE session_id=?", (session_id,)
    ).fetchone()[0]
    if count >= cap_row["capacity"]:
        conn.close()
        return HTMLResponse("Session full.")
    existing = conn.execute(
        "SELECT 1 FROM reservations WHERE session_id=? AND user_id=?",
        (session_id, user["id"]),
    ).fetchone()
    if existing:
        conn.close()
        return RedirectResponse("/sessions", status_code=303)
    conn.execute(
        "INSERT INTO reservations(session_id, user_id) VALUES (?, ?)",
        (session_id, user["id"]),
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/sessions", status_code=303)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
