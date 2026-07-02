import os
from google import genai
import sqlite3
import math
import time
import threading
from moderacion import es_mensaje_seguro
# 🔧 SE AGREGA 'send_from_directory' PARA SERVIR EL MANIFEST CORRECTAMENTE
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, current_app, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

ruta_actual = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(ruta_actual, "templates"))
app.secret_key = "llave_ultra_secreta_2026"
client = genai.Client()

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

# Toma los valores de Render, y si no existen, usa tus correos actuales por defecto
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'inworkersoporte@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'ofdogcebyoumumsu')
app.config['MAIL_DEFAULT_SENDER'] = ('inWorker Soporte', app.config['MAIL_USERNAME'])
mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# 📸 CONFIGURACIÓN Y VALIDACIÓN DE IMÁGENES PERMITIDAS (Solución al Error 500)
EXTENSIONES_PERMITIDAS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = os.path.join(ruta_actual, 'static', 'uploads')

# Crea la carpeta automáticamente si no existe en el servidor de Render para evitar NameError/FileNotFound
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def archivo_permitido(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in EXTENSIONES_PERMITIDAS

# 🔧 CORRECCIÓN AQUÍ: Recibe el objeto 'app' para no perder el contexto en hilos secundarios
def enviar_bienvenida_tecnico(app_contexto, correo_destino, nombre_usuario):
    with app_contexto.app_context(): # 👈 Esto activa el contexto dentro del hilo
        try:
            msg = Message(
                '¡Bienvenido a inWorker! Transforma tu talento en oportunidades',
                recipients=[correo_destino]
            )
            msg.html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
                <div style="background-color: #0052cc; padding: 20px; text-align: center; color: white;">
                    <h2>¡Hola, {nombre_usuario}! 👋</h2>
                    <p style="font-size: 16px; margin: 0;">Tu registro en inWorker ha sido exitoso</p>
                </div>
                <div style="padding: 20px; color: #333333; line-height: 1.6;">
                    <p>Estamos muy felices de tenerte con nosotros. Desde ahora, eres parte de la plataforma que conecta el mejor talento con las mejores oportunidades en Colombia.</p>
                    <p>Ya puedes ingresar a tu panel, completar tu perfil con tus habilidades y empezar a recibir ofertas de trabajo en tu zona de inmediato.</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="https://inworker.co/" style="background-color: #0052cc; color: white; padding: 12px 25px; text-align: center; text-decoration: none; font-weight: bold; border-radius: 5px;">Ingresar a mi Cuenta</a>
                    </div>
                    <p style="font-size: 12px; color: #777777;">Si tienes alguna duda o inconveniente, responde a este correo y nuestro equipo de soporte te atenderá de inmediato.</p>
                </div>
                <div style="background-color: #f9f9f9; padding: 15px; text-align: center; font-size: 12px; color: #999999; border-top: 1px solid #e0e0e0;">
                    © 2026 inWorker. Todos los derechos reservados.
                </div>
            </div>
            """
            mail.send(msg)
            print(f"📧 Correo enviado con éxito en segundo plano a: {correo_destino}")
        except Exception as e:
            print(f"❌ Error real en el envío del correo por SMTP: {e}")

ruta_db = os.path.join(ruta_actual, "inworker_prod.db")
# 💰 NUEVO PRECIO DEL CRÉDITO NACIONAL
VALOR_CREDITO_COP = 10000.0  

def construir_base_datos():
    conexion = sqlite3.connect(ruta_db)
    cursor = conexion.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            nombre TEXT NOT NULL, 
            cedula TEXT UNIQUE NOT NULL, 
            correo TEXT UNIQUE NOT NULL, 
            contrasena TEXT NOT NULL, 
            rol TEXT NOT NULL, 
            profesion TEXT DEFAULT 'Técnico General', 
            habilidades TEXT DEFAULT 'Sin especificar', 
            foto TEXT, 
            telefono TEXT DEFAULT 'Sin especificar',
            verificado INTEGER DEFAULT 0,
            saldo_creditos REAL DEFAULT 0.0, -- 🛑 NUEVOS USUARIOS INICIAN EN 0 Cr
            puntuacion_total REAL DEFAULT 0.0,
            total_calificaciones INTEGER DEFAULT 0,
            descripcion TEXT DEFAULT ''
        )
    ''')
    
    columnas_usuarios = [
        ("telefono", "TEXT DEFAULT 'Sin especificar'"),
        ("verificado", "INTEGER DEFAULT 0"),
        ("puntuacion_total", "REAL DEFAULT 0.0"),
        ("total_calificaciones", "INTEGER DEFAULT 0"),
        ("saldo_creditos", "REAL DEFAULT 10.0"),
        ("descripcion", "TEXT DEFAULT ''") 
    ]
    
    for col, definicion in columnas_usuarios:
        try: 
            cursor.execute(f"ALTER TABLE usuarios ADD COLUMN {col} {definicion}")
        except sqlite3.OperationalError: 
            pass
        
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            titulo TEXT NOT NULL, 
            descripcion TEXT NOT NULL, 
            pago TEXT NOT NULL, 
            categoria TEXT NOT NULL, 
            estado TEXT DEFAULT 'Disponible', 
            cliente_correo TEXT, 
            trabajador_nombre TEXT, 
            trabajador_correo TEXT, 
            costo_creditos REAL DEFAULT 1.0, 
            latitud REAL DEFAULT 10.9639, 
            longitud REAL DEFAULT -74.7964,
            confirmacion_cliente INTEGER DEFAULT 0,
            confirmacion_trabajador INTEGER DEFAULT 0,
            calificada INTEGER DEFAULT 0,
            zona TEXT DEFAULT 'Barranquilla (Norte)'
        )
    ''')
    try: cursor.execute("ALTER TABLE tareas ADD COLUMN calificada INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE tareas ADD COLUMN zona TEXT DEFAULT 'Barranquilla (Norte)'")
    except sqlite3.OperationalError: pass
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mensajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            tarea_id INTEGER, 
            canal_trabajador TEXT, 
            remitente_correo TEXT, 
            mensaje TEXT, 
            tipo TEXT DEFAULT 'texto', 
            leido INTEGER DEFAULT 0,
            fecha_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try: cursor.execute("ALTER TABLE mensajes ADD COLUMN leido INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portafolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_correo TEXT NOT NULL,
            imagen_ruta TEXT NOT NULL,
            descripcion TEXT,
            tipo TEXT DEFAULT 'Trabajo Realizado',
            fecha_subida TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS billetera_retiros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_correo TEXT NOT NULL,
            monto_creditos REAL NOT NULL,
            equivalente_pesos REAL NOT NULL,
            metodo_pago TEXT NOT NULL,
            detalles_cuenta TEXT NOT NULL,
            estado TEXT DEFAULT 'Pendiente',
            fecha_solicitud TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try: cursor.execute("ALTER TABLE billetera_retiros ADD COLUMN estado TEXT DEFAULT 'Pendiente'")
    except sqlite3.OperationalError: pass
    
    cursor.execute('''
        INSERT OR IGNORE INTO usuarios (nombre, cedula, correo, contrasena, rol, profesion, telefono, verificado, saldo_creditos) 
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, 999.0)
    ''', ('baraka', '99999999', 'baraka@inworker.com', 'baraka123', 'Admin', 'Administrador Principal', '3000000000'))
    
    conexion.commit()
    conexion.close()

construir_base_datos()

# =========================================================================
# ENDPOINT API PARA POLLEO ASÍNCRONO DE NOTIFICACIONES GLOBALES
# =========================================================================
@app.route('/api/notificaciones/globales', methods=['GET'])
def api_notificaciones_globales():
    if 'usuario_correo' not in session:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
        
    correo_logueado = session['usuario_correo']
    rol_logueado = session.get('usuario_rol')
    
    conexion = sqlite3.connect(ruta_db)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    
    if rol_logueado == 'Cliente':
        cursor.execute("""
            SELECT COUNT(*) as total 
            FROM mensajes m
            JOIN tareas t ON m.tarea_id = t.id
            WHERE t.cliente_correo = ? AND m.remitente_correo != ? AND m.leido = 0
        """, (correo_logueado, correo_logueado))
    elif rol_logueado == 'Trabajador':
        cursor.execute("""
            SELECT COUNT(*) as total 
            FROM mensajes m
            JOIN tareas t ON m.tarea_id = t.id
            WHERE (t.trabajador_correo = ? OR m.canal_trabajador = 'sala_' || t.id) 
              AND m.remitente_correo != ? AND m.leido = 0
        """, (correo_logueado, correo_logueado))
    else:
        cursor.execute("SELECT 0 as total")
        
    mensajes_sin_leer = cursor.fetchone()['total'] or 0
    
    cursor.execute("""
        SELECT id, titulo, estado, zona 
        FROM tareas 
        WHERE (cliente_correo = ? OR trabajador_correo = ?) AND estado IN ('En Garantia', 'Finalizada')
    """, (correo_logueado, correo_logueado))
    tareas_alertas = [dict(row) for row in cursor.fetchall()]
    
    conexion.close()
    
    return jsonify({
        'success': True,
        'mensajes_sin_leer': mensajes_sin_leer,
        'alertas_estados': tareas_alertas
    })
# =====================================================================
# 💬 SISTEMA DE ALERTAS EN TIEMPO REAL (Llamado cada 7 segundos) - ¡CORREGIDO!
# =====================================================================
@app.route('/verificar_alertas')
def verificar_alertas():
    # Si no hay sesión activa, respondemos con cero de inmediato
    if 'usuario_correo' not in session:
        return jsonify({"total_mensajes": 0})
        
    correo_usuario = session['usuario_correo']
    rol_logueado = session.get('usuario_rol')
    conexion = None
    
    try:
        conexion = sqlite3.connect(ruta_db)
        cursor = conexion.cursor()
        
        # Consultamos dinámicamente según el rol para evitar la columna inexistente 'receptor_correo'
        if rol_logueado == 'Cliente':
            cursor.execute("""
                SELECT COUNT(*) FROM mensajes m
                JOIN tareas t ON m.tarea_id = t.id
                WHERE t.cliente_correo = ? AND m.remitente_correo != ? AND m.leido = 0
            """, (correo_usuario, correo_usuario))
            
        elif rol_logueado == 'Trabajador':
            cursor.execute("""
                SELECT COUNT(*) FROM mensajes m
                JOIN tareas t ON m.tarea_id = t.id
                WHERE (t.trabajador_correo = ? OR m.canal_trabajador = 'sala_' || t.id) 
                  AND m.remitente_correo != ? AND m.leido = 0
            """, (correo_usuario, correo_usuario))
        else:
            return jsonify({"total_mensajes": 0})
        
        total_sin_leer = cursor.fetchone()[0]
        return jsonify({"total_mensajes": total_sin_leer})
        
    except Exception as e:
        print(f"⚠️ Error al verificar alertas en tiempo real: {e}")
        return jsonify({"total_mensajes": 0})
    finally:
        if conexion:
            conexion.close()

# =========================================================================
# ⚙️ NUEVO: INTERCEPTOR REQUERIDO PARA SISTEMA PWA (PROCESAMIENTO MANIFEST)
# =========================================================================
@app.route('/static/manifest.json')
def servir_manifest_pwa():
    return send_from_directory(os.path.join(ruta_actual, 'static'), 'manifest.json', mimetype='application/json')
# =========================================================================


# --- MÓDULO DE VISTAS ESTÁTICAS Y LEGALES ---
@app.route('/terminos-y-condiciones')
def terminos_condiciones():
    return render_template('terminos.html')

# =====================================================================
# 🌐 1. LA RAÍZ AHORA RENDERIZA TU LANDING PAGE COMERCIAL
# =====================================================================
@app.route('/')
def index(): 
    # Si el usuario ya está logueado, lo mandamos directo al Dashboard (home)
    if 'usuario_correo' in session:
        return redirect(url_for('home'))
    
    # Si es un visitante nuevo, le vendemos la visión con la Landing Page comercial
    return render_template('landing.html')


# =====================================================================
# 🔑 2. MÓDULO DE AUTENTICACIÓN CENTRALIZADO (Maneja GET y POST)
# =====================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conexion = sqlite3.connect(ruta_db)
        conexion.row_factory = sqlite3.Row # Mantiene tu estructura de acceso por llave
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE correo = ? AND contrasena = ?", (request.form['correo'], request.form['contrasena']))
        usuario = cursor.fetchone()
        conexion.close()
        
        if usuario:
            session['usuario_nombre'] = usuario['nombre']
            session['usuario_rol'] = usuario['rol']
            session['usuario_correo'] = usuario['correo']
            return redirect(url_for('home'))
        
        flash("❌ Credenciales incorrectas.", "error")
        return redirect(url_for('login')) # Redirige de nuevo a la pantalla de login si falla
        
    # Si entran por GET (es decir, haciendo clic en "Ingresar al Panel" desde la landing)
    return render_template('login.html')


# =====================================================================
# 📝 3. PROCESAMIENTO DE REGISTROS (Únicamente vía POST)
# =====================================================================
@app.route('/registrar', methods=['POST'])
def registrar():
    acepta_terminos = request.form.get('acepta_terminos')
    if not acepta_terminos:
        flash("❌ Es obligatorio aceptar los Términos y Condiciones para registrarse.", "error")
        return redirect(url_for('login', action='registro')) # Redirige a la pestaña de registro en login.html

    conexion = None
    try:
        conexion = sqlite3.connect(ruta_db, timeout=30)
        conexion.row_factory = sqlite3.Row
        cursor = conexion.cursor()
        
        telefono_form = request.form.get('telefono', 'Sin especificar')
        nombre = request.form['nombre']
        cedula = request.form['cedula']
        correo = request.form['correo']
        contrasena = request.form['contrasena']
        rol = request.form['rol']

        # 1. VALIDAR SI EL CORREO YA EXISTE
        cursor.execute("SELECT id FROM usuarios WHERE correo = ?", (correo,))
        if cursor.fetchone():
            flash("❌ Error: Este correo electrónico ya está registrado.", "error")
            return redirect(url_for('login', action='registro'))

        # 2. VALIDAR SI LA CÉDULA YA EXISTE
        cursor.execute("SELECT id FROM usuarios WHERE cedula = ?", (cedula,))
        if cursor.fetchone():
            flash("❌ Error: Esta cédula ya se encuentra registrada en el sistema.", "error")
            return redirect(url_for('login', action='registro'))

        # 3. SI TODO ESTÁ BIEN, SE INSERTA
        cursor.execute("""
            INSERT INTO usuarios (nombre, cedula, correo, contrasena, rol, telefono, verificado, saldo_creditos) 
            VALUES (?, ?, ?, ?, ?, ?, 0, 0.0)
        """, (nombre, cedula, correo, contrasena, rol, telefono_form))
        
        conexion.commit()
        
        # Envío de correo en segundo plano
        try:
            from flask import current_app
            app_real = current_app._get_current_object()
            
            hilo_correo = threading.Thread(
                target=enviar_bienvenida_tecnico, 
                args=(app_real, correo, nombre) 
            )
            hilo_correo.daemon = True  
            hilo_correo.start()
            print(f"🧵 Hilo creado con contexto unificado para enviar correo a: {correo}")
        except Exception as e_hilo:
            print(f"⚠️ No se pudo iniciar el hilo del correo: {e_hilo}")
        
        # 4. ACTIVAR LA SESIÓN Y REDIRIGIR AL HOME (Dashboard)
        session['usuario_nombre'] = nombre
        session['usuario_rol'] = rol
        session['usuario_correo'] = correo
        return redirect(url_for('home'))

    except Exception as e:
        print(f"⚠️ Error crítico en el registro: {e}")
        flash("❌ Ocurrió un error interno. Por favor, inténtalo de nuevo.", "error")
        return redirect(url_for('login', action='registro'))
        
    finally:
        if conexion:
            conexion.close()
# =====================================================================
# 🛡️ GESTIÓN DE ADMINISTRACIÓN: VERIFICAR Y PAUSAR ESPECIALISTAS
# =====================================================================

@app.route('/admin/verificar_usuario/<int:usuario_id>', methods=['POST'])
def admin_verificar_usuario(usuario_id):
    if 'usuario_nombre' not in session:
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
        
    conexion = None
    try:
        conexion = sqlite3.connect(ruta_db)
        cursor = conexion.cursor()
        
        # Cambiamos el estado de 'verificado' a 1
        cursor.execute("UPDATE usuarios SET verificado = 1 WHERE id = ?", (usuario_id,))
        conexion.commit()
        
        flash("✅ ¡Especialista verificado con éxito en el sistema nacional!", "success")
        return jsonify({'success': True})
    except Exception as e:
        print(f"⚠️ Error al verificar usuario {usuario_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conexion:
            conexion.close()

@app.route('/admin/pausar_usuario/<int:usuario_id>', methods=['POST'])
def admin_pausar_usuario(usuario_id):
    if 'usuario_nombre' not in session:
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
        
    conexion = None
    try:
        conexion = sqlite3.connect(ruta_db)
        cursor = conexion.cursor()
        
        # Para pausar, desverificamos al usuario (verificado = 0)
        # Nota: Si en el futuro agregas una columna 'estado', aquí la actualizarías
        cursor.execute("UPDATE usuarios SET verificado = 0 WHERE id = ?", (usuario_id,))
        conexion.commit()
        
        flash("⏸️ Perfil del especialista pausado correctamente.", "success")
        return jsonify({'success': True})
    except Exception as e:
        print(f"⚠️ Error al pausar usuario {usuario_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conexion:
            conexion.close()

# =====================================================================
# MÓDULO DE RECUPERACIÓN DE CONTRASEÑA
# =====================================================================

@app.route('/recuperar-contrasena', methods=['GET', 'POST'])
def recuperar_contrasena():
    if request.method == 'POST':
        correo = request.form['correo']
        
        conexion = sqlite3.connect(ruta_db)
        conexion.row_factory = sqlite3.Row
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE correo = ?", (correo,))
        usuario = cursor.fetchone()
        conexion.close()
        
        if usuario:
            # Generar un token único basado en el correo del usuario
            token = serializer.dumps(correo, salt='recuperar-claves-inworker')
            link_recuperacion = f"https://inworker.co" + url_for('restablecer_clave', token=token)
            
            # Enviar el correo con el enlace seguro
            try:
                msg = Message(
                    'Restablecer tu contraseña - inWorker',
                    recipients=[correo]
                )
                msg.html = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
                    <div style="background-color: #0052cc; padding: 20px; text-align: center; color: white;">
                        <h2>¿Olvidaste tu contraseña? 🔑</h2>
                    </div>
                    <div style="padding: 20px; color: #333333; line-height: 1.6;">
                        <p>Hola, <strong>{usuario['nombre']}</strong>.</p>
                        <p>Recibimos una solicitud para restablecer la contraseña de tu cuenta en inWorker. Para continuar, haz clic en el siguiente botón:</p>
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{link_recuperacion}" style="background-color: #0052cc; color: white; padding: 12px 25px; text-align: center; text-decoration: none; font-weight: bold; border-radius: 5px;">Restablecer Contraseña</a>
                        </div>
                        <p style="font-size: 12px; color: #777777;">Este enlace es seguro y vencerá en 1 hora. Si no solicitaste este cambio, puedes ignorar este correo con total tranquilidad.</p>
                    </div>
                </div>
                """
                mail.send(msg)
                flash("📧 Te hemos enviado un enlace de recuperación a tu correo electrónico.", "success")
            except Exception as e:
                flash(f"⚠️ Error al enviar el correo: {str(e)}", "error")
        else:
            # Por seguridad, es mejor decir que se envió si el formato es correcto, 
            # pero aquí te pongo el aviso real para tus pruebas locales:
            flash("❌ El correo ingresado no está registrado en inWorker.", "error")
            
        return redirect(url_for('index'))
        
    return render_template('recuperar.html')


@app.route('/restablecer-clave/<token>', methods=['GET', 'POST'])
def restablecer_clave(token):
    try:
        # El token expira automáticamente en 3600 segundos (1 hora)
        correo = serializer.loads(token, salt='recuperar-claves-inworker', max_age=3600)
    except SignatureExpired:
        flash("❌ El enlace de recuperación ha expirado. Por favor, solicita uno nuevo.", "error")
        return redirect(url_for('index'))
    except BadSignature:
        flash("❌ Enlace de recuperación inválido o alterado.", "error")
        return redirect(url_for('index'))

    if request.method == 'POST':
        nueva_clave = request.form['contrasena']
        
        # Actualizar la clave en la base de datos
        conexion = sqlite3.connect(ruta_db)
        cursor = conexion.cursor()
        cursor.execute("UPDATE usuarios SET contrasena = ? WHERE correo = ?", (nueva_clave, correo))
        conexion.commit()
        conexion.close()
        
        flash("✅ ¡Tu contraseña ha sido actualizada con éxito! Ya puedes iniciar sesión.", "success")
        return redirect(url_for('index'))
        
    return render_template('restablecer.html', token=token)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard', methods=['GET', 'POST'])
def home():
    # 🛡️ PROTECCIÓN AMIGABLE: Validamos usando el correo (más seguro que el nombre)
    if 'usuario_correo' not in session: 
        flash("🔒 Por favor, inicia sesión para acceder al panel.", "error")
        return redirect(url_for('login')) # 👈 Si no está logueado, lo mandamos al LOGIN, no a la landing
        
    correo_logueado = session.get('usuario_correo')
    conexion = sqlite3.connect(ruta_db)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    
    
    if request.method == 'POST' and request.form.get('accion_perfil') == 'solicitar_retiro':
        try:
            creditos_retiro = float(request.form.get('creditos_retiro', 0))
        except ValueError:
            creditos_retiro = 0.0
            
        metodo = request.form.get('metodo_pago', 'No especificado')
        detalles = request.form.get('detalles_cuenta', '')
        
        cursor.execute("SELECT IFNULL(saldo_creditos, 0.0) as saldo FROM usuarios WHERE correo = ?", (correo_logueado,))
        usuario_db = cursor.fetchone()
        saldo_actual = usuario_db['saldo'] if usuario_db else 0.0
        
        if creditos_retiro > 0 and creditos_retiro <= saldo_actual:
            equivalente_cop = creditos_retiro * VALOR_CREDITO_COP
            nuevo_saldo = round(saldo_actual - creditos_retiro, 2)
            
            # 1. Descontamos el saldo al usuario
            cursor.execute("UPDATE usuarios SET saldo_creditos = ? WHERE correo = ?", (nuevo_saldo, correo_logueado))
            
            # 2. Guardamos el retiro incluyendo la columna obligatoria equivalente_pesos
            cursor.execute("""
                INSERT INTO billetera_retiros (usuario_correo, monto_creditos, equivalente_pesos, metodo_pago, detalles_cuenta, estado)
                VALUES (?, ?, ?, ?, ?, 'Pendiente')
            """, (correo_logueado, creditos_retiro, equivalente_cop, metodo, detalles))
            
            conexion.commit()
            flash(f"✅ Solicitud por ${equivalente_cop:,.0f} COP enviada a revisión técnica.", "success")
        else:
            flash("❌ Fondos insuficientes o cantidad de créditos inválida.", "error")
    
    cursor.execute("SELECT COUNT(*) as total FROM usuarios WHERE rol = 'Trabajador'")
    total_workers = cursor.fetchone()['total'] or 0
    
    cursor.execute("SELECT COUNT(*) as total FROM tareas WHERE estado IN ('Cotización Pendiente', 'En Garantia')")
    ordenes_mediacion = cursor.fetchone()['total'] or 0
    
    cursor.execute("SELECT SUM(CAST(pago AS REAL)) as total_escrow FROM tareas WHERE estado = 'En Garantia'")
    fondos_escrow = cursor.fetchone()['total_escrow'] or 0
    
    cursor.execute("SELECT IFNULL(saldo_creditos, 0.0) as saldo FROM usuarios WHERE correo = ?", (correo_logueado,))
    usuario_db = cursor.fetchone() 
    saldo_usuario = round(usuario_db['saldo'], 2) if usuario_db else 0.0
    
    conexion.close()
    
    # =========================================================================
    # 💰 INYECCIÓN BLINDADA DE 10 CRÉDITOS DE PRUEBA ($100.000 COP)
    # =========================================================================
    saldo_test = 10.00  
    
    # Armamos diccionarios falsos por si tus layouts de HTML buscan datos del perfil
    perfil_falso = {'saldo_creditos': saldo_test, 'saldo': saldo_test}
    # =========================================================================
    
    return render_template('index.html', 
                           nombre_usuario=session['usuario_nombre'],
                           total_workers=total_workers,
                           ordenes_mediacion=ordenes_mediacion,
                           fondos_escrow=fondos_escrow,
                           saldo=saldo_test,                 # 👈 Inyectado fijo
                           saldo_usuario=saldo_test,         # 👈 Inyectado fijo
                           cliente_perfil=perfil_falso,       # 👈 Evita NameErrors
                           trabajador_perfil=perfil_falso)   # 👈 Evita NameErrors

@app.route('/api/optimizar_perfil', methods=['POST'])
def api_optimizar_perfil():
    if 'usuario_correo' not in session:
        return jsonify({'error': 'No autorizado'}), 401
        
    data = request.get_json()
    profesion = data.get('profesion', 'Especialista')
    habilidades_actuales = data.get('habilidades', '')
    
    # 🕵️‍♂️ ESTO NOS MOSTRARÁ EN LOS LOGS DE RENDER QUÉ LLEGA REALMENTE
    print(f"--- NUEVA PETICIÓN DE IA ---")
    print(f"Profesión recibida: {profesion}")
    print(f"Habilidades recibidas: {habilidades_actuales}")
    
    prompt = f"""
    Eres un expert en marca profesional para la plataforma inWorker.
    Tu tarea es redactar una descripción de perfil impecable, atractiva y muy vendedora basada estrictamente en los datos del trabajador.
    
    INFORMACIÓN REAL DEL USUARIO:
    - Oficio seleccionado: {profesion}
    - Habilidades y Experiencia ingresadas: {habilidades_actuales}
    
    REQUISITOS DEL TEXTO:
    1. Dale prioridad absoluta a TODAS las habilidades y tecnologías que el usuario mencionó. No dejes por fuera detalles importantes.
    2. El texto debe ser fluido, redactado con un tono profesional, serio y confiable.
    3. Permite que la extensión se adapte de forma natural para cubrir bien la experiencia del usuario, estructurando un extracto profesional sólido.
    4. Devuelve ÚNICAMENTE el texto sugerido final. No agregues introducciones, saludos, notas ni comillas.
    """
    
    try:
        # 🚀 Cambiamos el string al modelo más moderno y estable del nuevo SDK
        response = client.models.generate_content(
            model='gemini-2.5-flash',  # <-- Cambiado de 1.5-flash a 2.5-flash
            contents=prompt,
        )
        texto_optimizado = response.text.strip()
        
        print(f"✅ Respuesta exitosa del nuevo Gemini: {texto_optimizado}")
        return jsonify({'sugerencia': texto_optimizado})
        
    except Exception as e:
        print(f"❌ ERROR REAL EN NUEVO SDK DE GEMINI: {e}")
        # El respaldo amigable por si la API falla
        respaldo = f"Especialista en {profesion} comprometido con la excelencia operativa, puntualidad y soluciones eficientes en inWorker."
        return jsonify({'sugerencia': respaldo})

# --- RUTAS DEL ADMINISTRADOR MÓDULOS CORE ---
@app.route('/admin/validar_tecnicos')
def admin_validar_tecnicos():
    if 'usuario_nombre' not in session or session.get('usuario_rol') != 'Admin':
        return redirect(url_for('index'))
    
    conexion = sqlite3.connect(ruta_db)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE rol = 'Trabajador'")
    tecnicos_pendientes = [dict(row) for row in cursor.fetchall()]
    conexion.close()
    
    return render_template('trabajadores.html', usuarios=tecnicos_pendientes, nombre_usuario=session['usuario_nombre'])

@app.route('/admin/modulo_cedulas', methods=['GET', 'POST'])
def admin_modulo_cedulas():
    if 'usuario_nombre' not in session or session.get('usuario_rol') != 'Admin':
        return redirect(url_for('index'))
    
    resultado_busqueda = None
    if request.method == 'POST':
        cedula_buscar = request.form.get('cedula', '').strip()
        conexion = sqlite3.connect(ruta_db)
        conexion.row_factory = sqlite3.Row
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE cedula = ?", (cedula_buscar,))
        row = cursor.fetchone()
        if row:
            resultado_busqueda = dict(row)
        conexion.close()
        flash(f"Búsqueda ejecutada para la cédula: {cedula_buscar}", "success")
    
    return render_template('cedula.html', resultado=resultado_busqueda, nombre_usuario=session['usuario_nombre'])

@app.route('/admin/reportes')
def admin_reportes():
    if 'usuario_nombre' not in session or session.get('usuario_rol') != 'Admin':
        return redirect(url_for('index'))
        
    conexion = sqlite3.connect(ruta_db)
    cursor = conexion.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM tareas")
    total_tareas = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(equivalente_pesos) FROM billetera_retiros WHERE estado = 'Aprobado'")
    volumen_cop = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'Trabajador'")
    total_workers = cursor.fetchone()[0] or 0
    
    conexion.close()
    
    return render_template('reportes.html', 
                           total_tareas=total_tareas, 
                           volumen_cop=volumen_cop, 
                           total_workers=total_workers, 
                           nombre_usuario=session['usuario_nombre'])

# --- MÓDULO ADMINISTRATIVO DE GESTIÓN DE RETIROS (COBROS) ---
@app.route('/admin/retiros', methods=['GET', 'POST'])
def admin_retiros():
    if 'usuario_nombre' not in session or session.get('usuario_rol') != 'Admin':
        return redirect(url_for('index'))
        
    conexion = sqlite3.connect(ruta_db)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    
    if request.method == 'POST':
        # Captura el id_retiro tal cual como viene desde el formulario HTML
        solicitud_id = request.form.get('id_retiro')
        accion = request.form.get('accion')
        
        cursor.execute("SELECT * FROM billetera_retiros WHERE id = ?", (solicitud_id,))
        solicitud = cursor.fetchone()
        
        if solicitud and solicitud['estado'] == 'Pendiente':
            if accion == 'Completado':  # Coincide con el valor enviado por el botón "Marcar Pagado"
                cursor.execute("UPDATE billetera_retiros SET estado = 'Aprobado' WHERE id = ?", (solicitud_id,))
                flash(f"✅ Retiro #{solicitud_id} aprobado para transferencia manual.", "success")
            elif accion == 'Rechazado':  # Coincide con el valor enviado por el botón "Rechazar"
                cursor.execute("SELECT saldo_creditos FROM usuarios WHERE correo = ?", (solicitud['usuario_correo'],))
                res_user = cursor.fetchone()
                user_saldo = res_user['saldo_creditos'] if res_user else 0.0
                nuevo_saldo = round(user_saldo + solicitud['monto_creditos'], 2)
                
                cursor.execute("UPDATE usuarios SET saldo_creditos = ? WHERE correo = ?", (nuevo_saldo, solicitud['usuario_correo']))
                cursor.execute("UPDATE billetera_retiros SET estado = 'Rechazado' WHERE id = ?", (solicitud_id,))
                flash(f"❌ Retiro #{solicitud_id} rechazado. Créditos reintegrados al trabajador.", "error")
            conexion.commit()

    # Traemos las solicitudes pendientes mapeando el nombre esperado por el HTML
    cursor.execute("""
        SELECT r.id,
               r.monto_creditos,
               r.equivalente_pesos,
               r.metodo_pago,
               r.detalles_cuenta,
               r.estado,
               r.usuario_correo,
               COALESCE(u.nombre, r.usuario_correo) as nombre,
               COALESCE(u.cedula, 'Sin verificar') as trabajador_cedula
        FROM billetera_retiros r
        LEFT JOIN usuarios u ON LOWER(TRIM(r.usuario_correo)) = LOWER(TRIM(u.correo))
        WHERE r.estado = 'Pendiente'
        ORDER BY r.id DESC
    """)
    lista_retiros = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT COUNT(*) as total FROM usuarios WHERE rol = 'Trabajador'")
    total_workers = cursor.fetchone()['total'] or 0
    
    cursor.execute("SELECT COUNT(*) as total FROM tareas WHERE estado IN ('Cotización Pendiente', 'En Garantia')")
    ordenes_mediacion = cursor.fetchone()['total'] or 0
    
    cursor.execute("SELECT SUM(CAST(pago AS REAL)) as total_escrow FROM tareas WHERE estado = 'En Garantia'")
    fondos_escrow = cursor.fetchone()['total_escrow'] or 0
    
    conexion.close()
    
    # IMPORTANTE: Le pasamos 'solicitudes=lista_retiros' para que el HTML lo lea correctamente
    return render_template('admin_retiros.html', 
                           solicitudes=lista_retiros, 
                           nombre_usuario=session['usuario_nombre'],
                           total_workers=total_workers, 
                           ordenes_mediacion=ordenes_mediacion, 
                           fondos_escrow=fondos_escrow)

@app.route('/recargar_billetera', methods=['GET', 'POST'])
def recargar_billetera():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        # Simulamos que seleccionó un paquete (Ej: $30.000 COP = 1 Crédito)
        creditos_a_cargar = float(request.form.get('creditos', 1))
        usuario_id = session['usuario_id']
        
        # Conexión limpia a tu base de datos para sumarle los créditos comprados
        import sqlite3
        conexion = sqlite3.connect(ruta_db)
        cursor = conexion.cursor()
        
        # Actualizamos el saldo del usuario sumándole lo nuevo
        cursor.execute("UPDATE usuarios SET saldo = saldo + ? WHERE id = ?", (creditos_a_cargar, usuario_id))
        conexion.commit()
        conexion.close()
        
        # Actualizamos el saldo en la sesión para que se refleje inmediatamente
        session['saldo'] = session.get('saldo', 0) + creditos_a_cargar
        
        flash("¡Recarga simulada con éxito! Fondos agregados a tu billetera inWorker.", "success")
        return redirect(request.referrer or url_for('dashboard'))
        
    # Si entra por GET, le renderizamos una interfaz sencilla de selección de paquetes
    return render_template('recargar.html', saldo=session.get('saldo', 0))

            # --- CONTROL DEL TABLÓN DE ÓRDENES ---
@app.route('/tareas')
def ver_tareas():
    if 'usuario_nombre' not in session: 
        return redirect(url_for('index'))
    
    user_lat = request.args.get('lat', type=float)
    user_lng = request.args.get('lng', type=float)
    
    conexion = sqlite3.connect(ruta_db)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    
    cursor.execute("SELECT IFNULL(saldo_creditos, 0.0) as saldo_creditos FROM usuarios WHERE correo = ?", (session['usuario_correo'],))
    usuario_db = cursor.fetchone()
    saldo_actual = round(usuario_db['saldo_creditos'], 2) if usuario_db else 0.0
    
    cursor.execute("SELECT * FROM tareas")
    tareas_db = cursor.fetchall()
    conexion.close()
    
    lista_tareas = [dict(t) for t in tareas_db]
    t_distancia = False
    
    if user_lat and user_lng:
        t_distancia = True
        for t in lista_tareas:
            t_lat = t['latitud'] if t['latitud'] is not None else 10.9639
            t_lng = t['longitud'] if t['longitud'] is not None else -74.7964
            t['distancia'] = round(calcular_distancia(user_lat, user_lng, t_lat, t_lng), 1)
        lista_tareas.sort(key=lambda x: x.get('distancia', 9999))
        
    # =========================================================================
    # 💰 INYECCIÓN BLINDADA DE 10 CRÉDITOS DE PRUEBA ($100.000 COP)
    # =========================================================================
    saldo_test = 10.00  
    perfil_falso = {'saldo_creditos': saldo_test, 'saldo': saldo_test}
    # =========================================================================
        
    return render_template('tareas.html', 
                           tareas=lista_tareas, 
                           nombre_usuario=session['usuario_nombre'], 
                           saldo=saldo_test,                 # 👈 Cambiado para inyectar fijos los 10 créditos
                           saldo_usuario=saldo_test,         # 👈 Agregado por si acaso
                           cliente_perfil=perfil_falso,       # 👈 Blindaje contra NameErrors
                           trabajador_perfil=perfil_falso,   # 👈 Blindaje contra NameErrors
                           user_lat=user_lat, 
                           user_lng=user_lng,
                           t_distancia=t_distancia)

@app.route('/publicar_tarea', methods=['GET', 'POST'])
@app.route('/tareas/crear', methods=['GET', 'POST'])
def publicar_tarea():
    if 'usuario_nombre' not in session: 
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        lat = request.form.get('latitud', 10.9639)
        lng = request.form.get('longitud', -74.7964)
        zona = request.form.get('zona', 'Barranquilla (Norte)')
        pago_cop = request.form['pago']
        
        tecnico_invitado = request.form.get('tecnico_invitado', '')
        estado_inicial = 'Cotización Pendiente' if tecnico_invitado else 'Disponible'
        
        try: 
            creditos_calculados = round(float(pago_cop) / VALOR_CREDITO_COP, 2)
        except: 
            creditos_calculados = 1.0
        
        conexion = sqlite3.connect(ruta_db)
        cursor = conexion.cursor()
        
        # ==========================================================
        # 🔥 ULTRA-MEDIDA DE EMERGENCIA: ALTERACIÓN EN VIVO 🔥
        # ==========================================================
        # Obligamos a la base de datos actual a tener la columna pase lo que pase
        try:
            cursor.execute("ALTER TABLE tareas ADD COLUMN tecnico_correo TEXT;")
            conexion.commit()
        except sqlite3.OperationalError:
            pass # Si ya existe la columna, ignora el error de forma segura
        # ==========================================================
        
        cursor.execute("""
            INSERT INTO tareas (titulo, descripcion, pago, categoria, estado, costo_creditos, cliente_correo, latitud, longitud, zona, tecnico_correo) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form['titulo'], 
            request.form['descripcion'], 
            pago_cop, 
            request.form['categoria'], 
            estado_inicial, 
            creditos_calculados, 
            session['usuario_correo'], 
            lat, 
            lng, 
            zona,
            tecnico_invitado if tecnico_invitado else None
        ))
        
        id_tarea = cursor.lastrowid
        conexion.commit()
        conexion.close()
        
        # Limpieza de seguridad
        session.pop('invitar_tecnico_correo', None)
        
        if tecnico_invitado and id_tarea:
            return redirect(f'/chat/{id_tarea}')
            
        return redirect(url_for('ver_tareas'))        
    
    # ⬇️ AQUÍ ESTABA EL GRAN ERROR EN EL FLUJO 'GET' ⬇️
    invitar_correo = request.args.get('invitar', '')
    if invitar_correo:
        session['invitar_tecnico_correo'] = invitar_correo
        return redirect(url_for('ver_tareas', abrir_publicar='true'))
    
    # Si entran por GET y no van a invitar a nadie, renderizamos la página en vez de no devolver nada
    return render_template('tareas.html') # 👈 Asegúrate de que el nombre coincida con tu plantilla (ej: tareas.html o tarea.html)
    return redirect(url_for('ver_tareas'))
@app.route('/perfil', methods=['GET', 'POST'])
def ver_perfil():
    if 'usuario_nombre' not in session: 
        return redirect(url_for('index'))
        
    # Forzamos limpieza en el correo logueado para evitar fallos de coincidencia
    correo_logueado = session['usuario_correo'].strip().lower()
    
    if request.method == 'POST':
        conexion = None
        try:
            conexion = sqlite3.connect(ruta_db, timeout=30)
            cursor = conexion.cursor()
            accion_perfil = request.form.get('accion_perfil')
            
            if accion_perfil == 'actualizar_datos':
                telefono = request.form.get('telefono', 'Sin especificar')
                profesion = request.form.get('profesion', 'Técnico General')
                habilidades = request.form.get('habilidades', 'Sin especificar')
                descripcion = request.form.get('descripcion', '')
                
                # 1. PROCESAR FOTO DE AVATAR PRINCIPAL
                archivo_foto = request.files.get('foto_perfil')
                if archivo_foto and archivo_foto.filename != '' and archivo_permitido(archivo_foto.filename):
                    nombre_foto = f"avatar_{int(time.time())}_{secure_filename(archivo_foto.filename)}"
                    archivo_foto.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_foto))
                    
                    cursor.execute("""
                        UPDATE usuarios 
                        SET telefono = ?, profesion = ?, habilidades = ?, foto = ?, descripcion = ? 
                        WHERE LOWER(TRIM(correo)) = ?
                    """, (telefono, profesion, habilidades, nombre_foto, descripcion, correo_logueado))
                else:
                    cursor.execute("""
                        UPDATE usuarios 
                        SET telefono = ?, profesion = ?, habilidades = ?, descripcion = ?
                        WHERE LOWER(TRIM(correo)) = ?
                    """, (telefono, profesion, habilidades, descripcion, correo_logueado))
                
                # 2. PROCESAR CARGA MÚLTIPLE DEL PORTAFOLIO
                imagenes_portafolio = request.files.getlist('trabajos_previos')
                proyectos_guardados = 0
                
                for file in imagenes_portafolio:
                    if file and file.filename != '' and archivo_permitido(file.filename):
                        nombre_p = f"portafolio_{int(time.time())}_{secure_filename(file.filename)}"
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_p))
                        
                        # Insertamos en la tabla auxiliar portafolio
                        cursor.execute("""
                            INSERT INTO portafolio (usuario_correo, imagen_ruta, descripcion, tipo)
                            VALUES (?, ?, ?, ?)
                        """, (correo_logueado, nombre_p, "Trabajo Realizado", "Trabajo Anterior"))
                        proyectos_guardados += 1

                conexion.commit()
                
                if proyectos_guardados > 0:
                    flash(f"✨ ¡Perfil actualizado y {proyectos_guardados} fotos añadidas al portafolio!", "success")
                else:
                    flash("✨ ¡Perfil actualizado correctamente!", "success")
                
            elif accion_perfil == 'solicitar_retiro':
                try:
                    creditos_retiro = float(request.form.get('creditos_retiro', 0))
                except ValueError:
                    creditos_retiro = 0.0
                    
                metodo = request.form.get('metodo_pago', 'No especificado')
                detalles = request.form.get('detalles_cuenta', '')
                
                conexion.row_factory = sqlite3.Row
                cursor_saldo = conexion.cursor()
                cursor_saldo.execute("SELECT IFNULL(saldo_creditos, 0.0) as saldo FROM usuarios WHERE LOWER(TRIM(correo)) = ?", (correo_logueado,))
                res_u = cursor_saldo.fetchone()
                saldo_actual = res_u['saldo'] if res_u else 0.0
                
                if creditos_retiro > 0 and creditos_retiro <= saldo_actual:
                    equivalente_cop = creditos_retiro * VALOR_CREDITO_COP
                    nuevo_saldo = round(saldo_actual - creditos_retiro, 2)
                    
                    cursor.execute("UPDATE usuarios SET saldo_creditos = ? WHERE LOWER(TRIM(correo)) = ?", (nuevo_saldo, correo_logueado))
                    cursor.execute("""
                        INSERT INTO billetera_retiros (usuario_correo, monto_creditos, equivalente_pesos, metodo_pago, detalles_cuenta, estado)
                        VALUES (?, ?, ?, ?, ?, 'Pendiente')
                    """, (correo_logueado, creditos_retiro, equivalente_cop, metodo, detalles))
                    
                    conexion.commit()
                    flash(f"💵 Solicitud por ${equivalente_cop:,.0f} COP enviada a revisión técnica.", "success")
                else:
                    flash("❌ Saldo insuficiente o cantidad de créditos inválida.", "error")
                    
        except Exception as e:
            print(f"⚠️ ERROR CRÍTICO EN POST PERFIL: {e}")
            flash("❌ Ocurrió un error al guardar los cambios en la base de datos.", "error")
        finally:
            if conexion:
                conexion.close()
                
        return redirect(url_for('ver_perfil'))

    # =====================================================================
    # MÉTODO GET: RENDERIZAR VISTA NORMAL DEL PERFIL
    # =====================================================================
    conexion = sqlite3.connect(ruta_db)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    
    # 💰 Ajuste nacional comercial: El fallback por defecto de nuevos usuarios es 0.0 créditos
    cursor.execute("""
        SELECT nombre, cedula, correo, rol, profesion, habilidades, foto, telefono, verificado, descripcion,
               IFNULL(puntuacion_total, 0.0) as puntuacion_total, 
               IFNULL(total_calificaciones, 0) as total_calificaciones, 
               IFNULL(saldo_creditos, 0.0) as saldo_creditos 
        FROM usuarios 
        WHERE LOWER(TRIM(correo)) = ?
    """, (correo_logueado,))
    usuario_db = cursor.fetchone()
    
    if not usuario_db:
        conexion.close()
        flash("❌ El perfil solicitado no se encuentra registrado.", "error")
        return redirect(url_for('home'))
        
    usuario = dict(usuario_db)
    usuario['saldo_creditos'] = round(usuario['saldo_creditos'], 2)
    
    if usuario['total_calificaciones'] > 0:
        usuario['promedio_estrellas'] = round(usuario['puntuacion_total'] / usuario['total_calificaciones'], 1)
    else:
        usuario['promedio_estrellas'] = 0.0

    cursor.execute("""
        SELECT id, imagen_ruta, descripcion, tipo, fecha_subida 
        FROM portafolio 
        WHERE LOWER(TRIM(usuario_correo)) = ? 
        ORDER BY id DESC
    """, (correo_logueado,))
    proyectos = [dict(p) for p in cursor.fetchall()]
    
    cursor.execute("""
        SELECT id, monto_creditos, equivalente_pesos, metodo_pago, detalles_cuenta, estado, fecha_solicitud
        FROM billetera_retiros
        WHERE LOWER(TRIM(usuario_correo)) = ?
        ORDER BY id DESC
    """, (correo_logueado,))
    retiros = [dict(r) for r in cursor.fetchall()]
    
    conexion.close()
    
    return render_template('perfil.html', 
                           usuario=usuario, 
                           proyectos=proyectos, 
                           retiros=retiros,
                           saldo=usuario['saldo_creditos'],
                           nombre_usuario=session['usuario_nombre'])


# --- MÓDULO DE COMUNICACIÓN API HTTP (PROCESAMIENTO ASÍNCRONO) ---
@app.route('/chat/<int:tarea_id>', methods=['GET', 'POST'])
def ver_chat(tarea_id):
    if 'usuario_nombre' not in session:
        return redirect(url_for('index'))

    correo_logueado = session['usuario_correo']
    rol_logueado = session.get('usuario_rol')

    conexion = sqlite3.connect(ruta_db)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()

    cursor.execute("SELECT * FROM tareas WHERE id = ?", (tarea_id,))
    tarea = cursor.fetchone()

    if not tarea:
        conexion.close()
        flash("❌ La orden de servicio no existe.", "error")
        return redirect(url_for('ver_tareas'))

    canal_sala = f"sala_{tarea_id}"        

    if rol_logueado == 'Trabajador' and tarea['estado'] == 'Disponible':
        cursor.execute("UPDATE tareas SET estado = 'Cotización Pendiente' WHERE id = ?", (tarea_id,))
        conexion.commit()
        cursor.execute("SELECT * FROM tareas WHERE id = ?", (tarea_id,))
        tarea = cursor.fetchone()
        
    if tarea['estado'] == 'Finalizada' or canal_sala != "Ninguno":
        cursor.execute("UPDATE mensajes SET leido = 1 WHERE tarea_id = ? AND canal_trabajador = ? AND remitente_correo != ?", (tarea_id, canal_sala, correo_logueado))
        conexion.commit()
    
    if request.method == 'POST':
        mensaje_texto = request.form.get('mensaje')
        archivo = request.files.get('imagen_adjunta')
        
        if canal_sala == "Ninguno":
            flash("❌ Sala de negociación no inicializada.", "error")
            return redirect(url_for('ver_chat', tarea_id=tarea_id))

        # 🛡️ FILTRO INTELIGENTE DE MODERACIÓN DE TEXTO
        mensaje_final = mensaje_texto
        es_seguro = True
        
        # Solo se activa el filtro si la tarea NO está pagada y si viene texto en el mensaje
        if tarea['estado'] not in ['En Garantia', 'Finalizada'] and mensaje_texto:
            es_seguro, resultado_moderacion = es_mensaje_seguro(mensaje_texto)
            if not es_seguro:
                mensaje_final = resultado_moderacion  # Reemplaza el texto por la advertencia

        nombre_unico = None
        tipo_mensaje = 'texto'
        
        if archivo and archivo_permitido(archivo.filename):
            nombre_unico = f"chat_{tarea_id}_{int(time.time())}_{secure_filename(archivo.filename)}"
            ruta_guardado = os.path.join(app.config['UPLOAD_FOLDER'], nombre_unico)
            tipo_mensaje = 'imagen'
            
            try:
                img = Image.open(archivo)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                ancho_max = 800
                if img.width > ancho_max:
                    alto_proporcional = int((ancho_max / float(img.width)) * float(img.height))
                    img = img.resize((ancho_max, alto_proporcional), Image.Resampling.LANCZOS)
                
                img.save(ruta_guardado, optimize=True, quality=85)
            except Exception as e:
                archivo.seek(0)
                archivo.save(ruta_guardado)
                
            cursor.execute("""
                INSERT INTO mensajes (tarea_id, canal_trabajador, remitente_correo, mensaje, tipo, leido) 
                VALUES (?, ?, ?, ?, 'imagen', 0)
            """, (tarea_id, canal_sala, correo_logueado, nombre_unico))
            
        elif mensaje_texto and mensaje_texto.strip():
            # Si el mensaje infringe las normas, se marca como leído (1) de inmediato para evitar bucles de notificación
            leido_status = 0 if es_seguro else 1
            
            cursor.execute("""
                INSERT INTO mensajes (tarea_id, canal_trabajador, remitente_correo, mensaje, tipo, leido) 
                VALUES (?, ?, ?, ?, 'texto', ?)
            """, (tarea_id, canal_sala, correo_logueado, mensaje_final.strip(), leido_status))
            
        conexion.commit()
        
        # Sincronizamos los créditos en sesión por si acaso cambiaron en el POST antes de responder por AJAX
        cursor.execute("SELECT IFNULL(saldo_creditos, 0.0) as saldo_creditos FROM usuarios WHERE correo = ?", (correo_logueado,))
        usuario_db = cursor.fetchone()
        if usuario_db:
            session['usuario_creditos'] = round(usuario_db['saldo_creditos'], 2)

        conexion.close()

        # Respuesta para peticiones asíncronas AJAX cuando el mensaje es bloqueado
        if not es_seguro and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': mensaje_final}), 400

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'multipart/form-data' in request.content_type:
            return jsonify({
                'success': True, 
                'remitente_correo': correo_logueado,
                'remitente_nombre': session['usuario_nombre'],
                'mensaje': mensaje_final.strip() if tipo_mensaje == 'texto' else nombre_unico,
                'tipo': tipo_mensaje
            })

        return redirect(url_for('ver_chat', tarea_id=tarea_id))

    # --- MÉTODO GET (Muestra la pantalla del chat) ---
    cursor.execute("""
        SELECT m.id, m.tarea_id, m.canal_trabajador, m.remitente_correo, m.mensaje, m.tipo, m.fecha_envio, 
               IFNULL(u.nombre, 'Usuario de inWorker') as remitente 
        FROM mensajes m 
        LEFT JOIN usuarios u ON m.remitente_correo = u.correo 
        WHERE m.tarea_id = ? AND m.canal_trabajador = ? 
        ORDER BY m.id ASC
    """, (tarea_id, canal_sala))
    mensajes_raw = cursor.fetchall()
    
    mensajes = []
    for msg in mensajes_raw:
        item = dict(msg)
        if 'cotizacion' in item['tipo']:
            partes = item['mensaje'].split('|')
            item['cotizacion_pesos'] = partes[0] if len(partes) > 0 else "0"
            item['cotizacion_concepto'] = partes[1] if len(partes) > 1 else "Sin concepto"
            try: item['cotizacion_creditos'] = round(float(item['cotizacion_pesos']) / VALOR_CREDITO_COP, 2)
            except: item['cotizacion_creditos'] = 0.0
        mensajes.append(item)
    
    cursor.execute("SELECT nombre, correo, profesion, habilidades, cedula, telefono, verificado FROM usuarios WHERE correo = ?", (tarea['cliente_correo'],))
    datos_cliente = cursor.fetchone()
    
    tecnico_identificado = tarea['trabajador_correo'] if tarea['trabajador_correo'] else canal_sala
    
    datos_trabajador = None
    if tecnico_identificado and tecnico_identificado != "Ninguno":
        cursor.execute("""
            SELECT nombre, correo, profesion, habilidades, cedula, telefono, verificado, 
                   IFNULL(puntuacion_total, 0.0) as puntuacion_total, 
                   IFNULL(total_calificaciones, 0) as total_calificaciones 
            FROM usuarios WHERE correo = ?
        """, (tecnico_identificado,))
        trabajador_raw = cursor.fetchone()
        if trabajador_raw:
            trabajador_dict = dict(trabajador_raw)
            if trabajador_dict.get('total_calificaciones', 0) > 0:
                trabajador_dict['promedio_estrellas'] = round(trabajador_dict['puntuacion_total'] / trabajador_dict['total_calificaciones'], 1)
            else:
                trabajador_dict['promedio_estrellas'] = 0.0
            datos_trabajador = trabajador_dict
    
    # 🪙 CONSULTA REAL Y SINCRONIZACIÓN DE BILLETERA
    cursor.execute("SELECT IFNULL(saldo_creditos, 0.0) as saldo_creditos FROM usuarios WHERE correo = ?", (correo_logueado,))
    usuario_db = cursor.fetchone()
    saldo_actual = round(usuario_db['saldo_creditos'], 2) if usuario_db else 0.0
    
    # Mantenemos actualizada la cookie de sesión para evitar desfases en otras páginas
    session['usuario_creditos'] = saldo_actual
    
    conexion.close()
    
    return render_template('chat.html',
                           tarea=tarea,
                           mensajes=mensajes,
                           canal_actual=canal_sala,
                           canal_sala=tarea['cliente_correo'],
                           nombre_usuario=session['usuario_nombre'],
                           saldo=saldo_actual,
                           cliente_perfil=datos_cliente,
                           trabajador_perfil=datos_trabajador)

@app.route('/chat/<int:tarea_id>/enviar_cotizacion', methods=['POST'])
def enviar_cotizacion(tarea_id):
    if 'usuario_nombre' not in session or session.get('usuario_rol') != 'Trabajador':
        return redirect(url_for('index'))
        
    correo_logueado = session['usuario_correo']
    canal_sala = request.form.get('canal_actual')
    monto_pesos = request.form.get('monto_pesos', type=float)
    concepto = request.form.get('concepto', '').strip()
    
    if not monto_pesos or monto_pesos <= 0 or not concepto:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Datos de cotización inválidos'}), 400
        flash("❌ Ingresa un valor en pesos válido y la descripción del servicio.", "error")
        return redirect(url_for('ver_chat', tarea_id=tarea_id))
        
    contenido_cotizacion = f"{monto_pesos}|{concepto}"
    
    conexion = sqlite3.connect(ruta_db)
    cursor = conexion.cursor()
    cursor.execute("""
        INSERT INTO mensajes (tarea_id, canal_trabajador, remitente_correo, mensaje, tipo, leido) 
        VALUES (?, ?, ?, ?, 'cotizacion_pendiente', 0)
    """, (tarea_id, canal_sala, correo_logueado, contenido_cotizacion))
    
    cursor.execute("UPDATE tareas SET estado = 'Cotización Pendiente' WHERE id = ?", (tarea_id,))
    conexion.commit()
    conexion.close()
    
    flash(f"💼 ¡Oferta de ${monto_pesos:,.0f} COP enviada exitosamente!", "success")
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'multipart/form-data' in request.content_type:
        return jsonify({'success': True})

    return redirect(url_for('ver_chat', tarea_id=tarea_id))

# --- ENDPOINT API: CARGA Y NOTIFICACIÓN DE MENSAJES NUEVOS ---
@app.route('/api/chat/<int:tarea_id>/<string:canal>', methods=['GET'])
def api_cargar_mensajes(tarea_id, canal):
    if 'usuario_correo' not in session:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401

    # Capturamos el ultimo_id que nos envía el JavaScript dinámico (?ultimo_id=X)
    ultimo_id = request.args.get('ultimo_id', default=0, type=int)

    try:
        conexion = sqlite3.connect(ruta_db)
        conexion.row_factory = sqlite3.Row
        cursor = conexion.cursor()

        # Agregamos "AND id > ?" a la consulta para que solo busque los mensajes nuevos
        cursor.execute("""
            SELECT id, remitente_correo, canal_trabajador, mensaje, tipo, fecha_envio 
            FROM mensajes 
            WHERE tarea_id = ? AND canal_trabajador = ? AND id > ?
            ORDER BY id ASC
        """, (tarea_id, canal, ultimo_id))
        
        filas = cursor.fetchall()
        mensajes_completos = []
        
        for fila in filas:
            msg_dict = dict(fila)
            msg_dict['remitente'] = msg_dict['remitente_correo'].split('@')[0]
            
            if msg_dict['tipo'] in ['cotizacion_pendiente', 'cotizacion_aceptada', 'cotizacion_declinada']:
                partes = msg_dict['mensaje'].split('|')
                msg_dict['monto_pesos'] = partes[0] if len(partes) > 0 else "0"
                msg_dict['cotizacion_concepto'] = partes[1] if len(partes) > 1 else ""
                try:
                    msg_dict['cotizacion_creditos'] = round(float(msg_dict['monto_pesos']) / 30000, 2)
                except:
                    msg_dict['cotizacion_creditos'] = 0

            mensajes_completos.append(msg_dict)

        conexion.close()
        
        # Si no hay mensajes nuevos, devolverá la lista vacía [] de inmediato ahorrando CPU y RAM
        return jsonify({'success': True, 'mensajes': mensajes_completos})

    except Exception as e:
        print(f"❌ Error en API Chat: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/chat/<int:tarea_id>/responder_cotizacion/<int:mensaje_id>', methods=['POST'])
def responder_cotizacion(tarea_id, mensaje_id):
    if 'usuario_nombre' not in session:
        return redirect(url_for('index'))
        
    correo_logueado = session['usuario_correo']
    accion = request.form.get('accion')
    canal_sala = request.form.get('canal_actual')
    
    conexion = sqlite3.connect(ruta_db)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    
    cursor.execute("SELECT * FROM mensajes WHERE id = ? AND tarea_id = ?", (mensaje_id, tarea_id))
    msg_cotizacion = cursor.fetchone()
    
    if not msg_cotizacion or msg_cotizacion['tipo'] != 'cotizacion_pendiente':
        conexion.close()
        flash("❌ La oferta ya no se encuentra disponible.", "error")
        return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=canal_sala))
        
    try:
        partes = msg_cotizacion['mensaje'].split('|')
        monto_pesos = float(partes[0])
        monto_creditos_flotante = round(monto_pesos / VALOR_CREDITO_COP, 2)
    except Exception:
        conexion.close()
        flash("❌ Formato económico incorrecto.", "error")
        return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=canal_sala))

    if accion == 'Aceptar':
        cursor.execute("SELECT saldo_creditos FROM usuarios WHERE correo = ?", (correo_logueado,))
        res_cliente = cursor.fetchone()
        saldo_cliente = res_cliente['saldo_creditos'] if res_cliente else 0.0
        
        if saldo_cliente < monto_creditos_flotante:
            conexion.close()
            flash(f"❌ Saldo insuficiente en créditos. Necesitas {monto_creditos_flotante} Cr (${monto_pesos:,.0f} COP).", "error")
            return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=canal_sala))
            
        nuevo_saldo_cliente = round(saldo_cliente - monto_creditos_flotante, 2)
        cursor.execute("UPDATE usuarios SET saldo_creditos = ? WHERE correo = ?", (nuevo_saldo_cliente, correo_logueado))
        
        cursor.execute("SELECT nombre FROM usuarios WHERE correo = ?", (msg_cotizacion['remitente_correo'],))
        res_trabajador = cursor.fetchone()
        nombre_trabajador = res_trabajador['nombre'] if res_trabajador else "Técnico inWorker"
        
        cursor.execute("""
            UPDATE tareas 
            SET estado = 'En Garantia', 
                trabajador_correo = ?, 
                trabajador_nombre = ?, 
                pago = ?, 
                costo_creditos = ?,
                confirmacion_cliente = 0,
                confirmacion_trabajador = 0
            WHERE id = ?
        """, (msg_cotizacion['remitente_correo'], nombre_trabajador, str(monto_pesos), monto_creditos_flotante, tarea_id))
        
        cursor.execute("UPDATE mensajes SET tipo = 'cotizacion_aceptada' WHERE id = ?", (mensaje_id,))
        cursor.execute("UPDATE mensajes SET tipo = 'cotizacion_declinada' WHERE tarea_id = ? AND tipo = 'cotizacion_pendiente'", (tarea_id,))
        
        conexion.commit()
        flash("✔ ¡Propuesta aceptada! El depósito de garantía se encuentra congelado de manera segura.", "success")

    elif accion == 'Rechazar':
        cursor.execute("UPDATE mensajes SET tipo = 'cotizacion_declinada' WHERE id = ?", (mensaje_id,))
        conexion.commit()
        flash("❌ Oferta declinada correctamente.", "error")
        
    conexion.close()
    return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=canal_sala))


# --- MÓDULO DE ESCROW: CONFIRMACIÓN Y DESEMBOLSO ---
@app.route('/confirmar_entrega/<int:tarea_id>', methods=['POST'])
def confirmar_entrega(tarea_id):
    if 'usuario_nombre' not in session:
        return redirect(url_for('index'))
        
    correo_logueado = session['usuario_correo']
    
    conexion = sqlite3.connect(ruta_db)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    
    cursor.execute("SELECT * FROM tareas WHERE id = ?", (tarea_id,))
    tarea = cursor.fetchone()
    
    if not tarea or tarea['estado'] != 'En Garantia':
        conexion.close()
        flash("❌ Operación no válida para el estado actual de la tarea.", "error")
        return redirect(url_for('ver_chat', tarea_id=tarea_id))
        
    if correo_logueado == tarea['cliente_correo']:
        cursor.execute("UPDATE tareas SET confirmacion_cliente = 1 WHERE id = ?", (tarea_id,))
        flash("🚀 Has confirmado la conformidad del servicio.", "success")
    elif correo_logueado == tarea['trabajador_correo']:
        cursor.execute("UPDATE tareas SET confirmacion_trabajador = 1 WHERE id = ?", (tarea_id,))
        flash("📢 Has notificado al cliente que el trabajo está finalizado.", "success")
    else:
        conexion.close()
        return redirect(url_for('ver_chat', tarea_id=tarea_id))
        
    conexion.commit()
    
    cursor.execute("SELECT * FROM tareas WHERE id = ?", (tarea_id,))
    tarea_actualizada = cursor.fetchone()
    
    if tarea_actualizada['confirmacion_cliente'] == 1 and tarea_actualizada['confirmacion_trabajador'] == 1:
        creditos_desembolso = tarea_actualizada['costo_creditos']
        tecnico_destino = tarea_actualizada['trabajador_correo']
        
        cursor.execute("SELECT saldo_creditos FROM usuarios WHERE correo = ?", (tecnico_destino,))
        res_tecnico = cursor.fetchone()
        saldo_tecnico = res_tecnico['saldo_creditos'] if res_tecnico else 0.0
        
        nuevo_saldo_tecnico = round(saldo_tecnico + creditos_desembolso, 2)
        cursor.execute("UPDATE usuarios SET saldo_creditos = ? WHERE correo = ?", (nuevo_saldo_tecnico, tecnico_destino))
        cursor.execute("UPDATE tareas SET estado = 'Finalizada' WHERE id = ?", (tarea_id,))
        
        mensaje_sistema = f"SISTEMA: El pago de {creditos_desembolso} Cr (${float(tarea_actualizada['pago']):,.0f} COP) ha sido liberado de la garantía y transferido al saldo de {tarea_actualizada['trabajador_nombre']}."
        cursor.execute("""
            INSERT INTO mensajes (tarea_id, canal_trabajador, remitente_correo, mensaje, tipo, leido)
            VALUES (?, ?, 'baraka@inworker.com', ?, 'texto', 0)
        """, (tarea_id, tarea_actualizada['trabajador_correo'], mensaje_sistema))
        
        conexion.commit()
        flash("✨ ¡Garantía liberada con éxito! Los fondos ya están en la billetera del especialista.", "success")
        
    conexion.close()
    return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=tarea['trabajador_correo']))


# --- MÓDULO DE REPUTACIÓN Y CALIFICACIÓN ---
@app.route('/calificar/<int:tarea_id>', methods=['POST'])
def calificar_tecnico(tarea_id):
    if 'usuario_nombre' not in session:
        return redirect(url_for('index'))
        
    estrellas = request.form.get('estrellas', type=float)
    if not estrellas or estrellas < 1 or estrellas > 5:
        flash("❌ Calificación inválida.", "error")
        return redirect(url_for('ver_chat', tarea_id=tarea_id))
        
    conexion = sqlite3.connect(ruta_db)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    
    cursor.execute("SELECT * FROM tareas WHERE id = ?", (tarea_id,))
    tarea = cursor.fetchone()
    
    if tarea and tarea['estado'] == 'Finalizada' and tarea['calificada'] == 0 and session['usuario_correo'] == tarea['cliente_correo']:
        cursor.execute("""
            UPDATE usuarios 
            SET puntuacion_total = puntuacion_total + ?, 
                total_calificaciones = total_calificaciones + 1 
            WHERE correo = ?
        """, (estrellas, tarea['trabajador_correo']))
        
        cursor.execute("UPDATE tareas SET calificada = 1 WHERE id = ?", (tarea_id,))
        conexion.commit()
        flash("⭐ ¡Gracias por calificar al especialista!", "success")
        
    conexion.close()
    return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=tarea['trabajador_correo'] if tarea else None))

@app.route('/tecnicos')
def listar_tecnicos():
    if 'usuario_nombre' not in session: 
        return redirect(url_for('index'))
        
    conexion = sqlite3.connect(ruta_db)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    
    # 1. Traemos los datos principales del técnico desde la tabla usuarios
    cursor.execute("""
        SELECT nombre, correo, rol, profesion, habilidades, foto, descripcion 
        FROM usuarios 
        WHERE rol = 'Trabajador'
    """)
    tecnicos_raw = cursor.fetchall()
    
    tecnicos = []
    for tec in tecnicos_raw:
        item = dict(tec)
        
        # Biografía de respaldo si el campo está vacío
        item['descripcion'] = item.get('descripcion') or 'Especialista verificado dispuesto a ayudarte en tus requerimientos de soporte técnico.'
        
        # 2. PROCESO CLAVE: Buscamos los proyectos de este usuario específico en la tabla portafolio
        cursor_proyectos = conexion.cursor()
        cursor_proyectos.execute("""
            SELECT id, imagen_ruta, descripcion, tipo 
            FROM portafolio 
            WHERE usuario_correo = ? 
            ORDER BY id DESC
        """, (item['correo'],))
        
        # Guardamos los proyectos encontrados en una lista dentro del mismo objeto técnico
        item['proyectos'] = [dict(p) for p in cursor_proyectos.fetchall()]
        
        # Variables por defecto para calificaciones estables
        item['promedio_estrellas'] = 5.0
        item['total_calificaciones'] = 1
        tecnicos.append(item)
        
    conexion.close()
    return render_template('tecnicos.html', tecnicos=tecnicos, nombre_usuario=session['usuario_nombre'])


# =====================================================================
# 🚀 RUTA PROPIA PARA LA CONSULTA PRIVADA (CORREGIDA ERROR 500)
# =====================================================================
@app.route('/solicitar_cotizacion_privada', methods=['POST'])
def consultar_tecnico():
    if 'usuario_nombre' not in session:
        return redirect(url_for('index'))

    cliente = session['usuario_correo']
    
    # .get() evita que la app se estrelle si el HTML no envía el campo
    tecnico_correo = request.form.get('tecnico_correo') or request.form.get('trabajador_correo')
    titulo = request.form.get('titulo', 'Consulta Privada')
    descripcion = request.form.get('descripcion', 'Sin descripción')
    pago_estimado = request.form.get('pago', '0')
    categoria = request.form.get('categoria', 'Soporte Técnico')
    
    # Si de verdad no llegó ningún correo, tiramos un aviso controlado en vez de un error 500
    if not tecnico_correo:
        flash("❌ Error: No se pudo identificar al técnico para la cotización.", "error")
        return redirect(url_for('listar_tecnicos'))
    
    # Coordenadas por defecto o las que capture tu front
    lat = request.form.get('latitud', 10.9639)
    lng = request.form.get('longitud', -74.7964)
    zona = request.form.get('zona', 'Barranquilla (Privado)')
    
    try: 
        creditos_calculados = round(float(pago_estimado) / VALOR_CREDITO_COP, 2)
    except: 
        creditos_calculados = 1.0

    conexion = sqlite3.connect(ruta_db)
    cursor = conexion.cursor()
    
    # Asegurar que la columna existe por si acaso
    try:
        cursor.execute("ALTER TABLE tareas ADD COLUMN tecnico_correo TEXT;")
        conexion.commit()
    except sqlite3.OperationalError:
        pass

    # Insertamos la tarea bloqueada de una vez para ese técnico
    cursor.execute("""
        INSERT INTO tareas (titulo, descripcion, pago, categoria, estado, costo_creditos, cliente_correo, latitud, longitud, zona, tecnico_correo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        titulo, 
        descripcion, 
        pago_estimado, 
        categoria, 
        'Cotización Pendiente', 
        creditos_calculados, 
        cliente, 
        lat, 
        lng, 
        zona, 
        tecnico_correo
    ))
    
    id_tarea = cursor.lastrowid
    conexion.commit()
    conexion.close()
    
    # Redirección automática y directa al chat privado de negociación
    return redirect(f'/chat/{id_tarea}')


# =====================================================================
# 💰 INYECTADO: RUTA WEBHOOK DIRECTO DE NEQUI Y REVERSIÓN DE COSTOS
# =====================================================================
@app.route('/webhook-nequi', methods=['POST'])
def webhook_nequi():
    datos_pago = request.json
    id_servicio = datos_pago.get("id_servicio")
    estado_pago = datos_pago.get("estado") # Espera "APPROVED" o "DECLINED"
    
    if estado_pago == "APPROVED":
        print(f"💰 ¡Pago aprobado para el servicio {id_servicio}! Tu 7.5% está asegurado.")
        
        # Aquí puedes ejecutar la función para enviar el correo al técnico
        # Ejemplo: alertar_nuevo_servicio_tecnico("correo@tecnico.com", "Carlos", "Mantenimiento", "Soledad")
        
        return jsonify({"status": "success", "message": "Servicio activado e inyectado correctamente"}), 200
        
    return jsonify({"status": "failed", "message": "Pago rechazado o pendiente"}), 200

# =====================================================================
# ⚖️ ENDPOINT DE ARBITRAJE DE DISPUTAS CON IA (FASE 1.1)
# =====================================================================
@app.route('/admin/disputa/<int:tarea_id>')
def analizar_disputa_admin(tarea_id):
    # (Opcional) Aquí podrías validar si el usuario en sesión es administrador
    if 'usuario_nombre' not in session:
        return redirect(url_for('index'))
        
    conexion = sqlite3.connect(ruta_db)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    
    # 1. Traer los datos de la tarea
    cursor.execute("SELECT * FROM tareas WHERE id = ?", (tarea_id,))
    tarea = cursor.fetchone()
    
    if not tarea:
        conexion.close()
        return jsonify({"error": "La tarea no existe"}), 404
        
    # 2. Traer el historial de mensajes del chat de esa tarea
    cursor.execute("""
        SELECT remitente_correo, mensaje, fecha_envio 
        FROM mensajes 
        WHERE tarea_id = ? 
        ORDER BY id ASC
    """, (tarea_id,))
    mensajes = [dict(row) for row in cursor.fetchall()]
    conexion.close()
    
    if not mensajes:
        return jsonify({"error": "No hay mensajes en el chat de esta tarea para analizar."}), 400
        
    # Importamos el módulo que acabamos de crear y procesamos con la IA
    from disputas_ia import analizar_disputa_chat
    reporte_ia = analizar_disputa_chat(mensajes, dict(tarea))
    
    # Retorna el JSON estructurado para que lo pintes en tu panel administrativo
    return jsonify({
        "tarea_id": tarea_id,
        "titulo_tarea": tarea['titulo'],
        "estado_actual": tarea['estado'],
        "analisis_ia": reporte_ia
    })

# =====================================================================
# 🏁 BLOQUE FINAL DE ARRANQUE E INICIALIZACIÓN AUTOMÁTICA
# =====================================================================

# =====================================================================
# 🛠️ ENDPOINT COPILOT DE PERFIL PARA EL TRABAJADOR (FASE 2.2)
# =====================================================================
@app.route('/trabajador/optimizar-perfil', methods=['POST'])
def optimizar_perfil():
    # Validamos que el usuario esté logueado
    if 'usuario_nombre' not in session:
        return jsonify({"error": "No autorizado"}), 401
        
    # Recibimos los datos actuales del formulario de su perfil
    datos_frontend = request.get_json()
    descripcion_actual = datos_frontend.get('descripcion', '')
    habilidades = datos_frontend.get('habilidades', '')
    ciudad = datos_frontend.get('ciudad', 'Colombia')
    
    if not descripcion_actual:
        return jsonify({"error": "La descripción actual no puede estar vacía."}), 400
        
    # Invocamos el Copilot de IA
    from copilot_tecnico import optimizar_perfil_trabajador
    resultado_copilot = optimizar_perfil_trabajador(descripcion_actual, habilidades, ciudad)
    
    # Devolvemos la propuesta para que el técnico la apruebe y guarde en SQLite
    return jsonify(resultado_copilot)

if __name__ == '__main__':
    # Inicialización automática de la base de datos al encender el servidor
    conexion = sqlite3.connect(ruta_db)
    cursor = conexion.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            pago TEXT NOT NULL,
            categoria TEXT NOT NULL,
            estado TEXT DEFAULT 'Disponible',
            costo_creditos REAL,
            cliente_correo TEXT,
            latitud REAL,
            longitud REAL,
            zona TEXT,
            tecnico_correo TEXT,
            fecha_publicacion DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. Tabla de mensajes (LA QUE NECESITAS PARA QUE TODO LO ANTERIOR FUNCIONE)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mensajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarea_id INTEGER,
            remitente_correo TEXT,
            canal_trabajador TEXT,
            mensaje TEXT,
            tipo TEXT DEFAULT 'texto',
            leido INTEGER DEFAULT 0,
            fecha_envio DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conexion.commit()
    conexion.close()

    # Arranca tu servidor normal en el puerto 5000
    app.run(debug=True, port=5000)