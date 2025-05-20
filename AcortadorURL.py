from flask import Flask, request, jsonify, redirect, render_template, send_from_directory
import mysql.connector
import secrets
import os
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__, static_folder='static', template_folder='templates')

# Configuración de CORS para permitir solicitudes desde apps Android
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})
## FUNCIONES DE BASE DE DATOS ##

def get_db():
    """
    Establece conexión con la base de datos MySQL.
    Utiliza variables de entorno para la configuración con valores por defecto.
    
    Returns:
        conn: Objeto de conexión a MySQL o None si hay error
    """
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
        return None

def init_db():
    """
    Inicializa la base de datos creando la tabla 'urls' si no existe.
    La tabla almacena:
    - id: Identificador único
    - original_url: URL original
    - short_code: Código corto único
    - created_at: Fecha de creación
    - clicks: Contador de accesos
    """
    conn = None
    try:
        conn = get_db()
        if conn is None:
            print("No se pudo conectar a la DB. Reintentando...")
            return
            
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
        print("Tabla 'urls' creada/verificada")
    except mysql.connector.Error as err:
        print(f"Error al crear tabla: {err}")
    finally:
        if conn and conn.is_connected():
            conn.close()

# Inicializar la base de datos al iniciar la aplicación
init_db()

## ENDPOINTS DE LA API ##

@app.route('/api/shorten', methods=['POST'])
def shorten_url():
    """
    Endpoint para acortar URLs.
    
    Método: POST
    Parámetros (JSON):
    - url: URL original a acortar
    
    Retorna:
    - JSON con la URL original y la URL acortada
    - Códigos de estado HTTP apropiados para errores
    """
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "URL necesaria"}), 400
    
    original_url = data['url'].strip()
    if not original_url.startswith(('http://', 'https://')):
        original_url = f'https://{original_url}'
    
    # Generar código corto aleatorio de 6 caracteres
    short_code = secrets.token_urlsafe(4)[:6]
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Intento de inserción
        cursor.execute(
            'INSERT INTO urls (original_url, short_code) VALUES (%s, %s)',
            (original_url, short_code)
        )
        conn.commit()
        
        # Construir URL completa con el host actual
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
        if conn and conn.is_connected():
            conn.close()

@app.route('/api/urls', methods=['GET'])
def list_urls():
    """
    Endpoint para listar todas las URLs acortadas.
    
    Método: GET
    Parámetros: Ninguno
    
    Retorna:
    - JSON con lista de URLs (original, acortada, fecha creación, clics)
    - Ordenadas por fecha descendente (más recientes primero)
    - Límite de 100 registros
    """
    conn = None
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
        
        # Formatear respuesta
        return jsonify([{
            "original": url['original_url'],
            "short": f"{host_url}{url['short_code']}",
            "created_at": url['created_at'].isoformat() if url['created_at'] else None,
            "clicks": url['clicks']
        } for url in urls])
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.route('/api/urls/<short_code>', methods=['DELETE'])
def delete_url(short_code):
    """
    Endpoint para eliminar una URL acortada.
    
    Método: DELETE
    Parámetros:
    - short_code: Código corto de la URL a eliminar
    
    Retorna:
    - JSON con mensaje de éxito o error
    - Códigos de estado HTTP apropiados
    """
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Verificar si la URL existe
        cursor.execute(
            'SELECT id FROM urls WHERE short_code = %s',
            (short_code,)
        )
        if not cursor.fetchone():
            return jsonify({"error": "URL no encontrada"}), 404
        
        # Eliminar la URL
        cursor.execute(
            'DELETE FROM urls WHERE short_code = %s',
            (short_code,)
        )
        conn.commit()
        
        return jsonify({"message": "URL eliminada correctamente"})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.route('/<short_code>', methods=['GET'])
def redirect_url(short_code):
    """
    Endpoint para redireccionar desde una URL corta a la original.
    Incrementa el contador de clics cada vez que se accede.
    
    Parámetros:
    - short_code: Código corto de la URL
    
    Retorna:
    - Redirección a la URL original
    - Error 404 si no se encuentra la URL
    """
    conn = None
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
            return jsonify({"error": "URL no encontrada"}), 404
        
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
        if conn and conn.is_connected():
            conn.close()

## FRONTEND ##

@app.route('/')
def home():
    """Renderiza la página principal del acortador de URLs"""
    return render_template('index.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Sirve archivos estáticos (CSS, JS, imágenes)"""
    return send_from_directory(app.static_folder, filename)

## HEALTH CHECK ##

@app.route('/health')
def health_check():
    """Endpoint para verificar el estado del servicio"""
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
