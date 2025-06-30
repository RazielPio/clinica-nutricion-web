# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import json

app = Flask(__name__)
# ¡IMPORTANTE! Cambia esto por una frase secreta larga y aleatoria
app.secret_key = 'tu_llave_secreta_muy_segura_aqui_12345' 

# --- CONFIGURACIÓN DE LA BASE DE DATOS ---
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root', 
    'password': '', # La contraseña por defecto de XAMPP es vacía
    'database': 'clinigramm_db'
}

def get_db_connection():
    """Crea y retorna una conexión a la base de datos."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"Error al conectar a MySQL: {e}")
        return None

# --- DECORADORES DE AUTENTICACIÓN Y ROLES ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('user_rol') not in roles:
                flash('No tienes permiso para acceder a esta página.', 'danger')
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- RUTAS PRINCIPALES Y DE LOGIN (LÓGICA CORREGIDA) ---
@app.route('/')
def index():
    if 'user_id' in session:
        rol = session.get('user_rol')
        if rol == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif rol == 'recepcion':
            return redirect(url_for('recepcion_dashboard'))
        elif rol == 'nutriologo':
            return redirect(url_for('pacientes_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        db = get_db_connection()
        if not db:
            flash("Error de conexión con la base de datos.", "danger")
            return render_template('login.html')
            
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        usuario = cursor.fetchone()
        
        if usuario and check_password_hash(usuario['password_hash'], password):
            if usuario['estado'] != 'activo':
                flash('Tu cuenta está inactiva. Contacta al administrador.', 'danger')
                cursor.close()
                db.close()
                return redirect(url_for('login'))

            session.clear()
            session['user_id'] = usuario['id']
            session['user_rol'] = usuario['rol']
            session['user_name'] = usuario['nombre']

            ip_address = request.remote_addr
            cursor.execute("INSERT INTO log_sesiones (id_usuario, fecha_hora, ip_address) VALUES (%s, %s, %s)", (usuario['id'], datetime.now(), ip_address))
            db.commit()
            
            cursor.close()
            db.close()
            
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

# --- RUTAS DE ADMINISTRADOR ---
@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    db = get_db_connection()
    if not db: return "Error de conexión."
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre, email, estado, rol FROM usuarios WHERE rol IN ('nutriologo', 'recepcion')")
    usuarios_gestion = cursor.fetchall()
    cursor.execute("SELECT l.fecha_hora, l.ip_address, u.nombre, u.rol FROM log_sesiones l JOIN usuarios u ON l.id_usuario = u.id ORDER BY l.fecha_hora DESC LIMIT 50")
    logs = cursor.fetchall()
    cursor.close(); db.close()
    return render_template('admin_dashboard.html', usuarios=usuarios_gestion, logs=logs)

@app.route('/admin/update_status/<int:user_id>/<string:new_status>', methods=['POST'])
@login_required
@role_required('admin')
def update_user_status(user_id, new_status):
    if new_status not in ['activo', 'inactivo']: return redirect(url_for('admin_dashboard'))
    db = get_db_connection()
    if not db: return "Error de conexión."
    cursor = db.cursor()
    cursor.execute("UPDATE usuarios SET estado = %s WHERE id = %s", (new_status, user_id))
    db.commit(); cursor.close(); db.close()
    flash('El estado del usuario ha sido actualizado.', 'success')
    return redirect(url_for('admin_dashboard'))

# --- RUTAS DE RECEPCIÓN ---
@app.route('/recepcion/dashboard')
@login_required
@role_required('recepcion')
def recepcion_dashboard():
    db = get_db_connection()
    if not db: return "Error de conexión."
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre FROM usuarios WHERE rol = 'nutriologo' AND estado = 'activo' ORDER BY nombre")
    nutriologos = cursor.fetchall()
    cursor.close(); db.close()
    return render_template('recepcion_dashboard.html', nutriologos=nutriologos)

@app.route('/api/search_patients')
@login_required
@role_required('recepcion', 'admin')
def search_patients():
    query = request.args.get('q', '')
    if len(query) < 2: return jsonify([])
    db = get_db_connection()
    if not db: return jsonify([])
    cursor = db.cursor(dictionary=True)
    sql = "SELECT p.id, p.nombre_completo, u.nombre AS nutriologo_nombre, p.estatura_cm FROM pacientes p LEFT JOIN usuarios u ON p.id_nutriologo_asignado = u.id WHERE p.nombre_completo LIKE %s LIMIT 10"
    cursor.execute(sql, (f"%{query}%",))
    pacientes = cursor.fetchall()
    cursor.close(); db.close()
    return jsonify(pacientes)

@app.route('/recepcion/add_patient', methods=['POST'])
@login_required
@role_required('recepcion')
def add_patient():
    nombre, fecha_nac = request.form['nombre_completo'], request.form.get('fecha_nacimiento') or None
    estatura_cm = request.form.get('estatura_cm') or None
    telefono, email = request.form.get('telefono') or None, request.form.get('email') or None
    id_nutriologo = request.form.get('id_nutriologo_asignado') or None
    db = get_db_connection()
    if not db: return "Error de conexión."
    cursor = db.cursor()
    cursor.execute("INSERT INTO pacientes (nombre_completo, fecha_nacimiento, estatura_cm, telefono, email, id_nutriologo_asignado) VALUES (%s, %s, %s, %s, %s, %s)", 
                   (nombre, fecha_nac, estatura_cm, telefono, email, id_nutriologo))
    db.commit(); cursor.close(); db.close()
    flash('Paciente registrado y asignado exitosamente.', 'success')
    return redirect(url_for('recepcion_dashboard'))

@app.route('/recepcion/add_measurement', methods=['POST'])
@login_required
@role_required('recepcion')
def add_measurement():
    db_data = {}
    def get_float(name):
        try: return float(request.form.get(name))
        except (ValueError, TypeError): return None
    db_data['id_paciente'] = get_float('id_paciente')
    db_data['fecha_medicion'] = datetime.now()
    peso, altura_m = get_float('peso'), get_float('altura')
    imc = None
    if peso and altura_m and altura_m > 0: imc = round(peso / (altura_m * altura_m), 2)
    db_data.update({'peso': peso, 'altura': altura_m, 'imc': imc, 'grasa_corporal_pct': get_float('grasa_corporal_pct'), 'agua_corporal_pct': get_float('agua_corporal_pct'), 'masa_muscular_pct': get_float('masa_muscular_pct'), 'masa_osea_kg': get_float('masa_osea_kg'), 'tmb_kcal': get_float('tmb_kcal'), 'get_kcal': get_float('get_kcal'), 'observaciones': request.form.get('observaciones') or None})
    segmental_pct_form = {'grasa_tronco_pct': get_float('grasa_tronco_pct'), 'musculo_tronco_pct': get_float('musculo_tronco_pct'), 'grasa_brazo_der_pct': get_float('grasa_brazo_der_pct'), 'musculo_brazo_der_pct': get_float('musculo_brazo_der_pct'), 'grasa_brazo_izq_pct': get_float('grasa_brazo_izq_pct'), 'musculo_brazo_izq_pct': get_float('musculo_brazo_izq_pct'), 'grasa_pierna_der_pct': get_float('grasa_pierna_der_pct'), 'musculo_pierna_der_pct': get_float('musculo_pierna_der_pct'), 'grasa_pierna_izq_pct': get_float('grasa_pierna_izq_pct'), 'musculo_pierna_izq_pct': get_float('musculo_pierna_izq_pct')}
    db_data.update(segmental_pct_form)
    if peso:
        masa_muscular_pct_total = db_data.get('masa_muscular_pct')
        db_data['masa_muscular_kg'] = round((masa_muscular_pct_total / 100) * peso, 2) if masa_muscular_pct_total is not None else None
        segment_weight_percentages = {'tronco': 0.46, 'brazo_der': 0.055, 'brazo_izq': 0.055, 'pierna_der': 0.17, 'pierna_izq': 0.17}
        for segment_name, segment_weight_pct in segment_weight_percentages.items():
            estimated_segment_weight = peso * segment_weight_pct
            for comp_type in ['grasa', 'musculo']:
                pct_key, kg_key = f'{comp_type}_{segment_name}_pct', f'{comp_type}_{segment_name}_kg'
                pct_value = segmental_pct_form.get(pct_key)
                db_data[kg_key] = round((pct_value / 100) * estimated_segment_weight, 2) if pct_value is not None else None
    db = get_db_connection()
    if not db: return "Error de conexión."
    cursor = db.cursor()
    columns = ', '.join([f'`{k}`' for k in db_data.keys()])
    placeholders = ', '.join(['%s'] * len(db_data))
    sql = f"INSERT INTO mediciones ({columns}) VALUES ({placeholders})"
    cursor.execute(sql, list(db_data.values()))
    db.commit(); cursor.close(); db.close()
    flash('Medición registrada y calculada exitosamente.', 'success')
    return redirect(url_for('recepcion_dashboard'))

# --- RUTAS DE PACIENTES ---
@app.route('/pacientes')
@login_required
@role_required('nutriologo', 'admin')
def pacientes_dashboard():
    db = get_db_connection(); cursor = db.cursor(dictionary=True)
    sql_query = "SELECT p.*, u.nombre as nutriologo_nombre FROM pacientes p LEFT JOIN usuarios u ON p.id_nutriologo_asignado = u.id"
    params = []
    if session['user_rol'] == 'nutriologo':
        sql_query += " WHERE p.id_nutriologo_asignado = %s OR p.id_nutriologo_asignado IS NULL"
        params.append(session['user_id'])
    sql_query += " ORDER BY p.nombre_completo"
    cursor.execute(sql_query, params)
    pacientes = cursor.fetchall()
    cursor.close(); db.close()
    return render_template('pacientes_dashboard.html', pacientes=pacientes)
    
@app.route('/paciente/<int:paciente_id>')
@login_required
@role_required('nutriologo', 'recepcion', 'admin')
def ver_paciente(paciente_id):
    db = get_db_connection(); cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM pacientes WHERE id = %s", (paciente_id,))
    paciente = cursor.fetchone()
    if not paciente:
        flash("Paciente no encontrado.", "danger"); return redirect(url_for('index'))
    if session['user_rol'] == 'nutriologo' and paciente['id_nutriologo_asignado'] != session['user_id'] and paciente['id_nutriologo_asignado'] is not None:
        flash("No tienes permiso para ver este paciente.", "danger"); return redirect(url_for('pacientes_dashboard'))
    cursor.execute("SELECT * FROM mediciones WHERE id_paciente = %s ORDER BY fecha_medicion ASC", (paciente_id,))
    mediciones_asc = cursor.fetchall()
    cursor.execute("SELECT * FROM historial_clinico WHERE id_paciente = %s", (paciente_id,))
    historial = cursor.fetchone()
    cursor.close(); db.close()
    chart_data = {"labels": [m['fecha_medicion'].strftime('%d-%m-%Y') for m in mediciones_asc], "peso": [float(m['peso']) for m in mediciones_asc if m['peso'] is not None], "grasa": [float(m['grasa_corporal_pct']) for m in mediciones_asc if m['grasa_corporal_pct'] is not None], "musculo": [float(m['masa_muscular_kg']) for m in mediciones_asc if m['masa_muscular_kg'] is not None]}
    mediciones_desc = sorted(mediciones_asc, key=lambda x: x['fecha_medicion'], reverse=True)
    def to_safe_json(data): return json.dumps(data, default=str) if data else json.dumps({})
    return render_template('ver_paciente.html', paciente=paciente, mediciones=mediciones_desc, historial=historial, chart_data=chart_data, paciente_json=to_safe_json(paciente), historial_json=to_safe_json(historial), mediciones_json=to_safe_json(mediciones_desc))

@app.route('/paciente/<int:paciente_id>/historial', methods=['GET', 'POST'])
@login_required
@role_required('nutriologo', 'admin')
def editar_historial_clinico(paciente_id):
    db = get_db_connection(); cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        form_data = { key: (request.form.get(key) or None) for key in request.form.keys() }
        form_data["id_paciente"] = paciente_id
        if 'estatura_cm' in form_data and form_data['estatura_cm']:
            cursor.execute("UPDATE pacientes SET estatura_cm = %s WHERE id = %s", (form_data['estatura_cm'], paciente_id))
            db.commit()
        if 'edad' in form_data:
            cursor.execute("UPDATE historial_clinico SET edad = %s WHERE id_paciente = %s", (form_data.get('edad'), paciente_id))
            db.commit()
        
        # Guardar el resto de los datos del historial
        historial_data = form_data.copy()
        del historial_data['id_paciente']
        if 'estatura_cm' in historial_data: del historial_data['estatura_cm']
        
        cursor.execute("SELECT id FROM historial_clinico WHERE id_paciente = %s", (paciente_id,))
        existe = cursor.fetchone()
        
        if existe:
            fields = ", ".join([f"{key}=%s" for key in historial_data.keys()])
            sql = f"UPDATE historial_clinico SET {fields} WHERE id_paciente=%s"
            params = list(historial_data.values()) + [paciente_id]
        else:
            historial_data["id_paciente"] = paciente_id
            keys = ", ".join(historial_data.keys()); values = ", ".join(['%s'] * len(historial_data)); sql = f"INSERT INTO historial_clinico ({keys}) VALUES ({values})"
            params = list(historial_data.values())
            
        cursor.execute(sql, params)
        db.commit()
        flash('Historial clínico guardado exitosamente.', 'success')
        cursor.close(); db.close()
        return redirect(url_for('ver_paciente', paciente_id=paciente_id))

    cursor.execute("SELECT * FROM pacientes WHERE id = %s", (paciente_id,)); paciente = cursor.fetchone()
    cursor.execute("SELECT * FROM historial_clinico WHERE id_paciente = %s", (paciente_id,)); historial = cursor.fetchone()
    if not historial: historial = {'estatura_cm': paciente.get('estatura_cm')}
    cursor.close(); db.close()
    if not paciente:
        flash("Paciente no encontrado.", "danger"); return redirect(url_for('pacientes_dashboard'))
    return render_template('historial_clinico.html', paciente=paciente, historial=historial)

@app.route('/paciente/<int:paciente_id>/reasignar', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'recepcion')
def reasignar_paciente(paciente_id):
    db = get_db_connection(); cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        nuevo_nutriologo_id = request.form.get('id_nutriologo_asignado') or None
        cursor.execute("UPDATE pacientes SET id_nutriologo_asignado = %s WHERE id = %s", (nuevo_nutriologo_id, paciente_id))
        db.commit()
        flash('Paciente reasignado exitosamente.', 'success')
        cursor.close(); db.close()
        if session.get('user_rol') == 'recepcion': return redirect(url_for('recepcion_dashboard'))
        else: return redirect(url_for('ver_paciente', paciente_id=paciente_id))
    cursor.execute("SELECT p.*, u.nombre as nutriologo_actual FROM pacientes p LEFT JOIN usuarios u ON p.id_nutriologo_asignado = u.id WHERE p.id = %s", (paciente_id,))
    paciente = cursor.fetchone()
    if not paciente:
        flash("Paciente no encontrado.", "danger"); cursor.close(); db.close(); return redirect(url_for('index'))
    cursor.execute("SELECT id, nombre FROM usuarios WHERE rol = 'nutriologo' AND estado = 'activo'")
    nutriologos = cursor.fetchall()
    cursor.close(); db.close()
    return render_template('reasignar_paciente.html', paciente=paciente, nutriologos=nutriologos)

if __name__ == '__main__':
    app.run(debug=True, port=5001)

