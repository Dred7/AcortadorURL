from flask import Flask, request, jsonify, redirect, render_template, send_from_directory
import mysql.connector
import secrets
import os
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__, static_folder='../static', template_folder='../templates')

# Configuracion de cors para permitir solicitudes de apps android
CORS(app)

# Configuración de la base de datos
def get_db():
    try:
        conn = mysql.connector.connect(
            host=os.getenv('MYSQLHOST', 'localhost'),
            user=os.getenv('MYSQLUSER', 'root'),
            password=os.getenv('MYSQLPASSWORD', ''),
            database=os.getenv('MYSQLDATABASE', 'url_shortener'),
            port=os.getenv('MYSQLPORT', 3306)
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error de conexión a MySQL: {err}")
        raise
# Crea la tabla si no existe
def init_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS urls (
                id INT AUTO_INCREMENT PRIMARY KEY,
                original_url TEXT NOT NULL,
                short_code VARCHAR(8) NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                clicks INT DEFAULT 0
            )
        ''')
        conn.commit()
    except mysql.connector.Error as err:
        print(f"Error al crear tabla: {err}")
    finally:
        if conn.is_connected():
            conn.close()

init_db()

# Endpoint para acortar URL (API)
@app.route('/api/shorten', methods=['POST'])
def shorten_url():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "URL necesaria"}), 400
    
    original_url = data['url'].strip()
    if not original_url.startswith(('http://', 'https://')):
        original_url = f'https://{original_url}'
    
    short_code = secrets.token_urlsafe(4)[:6]  # Ejemplo: "AbCd12"
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Intento de inserción
        cursor.execute(
            'INSERT INTO urls (original_url, short_code) VALUES (%s, %s)',
            (original_url, short_code)
        )
        conn.commit()
        
        # Obtener URL base automáticamente
        host_url = request.host_url
        
        return jsonify({
            "original_url": original_url,
            "short_url": f"{host_url}{short_code}"
        })
        
    except mysql.connector.IntegrityError:
        # Si el código ya existe, generar uno nuevo
        short_code = secrets.token_urlsafe(4)[:6]
        cursor.execute(
            'INSERT INTO urls (original_url, short_code) VALUES (%s, %s)',
            (original_url, short_code)
        )
        conn.commit()
        return jsonify({
            "original_url": original_url,
            "short_url": f"{request.host_url}{short_code}"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
    finally:
        if conn.is_connected():
            conn.close()
# End point para listar URLs
@app.route('/api/urls', methods=['GET'])
def list_urls():
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('''
            SELECT original_url, short_code, created_at, clicks 
            FROM urls 
            ORDER BY created_at DESC
            LIMIT 100
        ''')
        
        urls = cursor.fetchall()
        host_url = request.host_url
        
        return jsonify([{
            "original": url['original_url'],
            "short": f"{host_url}{url['short_code']}",
            "created_at": url['created_at'].isoformat() if url['created_at'] else None,
            "clicks": url['clicks']
        } for url in urls])
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
    finally:
        if conn.is_connected():
            conn.close()

# Redirección desde la URL corta
@app.route('/<short_code>', methods=['GET'])
def redirect_url(short_code):
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # Obtener URL original
        cursor.execute(
            'SELECT original_url FROM urls WHERE short_code = %s',
            (short_code,)
        )
        result = cursor.fetchone()
        
        if not result:
            return jsonify({"error": "URL not found"}), 404
        
        # Actualizar contador de clics
        cursor.execute(
            'UPDATE urls SET clicks = clicks + 1 WHERE short_code = %s',
            (short_code,)
        )
        conn.commit()
        
        return redirect(result['original_url'])
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
    finally:
        if conn.is_connected():
            conn.close()

# Página principal (Frontend)
@app.route('/')
def home():
    return render_template('index.html')

# Servir archivos estáticos (CSS/JS)
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

# Health check para Railway
@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))