import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash

app = Flask(__name__)
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
MAX_MB = 1024
MAX_BYTES = MAX_MB * 1024 * 1024
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# =================== DB Setup =================== #

def init_db():
    with sqlite3.connect('database.db') as db:
        db.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS files (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL,
                        filename TEXT NOT NULL,
                        size INTEGER NOT NULL,
                        extension TEXT NOT NULL)''')

# =================== Utility =================== #

def get_usage(u):
    with sqlite3.connect('database.db') as db:
        row = db.execute("SELECT SUM(size) FROM files WHERE username = ?", (u,)).fetchone()
        return row[0] or 0

# =================== Routes =================== #

@app.route('/')
def index():
    return redirect('/login')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        with sqlite3.connect('database.db') as db:
            try:
                db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (u, p))
                db.commit()
                return redirect('/login')
            except:
                return "Username already exists!"
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        with sqlite3.connect('database.db') as db:
            row = db.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p)).fetchone()
            if row:
                session['username'] = u
                return redirect('/home')
            else:
                return "Invalid credentials!"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect('/login')

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect('/login')

    u = session['username']
    q = request.args.get('query', '').lower()
    c = request.args.get('category', 'All')

    ext_map = {
        'Pictures': ['jpg', 'jpeg', 'png', 'gif'],
        'Videos': ['mp4', 'avi', 'mov'],
        'Documents': ['pdf', 'docx', 'txt', 'xlsx'],
    }

    sql = "SELECT filename FROM files WHERE username = ?"
    args = [u]

    if q:
        sql += " AND LOWER(filename) LIKE ?"
        args.append(f"%{q}%")

    if c in ext_map:
        holders = ','.join('?' for _ in ext_map[c])
        sql += f" AND extension IN ({holders})"
        args.extend(ext_map[c])

    with sqlite3.connect('database.db') as db:
        files = [r[0] for r in db.execute(sql, args).fetchall()]

    used = get_usage(u)
    percent = (used / MAX_BYTES) * 100

    return render_template('home.html',
                           files=files,
                           category=c,
                           storage_used=used,
                           storage_percent=round(percent, 1),
                           max_storage=MAX_MB)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'username' not in session:
        return redirect('/login')

    u = session['username']
    path = os.path.join(app.config['UPLOAD_FOLDER'], u)
    os.makedirs(path, exist_ok=True)

    f = request.files['file']
    if f:
        data = f.read()
        size = len(data)
        ext = f.filename.rsplit('.', 1)[-1].lower()

        used = get_usage(u)
        if used + size > MAX_BYTES:
            flash("Storage limit reached. File not uploaded.")
            return redirect('/home')

        f.seek(0)
        full_path = os.path.join(path, f.filename)
        f.save(full_path)

        with sqlite3.connect('database.db') as db:
            db.execute("INSERT INTO files (username, filename, size, extension) VALUES (?, ?, ?, ?)",
                       (u, f.filename, size, ext))
            db.commit()

    return redirect('/home')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    if 'username' not in session:
        return redirect('/login')
    u = session['username']
    folder = os.path.join(app.config['UPLOAD_FOLDER'], u)
    return send_from_directory(folder, filename)

@app.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    if 'username' not in session:
        return redirect('/login')

    u = session['username']
    f_path = os.path.join(app.config['UPLOAD_FOLDER'], u, filename)

    with sqlite3.connect('database.db') as db:
        db.execute("DELETE FROM files WHERE username = ? AND filename = ?", (u, filename))
        db.commit()

    if os.path.exists(f_path):
        os.remove(f_path)

    return redirect(url_for('home'))

# =================== Run =================== #

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
