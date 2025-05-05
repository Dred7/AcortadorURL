from flask import Flask, request, jsonify, redirect, render_template, send_from_directory
import sqlite3
import secrets
import os

app = Flask(__name__, static_folder='../static', template_folder='../templates')

# Configuración de la base de datos
def get_db():
    conn = sqlite3.connect('urls.db')
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_url TEXT NOT NULL,
            short_code TEXT NOT NULL UNIQUE
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Endpoint para acortar URL (API)
@app.route('/api/shorten', methods=['POST'])
def shorten_url():
    data = request.json
    original_url = data.get('url')
    
    if not original_url:
        return jsonify({"error": "URL is required"}), 400
    
    short_code = secrets.token_urlsafe(4)[:6]  # Ejemplo: "AbCd12"
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO urls (original_url, short_code) VALUES (?, ?)', (original_url, short_code))
        conn.commit()
    except sqlite3.IntegrityError:
        # Si el código ya existe, generamos otro
        short_code = secrets.token_urlsafe(4)[:6]
        cursor.execute('INSERT INTO urls (original_url, short_code) VALUES (?, ?)', (original_url, short_code))
        conn.commit()
    finally:
        conn.close()
    
    return jsonify({
        "original_url": original_url,
        "short_url": f"{request.host_url}{short_code}"  # URL dinámica (http://tudominio.com/AbCd12)
    })

@app.route('/api/urls', methods=['GET'])
def list_urls():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT original_url, short_code FROM urls ORDER BY id DESC')
    urls = cursor.fetchall()
    conn.close()
    
    url_list = [{
        "original": url[0],
        "short": f"{request.host_url}{url[1]}"  # URL completa (ej: http://localhost:5000/AbCd12)
    } for url in urls]
    
    return jsonify(url_list)

# Redirección desde la URL corta
@app.route('/<short_code>', methods=['GET'])
def redirect_url(short_code):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT original_url FROM urls WHERE short_code = ?', (short_code,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return redirect(result[0]) # Redirige a la URL original
    else:
        return jsonify({"error": "URL not found"}), 404

# Página principal (Frontend)
@app.route('/')
def home():
    return render_template('index.html')

# Servir archivos estáticos (CSS/JS)
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

if __name__ == '__main__':
    app.run(debug=True)