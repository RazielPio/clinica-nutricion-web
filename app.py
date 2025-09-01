# app.py
import os
import uuid
import json
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for, session, 
                   flash, jsonify, g, send_from_directory, make_response)
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from fpdf import FPDF

# Importar la configuración desde config.py
from config import Config

app = Flask(__name__)
# Cargar configuración desde el objeto Config
app.config.from_object(Config)

# Asegurarse de que la carpeta de subidas exista
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# --- Conexión a DB y Decoradores ---

def get_db():
    """Obtiene una conexión a la base de datos para la solicitud actual."""
    if 'db' not in g:
        try:
            g.db = mysql.connector.connect(**Config.get_db_config())
        except Error as e:
            app.logger.error(f"Error al conectar a MySQL: {e}")
            g.db = None
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    """Cierra la conexión a la base de datos al final de la solicitud."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def db_connection_error_handler(f):
    """Decorador para manejar errores de conexión a la DB de forma centralizada."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not get_db():
            flash("Error de conexión con la base de datos. Por favor, inténtalo más tarde.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    """Decorador para requerir que un usuario haya iniciado sesión."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    """Decorador para requerir que un usuario tenga un rol específico."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('user_rol') not in roles:
                flash('No tienes permiso para acceder a esta página.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Rutas Principales ---

@app.route('/')
def index():
    if 'user_id' in session:
        rol = session.get('user_rol')
        if rol == 'admin': return redirect(url_for('admin_dashboard'))
        if rol == 'recepcion': return redirect(url_for('recepcion_dashboard'))
        if rol == 'nutriologo': return redirect(url_for('pacientes_dashboard'))
        if rol == 'entrenador': return redirect(url_for('entrenador_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email, password = request.form['email'], request.form['password']
        db = get_db()
        if not db:
            flash("Error de conexión con la base de datos.", "danger")
            return render_template('login.html')

        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        usuario = cursor.fetchone()
        
        if usuario and check_password_hash(usuario['password_hash'], password):
            if usuario['estado'] != 'activo':
                flash('Tu cuenta está inactiva. Contacta al administrador.', 'danger')
                return redirect(url_for('login'))
            
            session.update(user_id=usuario['id'], user_rol=usuario['rol'], user_name=usuario['nombre'])
            cursor.execute("INSERT INTO log_sesiones (id_usuario, fecha_hora, ip_address) VALUES (%s, %s, %s)", 
                           (usuario['id'], datetime.now(), request.remote_addr))
            db.commit()
            flash(f"Bienvenido de nuevo, {usuario['nombre']}!", 'success')
            return redirect(url_for('index'))
        else:
            flash('Email o contraseña incorrectos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('login'))

# --- Rutas de Administrador ---

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
@db_connection_error_handler
def admin_dashboard():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre, email, estado, rol FROM usuarios WHERE rol IN ('nutriologo', 'recepcion', 'entrenador')")
    usuarios = cursor.fetchall()
    cursor.execute("""
        SELECT l.fecha_hora, l.ip_address, u.nombre, u.rol 
        FROM log_sesiones l JOIN usuarios u ON l.id_usuario = u.id 
        ORDER BY l.fecha_hora DESC LIMIT 50
    """)
    logs = cursor.fetchall()
    return render_template('admin_dashboard.html', usuarios=usuarios, logs=logs)

@app.route('/admin/update_status/<int:user_id>/<string:new_status>', methods=['POST'])
@login_required
@role_required('admin')
@db_connection_error_handler
def update_user_status(user_id, new_status):
    if new_status not in ['activo', 'inactivo']:
        flash('Estado no válido.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE usuarios SET estado = %s WHERE id = %s", (new_status, user_id))
    db.commit()
    flash('El estado del usuario ha sido actualizado.', 'success')
    return redirect(url_for('admin_dashboard'))

# --- Rutas de Recepción ---

@app.route('/recepcion/dashboard')
@login_required
@role_required('recepcion')
@db_connection_error_handler
def recepcion_dashboard():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre FROM usuarios WHERE rol = 'nutriologo' AND estado = 'activo' ORDER BY nombre")
    nutriologos = cursor.fetchall()
    cursor.execute("SELECT id, nombre FROM usuarios WHERE rol = 'entrenador' AND estado = 'activo' ORDER BY nombre")
    entrenadores = cursor.fetchall()
    return render_template('recepcion_dashboard.html', nutriologos=nutriologos, entrenadores=entrenadores)

@app.route('/recepcion/add_patient', methods=['POST'])
@login_required
@role_required('recepcion')
@db_connection_error_handler
def add_patient():
    db = get_db()
    nombre = request.form['nombre_completo']
    fecha_nac = request.form.get('fecha_nacimiento') or None
    estatura_cm = request.form.get('estatura_cm') or None
    telefono = request.form.get('telefono') or None
    email = request.form.get('email') or None
    id_nutriologo = request.form.get('id_nutriologo_asignado') or None
    id_entrenador = request.form.get('id_entrenador_asignado') or None
    
    cursor = db.cursor()
    sql = """
        INSERT INTO pacientes 
        (nombre_completo, fecha_nacimiento, estatura_cm, telefono, email, id_nutriologo_asignado, id_entrenador_asignado) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(sql, (nombre, fecha_nac, estatura_cm, telefono, email, id_nutriologo, id_entrenador))
    db.commit()
    flash('Paciente registrado exitosamente.', 'success')
    return redirect(url_for('recepcion_dashboard'))

def _calculate_body_composition(form_data, peso):
    def get_float(name):
        try:
            val = form_data.get(name)
            return float(val) if val else None
        except (ValueError, TypeError):
            return None

    composicion = {}
    if not peso:
        return composicion

    masa_muscular_pct_total = get_float('masa_muscular_pct')
    if masa_muscular_pct_total is not None:
        composicion['masa_muscular_kg'] = round((masa_muscular_pct_total / 100) * peso, 2)

    segment_weight_percentages = {
        'tronco': 0.50, 'brazo_der': 0.06, 'brazo_izq': 0.06, 
        'pierna_der': 0.19, 'pierna_izq': 0.19
    }
    
    for segment, weight_pct in segment_weight_percentages.items():
        estimated_segment_weight = peso * weight_pct
        for comp_type in ['grasa', 'musculo']:
            pct_key = f'{comp_type}_{segment}_pct'
            kg_key = f'{comp_type}_{segment}_kg'
            pct_value = get_float(pct_key)
            if pct_value is not None:
                composicion[kg_key] = round((pct_value / 100) * estimated_segment_weight, 2)
    
    return composicion

@app.route('/recepcion/add_measurement', methods=['POST'])
@login_required
@role_required('recepcion')
@db_connection_error_handler
def add_measurement():
    db = get_db()

    def get_float(name):
        try:
            val = request.form.get(name)
            return float(val) if val else None
        except (ValueError, TypeError): return None

    required_fields = [
        'peso', 'altura', 'grasa_corporal_pct', 'masa_muscular_pct', 'bmr_kcal', 'amr_kcal',
        'agua_corporal_pct', 'masa_osea_kg', 'grasa_visceral', 'grasa_tronco_pct', 'musculo_tronco_pct',
        'grasa_brazo_der_pct', 'musculo_brazo_der_pct', 'grasa_brazo_izq_pct', 'musculo_brazo_izq_pct',
        'grasa_pierna_der_pct', 'musculo_pierna_der_pct', 'grasa_pierna_izq_pct', 'musculo_pierna_izq_pct'
    ]
    
    missing_fields = [field for field in required_fields if not request.form.get(field)]
    if missing_fields:
        flash(f'Error: Faltan datos en la medición. Por favor, completa todos los campos requeridos.', 'danger')
        return redirect(url_for('recepcion_dashboard'))

    db_data = {
        'id_paciente': int(request.form.get('id_paciente')),
        'fecha_medicion': datetime.now(),
        'observaciones': request.form.get('observaciones') or None,
    }
    
    for field in required_fields:
        db_data[field] = get_float(field)

    if db_data['peso']:
        if db_data['altura'] and db_data['altura'] > 0:
            db_data['imc'] = round(db_data['peso'] / (db_data['altura'] ** 2), 2)
        
        composicion_kg = _calculate_body_composition(request.form, db_data['peso'])
        db_data.update(composicion_kg)

    cursor = db.cursor()
    cursor.execute("SHOW COLUMNS FROM mediciones")
    table_columns = {col[0] for col in cursor.fetchall()}
    final_data = {k: v for k, v in db_data.items() if k in table_columns and v is not None}

    columns = ', '.join([f'`{k}`' for k in final_data.keys()])
    placeholders = ', '.join(['%s'] * len(final_data))
    sql = f"INSERT INTO mediciones ({columns}) VALUES ({placeholders})"
    
    cursor.execute(sql, list(final_data.values()))
    db.commit()
    
    flash('Medición registrada y calculada exitosamente.', 'success')
    return redirect(url_for('recepcion_dashboard'))

# --- Rutas de Pacientes y Asignaciones ---

@app.route('/pacientes')
@login_required
@role_required('nutriologo', 'admin')
@db_connection_error_handler
def pacientes_dashboard():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    sql_query = """
        SELECT 
            p.*, 
            u_nutri.nombre as nutriologo_nombre, 
            u_entre.nombre as entrenador_nombre 
        FROM pacientes p 
        LEFT JOIN usuarios u_nutri ON p.id_nutriologo_asignado = u_nutri.id
        LEFT JOIN usuarios u_entre ON p.id_entrenador_asignado = u_entre.id
    """
    params = []
    if session['user_rol'] == 'nutriologo':
        sql_query += " WHERE p.id_nutriologo_asignado = %s OR p.id_nutriologo_asignado IS NULL"
        params.append(session['user_id'])
    
    sql_query += " ORDER BY p.nombre_completo"
    cursor.execute(sql_query, tuple(params))
    pacientes = cursor.fetchall()
    return render_template('pacientes_dashboard.html', pacientes=pacientes)

@app.route('/paciente/<int:paciente_id>')
@login_required
@role_required('nutriologo', 'recepcion', 'admin', 'entrenador')
@db_connection_error_handler
def ver_paciente(paciente_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.*, u_nutri.nombre as nutriologo_nombre, u_entre.nombre as entrenador_nombre
        FROM pacientes p 
        LEFT JOIN usuarios u_nutri ON p.id_nutriologo_asignado = u_nutri.id
        LEFT JOIN usuarios u_entre ON p.id_entrenador_asignado = u_entre.id
        WHERE p.id = %s
    """, (paciente_id,))
    paciente = cursor.fetchone()
    
    if not paciente:
        flash("Paciente no encontrado.", "danger")
        return redirect(url_for('index'))
    
    user_id = session['user_id']
    user_rol = session['user_rol']
    
    if user_rol == 'nutriologo' and paciente['id_nutriologo_asignado'] != user_id and paciente['id_nutriologo_asignado'] is not None:
        flash("No tienes permiso para ver este paciente.", "danger")
        return redirect(url_for('pacientes_dashboard'))
    
    if user_rol == 'entrenador' and paciente['id_entrenador_asignado'] != user_id and paciente['id_entrenador_asignado'] is not None:
        flash("Este paciente no está asignado a ti.", "danger")
        return redirect(url_for('entrenador_dashboard'))

    cursor.execute("SELECT * FROM mediciones WHERE id_paciente = %s ORDER BY fecha_medicion ASC", (paciente_id,))
    mediciones_asc = cursor.fetchall()
    mediciones_desc = sorted(mediciones_asc, key=lambda x: x['fecha_medicion'], reverse=True)

    chart_data = {
        "labels": [m['fecha_medicion'].strftime('%d-%m-%Y') for m in mediciones_asc],
        "peso": [float(m['peso']) for m in mediciones_asc if m.get('peso') is not None],
        "grasa": [float(m['grasa_corporal_pct']) for m in mediciones_asc if m.get('grasa_corporal_pct') is not None],
        "musculo": [float(m['masa_muscular_kg']) for m in mediciones_asc if m.get('masa_muscular_kg') is not None]
    }
    
    radar_data = None
    if mediciones_desc:
        last_med = mediciones_desc[0]
        radar_data = {
            "labels": ["Tronco", "Brazo Derecho", "Brazo Izquierdo", "Pierna Derecha", "Pierna Izquierda"],
            "musculo_kg": [
                last_med.get('musculo_tronco_kg'), last_med.get('musculo_brazo_der_kg'),
                last_med.get('musculo_brazo_izq_kg'), last_med.get('musculo_pierna_der_kg'),
                last_med.get('musculo_pierna_izq_kg')
            ],
            "grasa_kg": [
                last_med.get('grasa_tronco_kg'), last_med.get('grasa_brazo_der_kg'),
                last_med.get('grasa_brazo_izq_kg'), last_med.get('grasa_pierna_der_kg'),
                last_med.get('grasa_pierna_izq_kg')
            ]
        }

    cursor.execute("SELECT * FROM historial_clinico WHERE id_paciente = %s", (paciente_id,))
    historial = cursor.fetchone() or {}
    cursor.execute("SELECT * FROM dietas_pdf WHERE id_paciente = %s ORDER BY fecha_subida DESC", (paciente_id,))
    dietas = cursor.fetchall()
    cursor.execute("SELECT * FROM rutinas_pdf WHERE id_paciente = %s ORDER BY fecha_subida DESC", (paciente_id,))
    rutinas = cursor.fetchall()

    def to_safe_json(data):
        return json.dumps(data, default=str) if data else json.dumps({})

    # CORRECCIÓN: Pasar la variable con el nombre que espera la plantilla.
    return render_template('ver_paciente.html', 
                           paciente=paciente, 
                           mediciones_desc=mediciones_desc, 
                           historial=historial, 
                           chart_data_json=to_safe_json(chart_data), 
                           radar_data_json=to_safe_json(radar_data),
                           dietas=dietas,
                           rutinas=rutinas)

@app.route('/paciente/<int:paciente_id>/historial', methods=['GET', 'POST'])
@login_required
@role_required('nutriologo', 'admin')
@db_connection_error_handler
def editar_historial_clinico(paciente_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    if request.method == 'POST':
        form_data = {key: (val or None) for key, val in request.form.items()}
        
        if form_data.get('estatura_cm'):
            cursor.execute("UPDATE pacientes SET estatura_cm = %s WHERE id = %s", (form_data['estatura_cm'], paciente_id))
        
        form_data.pop('estatura_cm', None)
        
        cursor.execute("SELECT id FROM historial_clinico WHERE id_paciente = %s", (paciente_id,))
        existe = cursor.fetchone()
        
        if existe:
            fields = ", ".join([f"`{key}`=%s" for key in form_data.keys()])
            sql = f"UPDATE historial_clinico SET {fields} WHERE id_paciente=%s"
            params = list(form_data.values()) + [paciente_id]
        else:
            form_data["id_paciente"] = paciente_id
            keys = ", ".join([f'`{k}`' for k in form_data.keys()])
            values = ", ".join(['%s'] * len(form_data))
            sql = f"INSERT INTO historial_clinico ({keys}) VALUES ({values})"
            params = list(form_data.values())
            
        cursor.execute(sql, tuple(params))
        db.commit()
        flash('Historial clínico guardado exitosamente.', 'success')
        return redirect(url_for('ver_paciente', paciente_id=paciente_id))

    cursor.execute("SELECT * FROM pacientes WHERE id = %s", (paciente_id,))
    paciente = cursor.fetchone()
    if not paciente:
        flash("Paciente no encontrado.", "danger")
        return redirect(url_for('pacientes_dashboard'))
        
    cursor.execute("SELECT * FROM historial_clinico WHERE id_paciente = %s", (paciente_id,))
    historial = cursor.fetchone()
    if not historial:
        historial = {'estatura_cm': paciente.get('estatura_cm')}

    return render_template('historial_clinico.html', paciente=paciente, historial=historial)

@app.route('/paciente/<int:paciente_id>/reasignar', methods=['GET'])
@login_required
@role_required('admin')
@db_connection_error_handler
def reasignar_paciente_page(paciente_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM pacientes WHERE id = %s", (paciente_id,))
    paciente = cursor.fetchone()

    if not paciente:
        flash("Paciente no encontrado.", "danger")
        return redirect(url_for('pacientes_dashboard'))
        
    cursor.execute("SELECT id, nombre FROM usuarios WHERE rol = 'nutriologo' AND estado = 'activo'")
    nutriologos = cursor.fetchall()
    cursor.execute("SELECT id, nombre FROM usuarios WHERE rol = 'entrenador' AND estado = 'activo'")
    entrenadores = cursor.fetchall()
    
    return render_template('reasignar_paciente.html', paciente=paciente, nutriologos=nutriologos, entrenadores=entrenadores)

@app.route('/paciente/<int:paciente_id>/update_assignments', methods=['POST'])
@login_required
@role_required('admin', 'recepcion')
@db_connection_error_handler
def update_assignments(paciente_id):
    db = get_db()
    cursor = db.cursor()
    nuevo_nutriologo_id = request.form.get('id_nutriologo_asignado')
    nuevo_entrenador_id = request.form.get('id_entrenador_asignado')

    if nuevo_nutriologo_id is not None:
        id_nutri = None if nuevo_nutriologo_id == 'null' else nuevo_nutriologo_id
        cursor.execute("UPDATE pacientes SET id_nutriologo_asignado = %s WHERE id = %s", (id_nutri, paciente_id))
    
    if nuevo_entrenador_id is not None:
        id_entre = None if nuevo_entrenador_id == 'null' else nuevo_entrenador_id
        cursor.execute("UPDATE pacientes SET id_entrenador_asignado = %s WHERE id = %s", (id_entre, paciente_id))
        
    db.commit()
    flash('Asignaciones del paciente actualizadas exitosamente.', 'success')
    
    if session.get('user_rol') == 'recepcion':
        return redirect(url_for('recepcion_dashboard'))
    else:
        return redirect(url_for('pacientes_dashboard'))

# --- Rutas de Entrenador ---

@app.route('/entrenador/dashboard')
@login_required
@role_required('entrenador')
@db_connection_error_handler
def entrenador_dashboard():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    sql_query = """
        SELECT p.id, p.nombre_completo, u_nutri.nombre as nutriologo_nombre
        FROM pacientes p 
        LEFT JOIN usuarios u_nutri ON p.id_nutriologo_asignado = u_nutri.id
        WHERE p.id_entrenador_asignado = %s
        ORDER BY p.nombre_completo
    """
    cursor.execute(sql_query, (session['user_id'],))
    pacientes = cursor.fetchall()
    
    return render_template('entrenador_dashboard.html', pacientes=pacientes)

# --- Rutas de API y Archivos ---

@app.route('/api/search_patients')
@login_required
@role_required('recepcion', 'admin', 'nutriologo')
@db_connection_error_handler
def search_patients():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])
    
    sql = """
        SELECT 
            p.id, p.nombre_completo, p.estatura_cm,
            u_nutri.nombre AS nutriologo_nombre,
            u_entre.nombre AS entrenador_nombre
        FROM pacientes p 
        LEFT JOIN usuarios u_nutri ON p.id_nutriologo_asignado = u_nutri.id 
        LEFT JOIN usuarios u_entre ON p.id_entrenador_asignado = u_entre.id
        WHERE p.nombre_completo LIKE %s LIMIT 10
    """
    cursor.execute(sql, (f"%{query}%",))
    pacientes = cursor.fetchall()
    return jsonify(pacientes)

@app.route('/paciente/<int:paciente_id>/upload_pdf', methods=['POST'])
@login_required
@db_connection_error_handler
def upload_pdf(paciente_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    user_id = session['user_id']
    user_rol = session['user_rol']
    
    file_type = request.form.get('file_type')
    if not file_type or file_type not in ['dieta', 'rutina']:
        flash('Tipo de archivo no especificado o no válido.', 'danger')
        return redirect(request.referrer)

    # Obtener datos del paciente para la autorización
    cursor.execute("SELECT id_nutriologo_asignado, id_entrenador_asignado FROM pacientes WHERE id = %s", (paciente_id,))
    paciente = cursor.fetchone()
    if not paciente:
        flash('Paciente no encontrado.', 'danger')
        return redirect(url_for('pacientes_dashboard'))

    # Lógica de autorización mejorada
    is_authorized = False
    if user_rol == 'admin':
        is_authorized = True
    elif user_rol == 'nutriologo' and file_type == 'dieta':
        if paciente['id_nutriologo_asignado'] == user_id or paciente['id_nutriologo_asignado'] is None:
            is_authorized = True
    elif user_rol == 'entrenador' and file_type == 'rutina':
        if paciente['id_entrenador_asignado'] == user_id or paciente['id_entrenador_asignado'] is None:
            is_authorized = True
    
    if not is_authorized:
        flash('No tienes permiso para subir archivos a este paciente.', 'danger')
        return redirect(request.referrer or url_for('index'))

    if 'archivo_pdf' not in request.files or request.files['archivo_pdf'].filename == '':
        flash('No se seleccionó ningún archivo.', 'danger')
        return redirect(request.referrer)
    
    file = request.files['archivo_pdf']
    if file and allowed_file(file.filename):
        original_filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        
        if file_type == 'dieta':
            table, id_col = 'dietas_pdf', 'id_nutriologo'
        else: # rutina
            table, id_col = 'rutinas_pdf', 'id_entrenador'

        sql = f"""INSERT INTO {table} (id_paciente, {id_col}, nombre_archivo_original, nombre_archivo_guardado, fecha_subida) 
                  VALUES (%s, %s, %s, %s, %s)"""
        cursor.execute(sql, (paciente_id, user_id, original_filename, unique_filename, datetime.now()))
        db.commit()
        flash(f'{file_type.capitalize()} subida exitosamente.', 'success')
    else:
        flash('Formato de archivo no permitido. Solo se aceptan PDF.', 'danger')

    return redirect(url_for('ver_paciente', paciente_id=paciente_id))

@app.route('/delete_pdf/<string:file_type>/<int:file_id>', methods=['POST'])
@login_required
@db_connection_error_handler
def delete_pdf(file_type, file_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    table_map = {'dieta': 'dietas_pdf', 'rutina': 'rutinas_pdf'}
    if file_type not in table_map:
        flash('Tipo de archivo no válido.', 'danger')
        return redirect(url_for('index'))

    table_name = table_map[file_type]
    
    cursor.execute(f"SELECT nombre_archivo_guardado, id_paciente FROM {table_name} WHERE id = %s", (file_id,))
    file_info = cursor.fetchone()

    if not file_info:
        flash('Archivo no encontrado.', 'danger')
        return redirect(url_for('index'))

    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file_info['nombre_archivo_guardado']))
    except OSError as e:
        app.logger.error(f"Error al borrar archivo físico: {e}")

    cursor.execute(f"DELETE FROM {table_name} WHERE id = %s", (file_id,))
    db.commit()

    flash(f'{file_type.capitalize()} eliminada exitosamente.', 'success')
    return redirect(url_for('ver_paciente', paciente_id=file_info['id_paciente']))

@app.route('/uploads/<path:filename>')
@login_required
@db_connection_error_handler
def download_file(filename):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    cursor.execute("SELECT id_paciente FROM dietas_pdf WHERE nombre_archivo_guardado = %s", (filename,))
    dieta = cursor.fetchone()
    cursor.execute("SELECT id_paciente FROM rutinas_pdf WHERE nombre_archivo_guardado = %s", (filename,))
    rutina = cursor.fetchone()

    paciente_id = (dieta['id_paciente'] if dieta else None) or (rutina['id_paciente'] if rutina else None)

    if not paciente_id:
        flash('Archivo no encontrado.', 'danger')
        return redirect(url_for('index'))

    cursor.execute("SELECT id_nutriologo_asignado, id_entrenador_asignado FROM pacientes WHERE id = %s", (paciente_id,))
    paciente = cursor.fetchone()
    user_id, user_rol = session['user_id'], session['user_rol']

    is_authorized = (
        user_rol in ['admin', 'recepcion'] or
        (paciente and user_rol == 'nutriologo' and paciente['id_nutriologo_asignado'] == user_id) or
        (paciente and user_rol == 'entrenador' and paciente['id_entrenador_asignado'] == user_id)
    )

    if not is_authorized:
        flash('No tienes permiso para descargar este archivo.', 'danger')
        return redirect(url_for('index'))

    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# --- Generación de PDF ---

class PDF(FPDF):
    def header(self):
        try:
            self.image('static/img/logo_clinica.png', 10, 8, 33)
        except Exception as e:
            app.logger.error(f"No se pudo cargar el logo del PDF: {e}")
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, 'Clinigramm', 0, 1, 'L')

        self.set_font('Arial', 'B', 20)
        self.set_text_color(0, 0, 0)
        self.cell(0, 10, 'Reporte de Composición Corporal', 0, 1, 'R')
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(0, 0, 0)
        fecha = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        self.cell(0, 10, f'Página {self.page_no()} | Generado el {fecha}', 0, 0, 'C')

    def section_title(self, title):
        self.set_font('Arial', 'B', 14)
        self.set_fill_color(240, 240, 240)
        self.set_text_color(0, 0, 0)
        self.cell(0, 8, title, 0, 1, 'L', fill=True) # Reducir altura de celda
        self.ln(2) # Reducir espacio

    def data_table(self, data):
        self.set_font('Arial', '', 10) # Reducir tamaño de fuente
        self.set_text_color(0, 0, 0)
        key_width = 95
        value_width = 95
        
        for i, (key, value) in enumerate(data.items()):
            if i % 2 == 0: self.set_fill_color(255, 255, 255)
            else: self.set_fill_color(248, 249, 250)
            
            self.cell(key_width, 8, f'  {key}', 0, 0, 'L', fill=True) # Reducir altura de celda
            self.cell(value_width, 8, str(value), 0, 1, 'R', fill=True) # Reducir altura de celda
        self.ln(4) # Reducir espacio

    def segmental_table(self, data, headers):
        self.set_font('Arial', 'B', 10) # Reducir tamaño de fuente
        self.set_fill_color(40, 40, 40)
        self.set_text_color(255, 255, 255)
        
        self.cell(64, 8, headers[0], 1, 0, 'C', fill=True) # Reducir altura de celda
        self.cell(63, 8, headers[1], 1, 0, 'C', fill=True) # Reducir altura de celda
        self.cell(63, 8, headers[2], 1, 1, 'C', fill=True) # Reducir altura de celda

        self.set_font('Arial', '', 10) # Reducir tamaño de fuente
        self.set_text_color(0, 0, 0)

        keys = list(data[0].keys())
        for i, row in enumerate(data):
            if i % 2 == 0: self.set_fill_color(255, 255, 255)
            else: self.set_fill_color(248, 249, 250)
            
            self.cell(64, 8, f" {row[keys[0]]}", 1, 0, 'L', fill=True) # Reducir altura de celda
            self.cell(63, 8, f"{row[keys[1]]}", 1, 0, 'C', fill=True) # Reducir altura de celda
            self.cell(63, 8, f"{row[keys[2]]}", 1, 1, 'C', fill=True) # Reducir altura de celda
        self.ln(4) # Reducir espacio
        
    def comparison_table(self, data, dates, title):
        self.section_title(title)
        self.set_font('Arial', 'B', 10) # Reducir tamaño de fuente
        self.set_fill_color(40, 40, 40)
        self.set_text_color(255, 255, 255)
        
        self.cell(60, 8, 'Parámetro', 1, 0, 'C', fill=True) # Reducir altura de celda
        self.cell(40, 8, f"Anterior ({dates['anterior']})", 1, 0, 'C', fill=True) # Reducir altura de celda
        self.cell(40, 8, f"Actual ({dates['actual']})", 1, 0, 'C', fill=True) # Reducir altura de celda
        self.cell(50, 8, 'Diferencia', 1, 1, 'C', fill=True) # Reducir altura de celda

        self.set_font('Arial', '', 10) # Reducir tamaño de fuente
        self.set_text_color(0, 0, 0)
        
        for i, row in enumerate(data):
            if i % 2 == 0: self.set_fill_color(255, 255, 255)
            else: self.set_fill_color(248, 249, 250)
            
            self.cell(60, 8, f" {row['parametro']}", 1, 0, 'L', fill=True) # Reducir altura de celda
            self.cell(40, 8, str(row['anterior']), 1, 0, 'C', fill=True) # Reducir altura de celda
            self.cell(40, 8, str(row['actual']), 1, 0, 'C', fill=True) # Reducir altura de celda
            self.cell(50, 8, row['diferencia'], 1, 1, 'C', fill=True) # Reducir altura de celda
        self.ln(4) # Reducir espacio

@app.route('/paciente/<int:paciente_id>/generar_pdf')
@login_required
@role_required('nutriologo', 'admin')
@db_connection_error_handler
def generar_pdf(paciente_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM pacientes WHERE id = %s", (paciente_id,))
    paciente = cursor.fetchone()
    cursor.execute("SELECT * FROM mediciones WHERE id_paciente = %s ORDER BY fecha_medicion DESC LIMIT 2", (paciente_id,))
    mediciones = cursor.fetchall()

    if not paciente or not mediciones:
        flash('No hay datos suficientes para generar el reporte.', 'danger')
        return redirect(url_for('ver_paciente', paciente_id=paciente_id))
    
    medicion_actual = mediciones[0]
    medicion_anterior = mediciones[1] if len(mediciones) > 1 else None

    def get_val(med, key, unit=''):
        val = med.get(key)
        return f"{val}{unit}" if val is not None else 'N/A'

    pdf = PDF()
    pdf.add_page()

    pdf.section_title('Datos del Paciente')
    datos_paciente = {
        'Nombre Completo': paciente['nombre_completo'],
        'Fecha de Nacimiento': paciente['fecha_nacimiento'].strftime('%d-%m-%Y') if paciente.get('fecha_nacimiento') else 'N/A',
        'Estatura': f"{paciente.get('estatura_cm')} cm" if paciente.get('estatura_cm') else 'N/A'
    }
    pdf.data_table(datos_paciente)

    pdf.section_title(f"Resultados de la Medición ({medicion_actual['fecha_medicion'].strftime('%d-%m-%Y')})")
    datos_medicion = {
        'Peso': get_val(medicion_actual, 'peso', ' kg'),
        'Índice de Masa Corporal (IMC)': get_val(medicion_actual, 'imc'),
        'Porcentaje de Grasa Corporal': get_val(medicion_actual, 'grasa_corporal_pct', '%'),
        'Masa Muscular': get_val(medicion_actual, 'masa_muscular_kg', ' kg'),
        'Porcentaje de Agua Corporal': get_val(medicion_actual, 'agua_corporal_pct', '%'),
        'Masa Ósea': get_val(medicion_actual, 'masa_osea_kg', ' kg'),
        'Nivel de Grasa Visceral': get_val(medicion_actual, 'grasa_visceral'),
        'Metabolismo Basal (BMR)': get_val(medicion_actual, 'bmr_kcal', ' kcal'),
        'Metabolismo Activo (AMR)': get_val(medicion_actual, 'amr_kcal', ' kcal'),
    }
    pdf.data_table(datos_medicion)

    if medicion_anterior:
        dates = {
            'anterior': medicion_anterior['fecha_medicion'].strftime('%d-%m-%y'),
            'actual': medicion_actual['fecha_medicion'].strftime('%d-%m-%y')
        }
        
        segmental_fat_comparison = []
        segmental_muscle_comparison = []
        segments = [
            {'key': 'tronco', 'label': 'Tronco'},
            {'key': 'brazo_der', 'label': 'Brazo Derecho'},
            {'key': 'brazo_izq', 'label': 'Brazo Izquierdo'},
            {'key': 'pierna_der', 'label': 'Pierna Derecha'},
            {'key': 'pierna_izq', 'label': 'Pierna Izquierda'},
        ]
        
        segment_weight_percentages = {
            'tronco': 0.50, 'brazo_der': 0.06, 'brazo_izq': 0.06, 
            'pierna_der': 0.19, 'pierna_izq': 0.19
        }

        for segment in segments:
            ant_weight = float(medicion_anterior.get('peso', 0))
            act_weight = float(medicion_actual.get('peso', 0))
            seg_pct = segment_weight_percentages[segment['key']]

            ant_fat_pct = medicion_anterior.get(f"grasa_{segment['key']}_pct")
            act_fat_pct = medicion_actual.get(f"grasa_{segment['key']}_pct")
            
            if ant_fat_pct is not None and act_fat_pct is not None:
                ant_fat_kg = (ant_weight * seg_pct) * (float(ant_fat_pct) / 100)
                act_fat_kg = (act_weight * seg_pct) * (float(act_fat_pct) / 100)
                diff = act_fat_kg - ant_fat_kg
                segmental_fat_comparison.append({'parametro': segment['label'], 'anterior': f"{ant_fat_kg:.2f} kg", 'actual': f"{act_fat_kg:.2f} kg", 'diferencia': f"{diff:+.2f} kg"})

            ant_muscle_pct = medicion_anterior.get(f"musculo_{segment['key']}_pct")
            act_muscle_pct = medicion_actual.get(f"musculo_{segment['key']}_pct")

            if ant_muscle_pct is not None and act_muscle_pct is not None:
                ant_muscle_kg = (ant_weight * seg_pct) * (float(ant_muscle_pct) / 100)
                act_muscle_kg = (act_weight * seg_pct) * (float(act_muscle_pct) / 100)
                diff = act_muscle_kg - ant_muscle_kg
                segmental_muscle_comparison.append({'parametro': segment['label'], 'anterior': f"{ant_muscle_kg:.2f} kg", 'actual': f"{act_muscle_kg:.2f} kg", 'diferencia': f"{diff:+.2f} kg"})
        
        if segmental_fat_comparison:
            pdf.comparison_table(segmental_fat_comparison, dates, "Comparativa de Grasa Segmental (kg)")
        if segmental_muscle_comparison:
            pdf.comparison_table(segmental_muscle_comparison, dates, "Comparativa de Músculo Segmental (kg)")

    pdf.section_title('Análisis Segmental (Última Medición) - Porcentajes')
    datos_segmental_pct = []
    for segment in segments:
        grasa_pct_val = medicion_actual.get(f"grasa_{segment['key']}_pct")
        musculo_pct_val = medicion_actual.get(f"musculo_{segment['key']}_pct")
        grasa_pct_str = f"{grasa_pct_val:.1f}%" if grasa_pct_val is not None else 'N/A'
        musculo_pct_str = f"{musculo_pct_val:.1f}%" if musculo_pct_val is not None else 'N/A'
        datos_segmental_pct.append({'segmento': segment['label'], 'grasa': grasa_pct_str, 'musculo': musculo_pct_str})
    headers_pct = ['Segmento Corporal', 'Grasa (%)', 'Músculo (%)']
    pdf.segmental_table(datos_segmental_pct, headers_pct)

    pdf.section_title('Análisis Segmental (Última Medición) - Kilogramos')
    datos_segmental_kg = []
    current_weight = float(medicion_actual.get('peso', 0))
    for segment in segments:
        grasa_kg = 'N/A'
        musculo_kg = 'N/A'
        grasa_pct = medicion_actual.get(f"grasa_{segment['key']}_pct")
        musculo_pct = medicion_actual.get(f"musculo_{segment['key']}_pct")
        seg_pct = segment_weight_percentages[segment['key']]

        if grasa_pct is not None:
            grasa_kg = f"{(current_weight * seg_pct) * (float(grasa_pct) / 100):.2f} kg"
        if musculo_pct is not None:
            musculo_kg = f"{(current_weight * seg_pct) * (float(musculo_pct) / 100):.2f} kg"
        datos_segmental_kg.append({'segmento': segment['label'], 'grasa': grasa_kg, 'musculo': musculo_kg})
    headers_kg = ['Segmento Corporal', 'Grasa (kg)', 'Músculo (kg)']
    pdf.segmental_table(datos_segmental_kg, headers_kg)
    
    response = make_response(pdf.output(dest='S').encode('latin-1'))
    response.headers.set('Content-Disposition', 'inline', filename=f'reporte_{paciente["nombre_completo"]}.pdf')
    response.headers.set('Content-Type', 'application/pdf')
    return response

if __name__ == '__main__':
    app.run(debug=True, port=5001)

