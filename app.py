import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Folder to store uploads
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Max storage per user (in MB)
MAX_STORAGE_MB = 1024
MAX_STORAGE_BYTES = MAX_STORAGE_MB * 1024 * 1024

# Ensure base uploads folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ============================= Database Setup ================================= #

def init_db():
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        conn.commit()

# ============================= Utility Functions ================================= #

def get_storage_usage(folder):
    total_size = 0
    for root, dirs, files in os.walk(folder):
        for f in files:
            filepath = os.path.join(root, f)
            if os.path.isfile(filepath):
                total_size += os.path.getsize(filepath)
    return total_size

# ============================= Routes ================================= #

@app.route('/')
def index():
    return redirect('/login')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect('database.db') as conn:
            try:
                conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                conn.commit()
                return redirect('/login')
            except:
                return "Username already exists!"
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect('database.db') as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
            user = c.fetchone()
            if user:
                session['username'] = username
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

    username = session['username']
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], username)
    os.makedirs(user_folder, exist_ok=True)

    query = request.args.get('query', '').lower()
    category = request.args.get('category', 'All')
    files = []

    for fname in os.listdir(user_folder):
        if query and query not in fname.lower():
            continue
        ext = fname.split('.')[-1].lower()
        if category == 'Pictures' and ext in ['jpg', 'jpeg', 'png', 'gif']:
            files.append(fname)
        elif category == 'Videos' and ext in ['mp4', 'avi', 'mov']:
            files.append(fname)
        elif category == 'Documents' and ext in ['pdf', 'docx', 'txt', 'xlsx']:
            files.append(fname)
        elif category == 'All':
            files.append(fname)

    storage_used = get_storage_usage(user_folder)
    storage_percent = (storage_used / MAX_STORAGE_BYTES) * 100

    return render_template('home.html',
                           files=files,
                           category=category,
                           storage_used=storage_used,
                           storage_percent=round(storage_percent, 1),
                           max_storage=MAX_STORAGE_MB)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], username)
    os.makedirs(user_folder, exist_ok=True)

    file = request.files['file']
    if file:
        file_data = file.read()
        current_usage = get_storage_usage(user_folder)
        
        if current_usage + len(file_data) > MAX_STORAGE_BYTES:
            flash("Storage limit reached. File not uploaded.")
            return redirect('/home')

        file.seek(0)
        filepath = os.path.join(user_folder, file.filename)
        file.save(filepath)

    return redirect('/home')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], username)
    return send_from_directory(user_folder, filename)

@app.route('/view/<filename>')
def view_file(filename):
    return redirect(url_for('uploaded_file', filename=filename))

@app.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], username)
    file_path = os.path.join(user_folder, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    return redirect(url_for('home'))

# ============================= Main ================================= #

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
