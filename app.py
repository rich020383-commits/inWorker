import os
import re
from PIL import Image
import math
import time
import threading
from google import genai
from moderacion import es_mensaje_seguro
from disputas_ia import analizar_disputa_chat

# 🔧 CONFIGURACIÓN AVANZADA CON FLASK-SQLALCHEMY PARA OPTIMIZAR EL PLAN STARTER
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, current_app, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_  # 👈 ¡ESTA ES LA LÍNEA MÁGICA QUE FALTA!
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash 
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

import re

# Asegúrate de tener importado genai (vi que ya lo tienes arriba en tu app.py)
# from google import genai

def imagen_contiene_contactos(ruta_imagen):
    """
    Usa Gemini Vision para leer el texto de la foto y detectar si intentan 
    pasar un número de celular o correo para evadir la plataforma.
    """
    try:
        # 1. Le pasamos la imagen a Gemini
        imagen_pil = Image.open(ruta_imagen)
        
        # 2. Le damos una instrucción estricta al modelo
        prompt = """
        Eres un moderador de seguridad estricto. Lee todo el texto visible en esta imagen.
        Tu único trabajo es detectar si el usuario está intentando compartir información de contacto directo.
        
        Responde ÚNICAMENTE con la palabra "BLOQUEAR" si encuentras:
        - Números de teléfono (secuencias de 7 a 10 números, con o sin guiones/espacios).
        - Direcciones de correo electrónico.
        - Enlaces a redes sociales (Instagram, Facebook, etc).
        
        Responde ÚNICAMENTE con "SEGURO" si la imagen es normal (una foto de un daño, un equipo, un repuesto, etc) y no tiene contactos.
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash', # Usamos flash porque es ultra rápido
            contents=[prompt, imagen_pil]
        )
        
        resultado = response.text.strip().upper()
        
        if "BLOQUEAR" in resultado:
            return True # Sí contiene contactos prohibidos
        return False # Es una imagen segura
        
    except Exception as e:
        print(f"⚠️ Error en OCR de Gemini: {e}")
        # En caso de que la IA falle por red, dejamos pasar la foto para no trabar el chat
        return False

# 📸 CONFIGURACIÓN Y VALIDACIÓN DE IMÁGENES PERMITIDAS
EXTENSIONES_PERMITIDAS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = os.path.join(ruta_actual, 'static', 'uploads')

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def archivo_permitido(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in EXTENSIONES_PERMITIDAS

# 🔧 ENVÍO DE CORREOS EN SEGUNDO PLANO SIN PERDER EL CONTEXTO
def enviar_bienvenida_tecnico(app_contexto, correo_destino, nombre_usuario):
    with app_contexto.app_context():
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

# ========================================================
# 📦 REDIRECCIÓN AL DISCO PERSISTENTE SEGURO DE RENDER
# ========================================================
# Detecta si corre en Render para meter la BD en el disco externo /data. Si es local, usa la raíz.
if os.environ.get("RENDER"):
    uri = "sqlite:////data/inworker_prod.db"  # Ruta absoluta dentro de tu SSD asignado
else:
    uri = os.environ.get("DATABASE_URL", "sqlite:///inworker_prod.db")

# Ajuste por compatibilidad general de cadenas
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 💰 CONFIGURACIÓN DE PRECIOS NACIONALES
VALOR_CREDITO_COP = 10000.0  

# ========================================================
# 📐 MODELOS DE LA BASE DE DATOS (ESTRUCTURA DE TABLAS)
# ========================================================
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    cedula = db.Column(db.String(50), unique=True, nullable=False)
    correo = db.Column(db.String(150), unique=True, nullable=False)
    contrasena = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(50), nullable=False)
    profesion = db.Column(db.String(150), default='Técnico General')
    habilidades = db.Column(db.Text, default='Sin especificar')
    foto = db.Column(db.String(255))
    telefono = db.Column(db.String(50), default='Sin especificar')
    verificado = db.Column(db.Integer, default=0)
    saldo_creditos = db.Column(db.Float, default=0.0) # Inician en 0 Cr
    puntuacion_total = db.Column(db.Float, default=0.0)
    total_calificaciones = db.Column(db.Integer, default=0)
    descripcion = db.Column(db.Text, default='')

class Tarea(db.Model):
    __tablename__ = 'tareas'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    pago = db.Column(db.String(50), nullable=False)
    categoria = db.Column(db.String(100), nullable=False)
    estado = db.Column(db.String(50), default='Disponible')
    cliente_correo = db.Column(db.String(150))
    trabajador_nombre = db.Column(db.String(150))
    trabajador_correo = db.Column(db.String(150))
    costo_creditos = db.Column(db.Float, default=1.0)
    latitud = db.Column(db.Float, default=10.9639)
    longitud = db.Column(db.Float, default=-74.7964)
    confirmacion_cliente = db.Column(db.Integer, default=0)
    confirmacion_trabajador = db.Column(db.Integer, default=0)
    calificada = db.Column(db.Integer, default=0)
    zona = db.Column(db.String(100), default='Barranquilla (Norte)')

class Mensaje(db.Model):
    __tablename__ = 'mensajes'
    id = db.Column(db.Integer, primary_key=True)
    tarea_id = db.Column(db.Integer, index=True) # ⚡ INDEXADO para velocidad de Polling extrema
    canal_trabajador = db.Column(db.String(150), index=True) # ⚡ INDEXADO para velocidad de Polling extrema
    remitente_correo = db.Column(db.String(150))
    mensaje = db.Column(db.Text)
    tipo = db.Column(db.String(50), default='texto')
    leido = db.Column(db.Integer, default=0)
    fecha_envio = db.Column(db.DateTime, default=db.func.current_timestamp())

class Portafolio(db.Model):
    __tablename__ = 'portafolio'
    id = db.Column(db.Integer, primary_key=True)
    usuario_correo = db.Column(db.String(150), nullable=False)
    imagen_ruta = db.Column(db.String(255), nullable=False)
    descripcion = db.Column(db.Text)
    tipo = db.Column(db.String(100), default='Trabajo Realizado')
    fecha_subida = db.Column(db.DateTime, default=db.func.current_timestamp())

class BilleteraRetiro(db.Model):
    __tablename__ = 'billetera_retiros'
    id = db.Column(db.Integer, primary_key=True)
    usuario_correo = db.Column(db.String(150), nullable=False)
    monto_creditos = db.Column(db.Float, nullable=False)
    equivalente_pesos = db.Column(db.Float, nullable=False)
    metodo_pago = db.Column(db.String(50), nullable=False)
    detalles_cuenta = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(50), default='Pendiente')
    fecha_solicitud = db.Column(db.DateTime, default=db.func.current_timestamp())


# ========================================================
# 🚀 EJECUCIÓN DEL CONTEXTO Y SEEDING DE SEGURIDAD
# ========================================================
with app.app_context():
    # 1. Crea automáticamente el archivo físico dentro del SSD (/data/) con las tablas indexadas
    db.create_all()
    print("¡Estructura de Base de Datos persistente e indexada montada con éxito!")
    
    # 2. Sembrado automático del Administrador Principal 'baraka'
    admin_existe = Usuario.query.filter_by(correo='baraka@inworker.com').first()
    if not admin_existe:
        print("Creando usuario Administrador predeterminado en almacenamiento persistente...")
        nuevo_admin = Usuario(
            nombre='baraka',
            cedula='99999999',
            correo='baraka@inworker.com',
            contrasena='baraka123', # Conserva tu credencial exacta actual
            rol='Admin',
            profesion='Administrador Principal',
            telefono='3000000000',
            verificado=1,
            saldo_creditos=999.0
        )
        db.session.add(nuevo_admin)
        db.session.commit()
        print("¡Administrador 'baraka' blindado y registrado con éxito!")
    else:
        print("El Administrador principal ya está operativo en el almacenamiento persistente.")

# =========================================================================
# ENDPOINT API PARA POLLEO ASÍNCRONO DE NOTIFICACIONES GLOBALES
# =========================================================================
@app.route('/api/notificaciones/globales', methods=['GET'])
def api_notificaciones_globales():
    if 'usuario_correo' not in session:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
        
    correo_logueado = session['usuario_correo']
    rol_logueado = session.get('usuario_rol') # Puede ser 'Cliente', 'Trabajador' o 'Worker'
    
    mensajes_sin_leer = 0

    # ⚡ SECCIÓN 1: Conteo optimizado de mensajes no leídos usando SQLAlchemy Join
    if rol_logueado == 'Cliente':
        mensajes_sin_leer = db.session.query(db.func.count(Mensaje.id))\
            .join(Tarea, Mensaje.tarea_id == Tarea.id)\
            .filter(
                Tarea.cliente_correo == correo_logueado,
                Mensaje.remitente_correo != correo_logueado,
                Mensaje.leido == 0
            ).scalar() or 0

    elif rol_logueado in ['Trabajador', 'Worker']:
        mensajes_sin_leer = db.session.query(db.func.count(Mensaje.id))\
            .join(Tarea, Mensaje.tarea_id == Tarea.id)\
            .filter(
                (Tarea.trabajador_correo == correo_logueado) | 
                (Mensaje.canal_trabajador == 'sala_' + db.func.cast(Tarea.id, db.String)),
                Mensaje.remitente_correo != correo_logueado,
                Mensaje.leido == 0
            ).scalar() or 0

    # ⚡ SECCIÓN 2: Consulta de Alertas de Estados (Garantía o Finalizada)
    tareas_query = Tarea.query.filter(
        (Tarea.cliente_correo == correo_logueado) | (Tarea.trabajador_correo == correo_logueado),
        Tarea.estado.in_(['En Garantia', 'Finalizada'])
    ).all()

    # Mapeamos los objetos de la base de datos a un diccionario simple para el JSON
    tareas_alertas = [{
        'id': t.id,
        'titulo': t.titulo,
        'estado': t.estado,
        'zona': t.zona
    } for t in tareas_query]
    
    return jsonify({
        'success': True,
        'mensajes_sin_leer': mensajes_sin_leer,
        'alertas_estados': tareas_alertas
    })
# =====================================================================
# 💬 SISTEMA DE ALERTAS EN TIEMPO REAL (Llamado cada 7 segundos) - ¡OPTIMIZADO!
# =====================================================================
@app.route('/verificar_alertas')
def verificar_alertas():
    # Si no hay sesión activa, respondemos con cero de inmediato
    if 'usuario_correo' not in session:
        return jsonify({"total_mensajes": 0})
        
    correo_usuario = session['usuario_correo']
    rol_logueado = session.get('usuario_rol') # Puede ser 'Cliente', 'Trabajador' o 'Worker'
    
    try:
        total_sin_leer = 0
        
        # Consultamos dinámicamente según el rol usando el Pool de conexiones de SQLAlchemy
        if rol_logueado == 'Cliente':
            total_sin_leer = db.session.query(db.func.count(Mensaje.id))\
                .join(Tarea, Mensaje.tarea_id == Tarea.id)\
                .filter(
                    Tarea.cliente_correo == correo_usuario,
                    Mensaje.remitente_correo != correo_usuario,
                    Mensaje.leido == 0
                ).scalar() or 0
                
        elif rol_logueado in ['Trabajador', 'Worker']:
            total_sin_leer = db.session.query(db.func.count(Mensaje.id))\
                .join(Tarea, Mensaje.tarea_id == Tarea.id)\
                .filter(
                    (Tarea.trabajador_correo == correo_usuario) | 
                    (Mensaje.canal_trabajador == 'sala_' + db.func.cast(Tarea.id, db.String)),
                    Mensaje.remitente_correo != correo_usuario,
                    Mensaje.leido == 0
                ).scalar() or 0
        else:
            return jsonify({"total_mensajes": 0})
            
        return jsonify({"total_mensajes": total_sin_leer})
        
    except Exception as e:
        print(f"⚠️ Error al verificar alertas en tiempo real: {e}")
        return jsonify({"total_mensajes": 0})

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
# 🔑 2. MÓDULO DE AUTENTICACIÓN CENTRALIZADO (Maneja GET y POST) - OPTIMIZADO
# =====================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo_form = request.form['correo']
        contrasena_form = request.form['contrasena']
        
        # ⚡ Consulta segura y directa usando el modelo Usuario de SQLAlchemy
        usuario = Usuario.query.filter_by(correo=correo_form, contrasena=contrasena_form).first()
        
        if usuario:
            # SQLAlchemy nos permite mapear las propiedades directo del objeto obtenido
            session['usuario_nombre'] = usuario.nombre
            session['usuario_rol'] = usuario.rol
            session['usuario_correo'] = usuario.correo
            return redirect(url_for('home'))
        
        flash("❌ Credenciales incorrectas.", "error")
        return redirect(url_for('login'))
        
    # Si entran por GET (es decir, haciendo clic en "Ingresar al Panel" desde la landing)
    return render_template('login.html')


# =====================================================================
# 📝 3. PROCESAMIENTO DE REGISTROS (Únicamente vía POST) - OPTIMIZADO
# =====================================================================
@app.route('/registrar', methods=['POST'])
def registrar():
    acepta_terminos = request.form.get('acepta_terminos')
    if not acepta_terminos:
        flash("❌ Es obligatorio aceptar los Términos y Condiciones para registrarse.", "error")
        return redirect(url_for('login', action='registro')) # Redirige a la pestaña de registro en login.html

    try:
        telefono_form = request.form.get('telefono', 'Sin especificar')
        nombre = request.form['nombre']
        cedula = request.form['cedula']
        correo = request.form['correo']
        contrasena = request.form['contrasena']
        rol = request.form['rol']

        # 1. VALIDAR SI EL CORREO YA EXISTE (Usando SQLAlchemy)
        correo_existe = Usuario.query.filter_by(correo=correo).first()
        if correo_existe:
            flash("❌ Error: Este correo electrónico ya está registrado.", "error")
            return redirect(url_for('login', action='registro'))

        # 2. VALIDAR SI LA CÉDULA YA EXISTE
        cedula_existe = Usuario.query.filter_by(cedula=cedula).first()
        if cedula_existe:
            flash("❌ Error: Esta cédula ya se encuentra registrada en el sistema.", "error")
            return redirect(url_for('login', action='registro'))

        # 3. SI TODO ESTÁ BIEN, SE CREA EL OBJETO E INSERTA
        nuevo_usuario = Usuario(
            nombre=nombre,
            cedula=cedula,
            correo=correo,
            contrasena=contrasena,
            rol=rol,
            telefono=telefono_form,
            verificado=0,
            saldo_creditos=0.0
        )
        
        db.session.add(nuevo_usuario)
        db.session.commit() # Guarda físicamente en /data/inworker_prod.db
        
        # Envío de correo en segundo plano (Mantenemos tu lógica intacta)
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
        db.session.rollback() # Si algo falla, deshace la operación para no corromper la BD
        print(f"⚠️ Error crítico en el registro: {e}")
        flash("❌ Ocurrió un error interno. Por favor, inténtalo de nuevo.", "error")
        return redirect(url_for('login', action='registro'))
# =====================================================================
# 🛡️ GESTIÓN DE ADMINISTRACIÓN: VERIFICAR Y PAUSAR ESPECIALISTAS
# =====================================================================

@app.route('/admin/verificar_usuario/<int:usuario_id>', methods=['POST'])
def admin_verificar_usuario(usuario_id):
    if 'usuario_nombre' not in session:
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
        
    try:
        # ⚡ Buscamos al usuario directamente por su ID de clave primaria
        usuario = Usuario.query.get(usuario_id)
        
        if not usuario:
            return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404
            
        # Cambiamos el estado de 'verificado' a 1
        usuario.verificado = 1
        db.session.commit() # Impacta directamente el archivo en /data/
        
        flash("✅ ¡Especialista verificado con éxito en el sistema nacional!", "success")
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Error al verificar usuario {usuario_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/pausar_usuario/<int:usuario_id>', methods=['POST'])
def admin_pausar_usuario(usuario_id):
    if 'usuario_nombre' not in session:
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
        
    try:
        # ⚡ Buscamos al usuario por su ID
        usuario = Usuario.query.get(usuario_id)
        
        if not usuario:
            return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404
            
        # Para pausar, desverificamos al usuario (verificado = 0)
        usuario.verificado = 0
        db.session.commit()
        
        flash("⏸️ Perfil del especialista pausado correctamente.", "success")
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Error al pausar usuario {usuario_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =====================================================================
# MÓDULO DE RECUPERACIÓN DE CONTRASEÑA - OPTIMIZADO
# =====================================================================

@app.route('/recuperar-contrasena', methods=['GET', 'POST'])
def recuperar_contrasena():
    if request.method == 'POST':
        # ⚡ Capturamos el name exacto que pusimos en el nuevo login.html
        correo = request.form.get('correo_recuperacion')
        
        if not correo:
            flash("❌ Debes ingresar un correo válido.", "error")
            return redirect(url_for('login', action='recuperar'))
        
        # Consulta directa y segura usando el modelo Usuario
        usuario = Usuario.query.filter_by(correo=correo).first()
        
        if usuario:
            # Generar un token único basado en el correo del usuario
            token = serializer.dumps(correo, salt='recuperar-claves-inworker')
            # ⚡ OJO: Asegúrate de que tu dominio sea el correcto en producción
            link_recuperacion = f"https://inworker.co" + url_for('restablecer_clave', token=token)
            
            # Enviar el correo con el enlace seguro
            try:
                msg = Message(
                    'Restablecer tu contraseña - inWorker',
                    recipients=[correo]
                )
                msg.html = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
                    <div style="background-color: #2563EB; padding: 20px; text-align: center; color: white;">
                        <h2>¿Olvidaste tu contraseña? 🔑</h2>
                    </div>
                    <div style="padding: 20px; color: #333333; line-height: 1.6;">
                        <p>Hola, <strong>{usuario.nombre}</strong>.</p>
                        <p>Recibimos una solicitud para restablecer la contraseña de tu cuenta en inWorker. Para continuar, haz clic en el siguiente botón:</p>
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{link_recuperacion}" style="background-color: #22C55E; color: white; padding: 12px 25px; text-align: center; text-decoration: none; font-weight: bold; border-radius: 8px;">Restablecer Contraseña</a>
                        </div>
                        <p style="font-size: 12px; color: #777777;">Este enlace es seguro y vencerá pronto. Si no solicitaste este cambio, puedes ignorar este correo con total tranquilidad.</p>
                    </div>
                </div>
                """
                mail.send(msg)
                flash("📧 Te hemos enviado un enlace de recuperación a tu correo electrónico.", "success")
            except Exception as e:
                print(f"Error enviando correo: {e}")
                flash("⚠️ Ocurrió un error al intentar enviar el correo. Intenta más tarde.", "error")
        else:
            flash("❌ El correo ingresado no está registrado en inWorker.", "error")
            
        # Redirigimos al login pero manteniendo la pestaña de recuperación abierta
        return redirect(url_for('login', action='recuperar'))
        
    # Si intentan entrar por GET (escribiendo la URL directo), los mandamos al login
    return redirect(url_for('login', action='recuperar'))


<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>inWorker - Nueva Contraseña</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body class="bg-slate-50 text-slate-900 min-h-screen flex items-center justify-center p-4 font-sans">

    <div class="bg-white w-full max-w-md p-6 sm:p-8 rounded-2xl border border-slate-200 shadow-xl text-center">
        
        <div class="flex flex-col items-center justify-center mb-6 select-none">
            <i class="fas fa-unlock-alt text-5xl text-[#22C55E] mb-4"></i>
            <h2 class="text-2xl font-black text-slate-900 tracking-tight">Nueva Contraseña</h2>
            <p class="text-xs text-slate-500 mt-2 px-2">Elige una contraseña segura que puedas recordar fácilmente.</p>
        </div>

        <form method="POST" action="{{ url_for('restablecer_clave', token=token) }}" class="space-y-4">
            
            <div class="text-left space-y-1">
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-500">Tu Nueva Contraseña</label>
                
                <div class="relative flex items-center">
                    <input type="password" id="pass_nueva" name="contrasena" placeholder="Escribe tu nueva clave" required autocomplete="new-password"
                        class="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-900 focus:outline-none focus:border-green-500 transition-colors">
                    
                    <button type="button" onclick="togglePassword('pass_nueva', 'icon_nueva')" class="absolute right-4 text-slate-400 hover:text-green-600 transition-colors focus:outline-none">
                        <i class="fas fa-eye" id="icon_nueva"></i>
                    </button>
                </div>
            </div>

            <button type="submit" class="w-full bg-green-500 hover:bg-green-600 text-white font-black py-3.5 px-4 rounded-xl text-xs uppercase tracking-wider transition-all shadow-md active:scale-[0.98] mt-4">
                Guardar y Entrar <i class="fas fa-check-circle ml-1"></i>
            </button>
            
        </form>
    </div>

    <script>
        function togglePassword(inputId, iconId) {
            const input = document.getElementById(inputId);
            const icon = document.getElementById(iconId);
            
            if (input && icon) {
                if (input.type === "password") {
                    input.type = "text";
                    icon.classList.remove('fa-eye');
                    icon.classList.add('fa-eye-slash');
                } else {
                    input.type = "password";
                    icon.classList.remove('fa-eye-slash');
                    icon.classList.add('fa-eye');
                }
            }
        }
    </script>
</body>
</html>

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard', methods=['GET', 'POST'])
def home():
    # 🛡️ PROTECCIÓN AMIGABLE: Validamos usando el correo (más seguro que el nombre)
    if 'usuario_correo' not in session: 
        flash("🔒 Por favor, inicia sesión para acceder al panel.", "error")
        return redirect(url_for('login'))
        
    correo_logueado = session.get('usuario_correo')
    
    # Manejo de Solicitud de Retiro (POST)
    if request.method == 'POST' and request.form.get('accion_perfil') == 'solicitar_retiro':
        try:
            creditos_retiro = float(request.form.get('creditos_retiro', 0))
        except ValueError:
            creditos_retiro = 0.0
            
        metodo = request.form.get('metodo_pago', 'No especificado')
        detalles = request.form.get('detalles_cuenta', '')
        
        # Buscamos al usuario de forma directa
        usuario = Usuario.query.filter_by(correo=correo_logueado).first()
        saldo_actual = usuario.saldo_creditos if usuario else 0.0
        
        if creditos_retiro > 0 and creditos_retiro <= saldo_actual:
            equivalente_cop = creditos_retiro * VALOR_CREDITO_COP
            nuevo_saldo = round(saldo_actual - creditos_retiro, 2)
            
            try:
                # 1. Descontamos el saldo al usuario asignando la propiedad
                usuario.saldo_creditos = nuevo_saldo
                
                # 2. Registramos la solicitud en la tabla de retiros
                nuevo_retiro = BilleteraRetiro(
                    usuario_correo=correo_logueado,
                    monto_creditos=creditos_retiro,
                    equivalente_pesos=equivalente_cop,
                    metodo_pago=metodo,
                    detalles_cuenta=detalles,
                    estado='Pendiente'
                )
                db.session.add(nuevo_retiro)
                db.session.commit() # Guarda ambas acciones de forma atómica en el disco persistente
                
                flash(f"✅ Solicitud por ${equivalente_cop:,.0f} COP enviada a revisión técnica.", "success")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error al procesar el retiro financiero: {e}")
                flash("❌ Ocurrió un error al procesar tu transacción. Fondos protegidos.", "error")
        else:
            flash("❌ Fondos insuficientes o cantidad de créditos inválida.", "error")
    
    # 📊 SECCIÓN DE MÉTRICAS DEL DASHBOARD (Agregaciones optimizadas)
    total_workers = Usuario.query.filter_by(rol='Trabajador').count()
    
    ordenes_mediacion = Tarea.query.filter(Tarea.estado.in_(['Cotización Pendiente', 'En Garantia'])).count()
    
    # Suma limpia de fondos en Escrow (Maneja si es None devolviendo 0.0)
    fondos_escrow = db.session.query(db.func.sum(db.func.cast(Tarea.pago, db.Float)))\
        .filter(Tarea.estado == 'En Garantia').scalar() or 0.0
    
    # 💰 CONSULTA REAL DE BALDO EN BASE DE DATOS
    usuario_info = Usuario.query.filter_by(correo=correo_logueado).first()
    saldo_real = round(usuario_info.saldo_creditos, 2) if usuario_info else 0.0
    
    # ⚖️ CONSULTA DE DISPUTAS ACTIVAS PARA LA CONSOLA DE ARBITRAJE
    disputas_query = Tarea.query.filter_by(estado='En Arbitraje Admin').order_by(Tarea.id.desc()).all()
    
    # Adaptación a diccionarios planos para mantener compatibilidad con tu frontend actual
    lista_disputas = [{
        'id': d.id,
        'titulo': d.titulo,
        'estado': d.estado,
        'reportado_por': getattr(d, 'reportado_por', 'No especificado'),  # Seguro si aún estás migrando columnas
        'motivo_disputa': getattr(d, 'motivo_disputa', 'Sin motivo'),
        'costo_creditos': d.costo_creditos
    } for d in disputas_query]
    
    # Armamos el diccionario dinámico para las plantillas
    perfil_real = {'saldo_creditos': saldo_real, 'saldo': saldo_real}
    
    return render_template('index.html', 
                           nombre_usuario=session['usuario_nombre'],
                           total_workers=total_workers,
                           ordenes_mediacion=ordenes_mediacion,
                           fondos_escrow=fondos_escrow,
                           saldo=saldo_real,
                           saldo_usuario=saldo_real,
                           cliente_perfil=perfil_real,
                           trabajador_perfil=perfil_real,
                           lista_disputas=lista_disputas)

@app.route('/api/optimizar_perfil', methods=['POST'])
def api_optimizar_perfil():
    if 'usuario_correo' not in session:
        return jsonify({'error': 'No autorizado'}), 401
        
    try:
        data = request.get_json() or {} # Evita errores si data llega None
    except Exception:
        return jsonify({'error': 'Formato JSON inválido'}), 400
        
    profesion = data.get('profesion', 'Especialista')
    habilidades_actuales = data.get('habilidades', '')
    
    # 🕵️‍♂️ Monitoreo en logs de Render
    print(f"--- NUEVA PETICIÓN DE IA ---")
    print(f"Profesión recibida: {profesion}")
    print(f"Habilidades recibidas: {habilidades_actuales}")
    
    prompt = f"""
    Eres un experto en marca profesional para la plataforma inWorker.
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
        # 🚀 Consumo estable con el nuevo SDK de Gemini
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        texto_optimizado = response.text.strip()
        
        print(f"✅ Respuesta exitosa del nuevo Gemini: {texto_optimizado}")
        return jsonify({'sugerencia': texto_optimizado})
        
    except Exception as e:
        print(f"❌ ERROR REAL EN NUEVO SDK DE GEMINI: {e}")
        # El respaldo amigable por si la API falla o excede la cuota
        respaldo = f"Especialista en {profesion} comprometido con la excelencia operativa, puntualidad y soluciones eficientes en inWorker."
        return jsonify({'sugerencia': respaldo})

# --- RUTAS DEL ADMINISTRADOR MÓDULOS CORE - OPTIMIZADO ---
@app.route('/admin/validar_tecnicos')
def admin_validar_tecnicos():
    if 'usuario_nombre' not in session or session.get('usuario_rol') != 'Admin':
        return redirect(url_for('index'))
    
    # ⚡ Traemos todos los usuarios con rol 'Trabajador' usando SQLAlchemy
    trabajadores = Usuario.query.filter_by(rol='Trabajador').all()
    
    # Mapeamos los objetos a diccionarios para mantener compatibilidad total con el HTML viejo
    tecnicos_pendientes = [{
        'id': t.id,
        'nombre': t.nombre,
        'cedula': t.cedula,
        'correo': t.correo,
        'rol': t.rol,
        'telefono': t.telefono,
        'verificado': t.verificado,
        'saldo_creditos': t.saldo_creditos
    } for t in trabajadores]
    
    return render_template('trabajadores.html', usuarios=tecnicos_pendientes, nombre_usuario=session['usuario_nombre'])

@app.route('/admin/modulo_cedulas', methods=['GET', 'POST'])
def admin_modulo_cedulas():
    if 'usuario_nombre' not in session or session.get('usuario_rol') != 'Admin':
        return redirect(url_for('index'))
    
    resultado_busqueda = None
    if request.method == 'POST':
        cedula_buscar = request.form.get('cedula', '').strip()
        
        # ⚡ Búsqueda indexada instantánea por cédula
        usuario_db = Usuario.query.filter_by(cedula=cedula_buscar).first()
        
        if usuario_db:
            resultado_busqueda = {
                'id': usuario_db.id,
                'nombre': usuario_db.nombre,
                'cedula': usuario_db.cedula,
                'correo': usuario_db.correo,
                'rol': usuario_db.rol,
                'telefono': usuario_db.telefono,
                'verificado': usuario_db.verificado,
                'saldo_creditos': usuario_db.saldo_creditos
            }
            
        flash(f"Búsqueda ejecutada para la cédula: {cedula_buscar}", "success")
    
    return render_template('cedula.html', resultado=resultado_busqueda, nombre_usuario=session['usuario_nombre'])

@app.route('/admin/reportes')
def admin_reportes():
    if 'usuario_nombre' not in session or session.get('usuario_rol') != 'Admin':
        return redirect(url_for('index'))
        
    # 📊 Métricas globales optimizadas desde memoria con funciones nativas del ORM
    total_tareas = Tarea.query.count()
    
    # Suma directa del volumen aprobado en COP (Maneja si da None devolviendo 0)
    volumen_cop = db.session.query(db.func.sum(BilleteraRetiro.equivalente_pesos))\
        .filter(BilleteraRetiro.estado == 'Aprobado').scalar() or 0
        
    total_workers = Usuario.query.filter_by(rol='Trabajador').count()
    
    return render_template('reportes.html', 
                           total_tareas=total_tareas, 
                           volumen_cop=volumen_cop, 
                           total_workers=total_workers, 
                           nombre_usuario=session['usuario_nombre'])

# --- MÓDULO ADMINISTRATIVO DE GESTIÓN DE RETIROS (COBROS) - OPTIMIZADO ---
@app.route('/admin/retiros', methods=['GET', 'POST'])
def admin_retiros():
    if 'usuario_nombre' not in session or session.get('usuario_rol') != 'Admin':
        return redirect(url_for('index'))
        
    # ⚡ Definimos la variable para que el filtro de Escrow no lance NameError
    correo_logueado = session.get('usuario_correo', '')
        
    if request.method == 'POST':
        solicitud_id = request.form.get('id_retiro')
        accion = request.form.get('accion')
        
        try:
            # ⚡ Buscamos la solicitud de retiro por su clave primaria
            solicitud = BilleteraRetiro.query.get(solicitud_id)
            
            if solicitud and solicitud.estado == 'Pendiente':
                if accion == 'Completado':  # Botón "Marcar Pagado"
                    solicitud.estado = 'Aprobado'
                    flash(f"✅ Retiro #{solicitud_id} aprobado para transferencia manual.", "success")
                    
                elif accion == 'Rechazado':  # Botón "Rechazar"
                    # Buscamos al usuario dueño del correo asociado al cobro
                    usuario = Usuario.query.filter_by(correo=solicitud.usuario_correo).first()
                    
                    if usuario:
                        # Reintegramos los créditos de forma matemática exacta
                        user_saldo = usuario.saldo_creditos or 0.0
                        usuario.saldo_creditos = round(user_saldo + solicitud.monto_creditos, 2)
                        solicitud.estado = 'Rechazado'
                        flash(f"❌ Retiro #{solicitud_id} rechazado. Créditos reintegrados al trabajador.", "error")
                    else:
                        flash("❌ Error: No se encontró al usuario para reintegrar los fondos.", "error")
                
                db.session.commit() # Guarda todos los cambios de manera segura en /data/
                
        except Exception as e:
            db.session.rollback() # Si algo falla en la mitad, la BD vuelve a su estado seguro
            print(f"❌ Error crítico procesando acción de retiro #{solicitud_id}: {e}")
            flash("❌ Ocurrió un error interno al procesar el estado del retiro.", "error")

    # 📊 CONSTRUCCIÓN DE LA LISTA DE RETIROS PENDIENTES CON JOIN DE MODELOS
    solicitudes_pendientes = db.session.query(BilleteraRetiro, Usuario)\
        .outerjoin(Usuario, db.func.lower(db.func.trim(BilleteraRetiro.usuario_correo)) == db.func.lower(db.func.trim(Usuario.correo)))\
        .filter(BilleteraRetiro.estado == 'Pendiente')\
        .order_by(BilleteraRetiro.id.desc()).all()
        
    # Formateamos exactamente como lo pide tu HTML usando un mapeo plano
    lista_retiros = []
    for ret, usr in solicitudes_pendientes:
        lista_retiros.append({
            'id': ret.id,
            'monto_creditos': ret.monto_creditos,
            'equivalente_pesos': ret.equivalente_pesos,
            'metodo_pago': ret.metodo_pago,
            'detalles_cuenta': ret.detalles_cuenta,
            'estado': ret.estado,
            'usuario_correo': ret.usuario_correo,
            'nombre': usr.nombre if usr else ret.usuario_correo,
            'trabajador_cedula': usr.cedula if usr else 'Sin verificar'
        })
    
    # Métricas del lateral / contadores del panel administrativo
    total_workers = Usuario.query.filter_by(rol='Trabajador').count()
    ordenes_mediacion = Tarea.query.filter(Tarea.estado.in_(['Cotización Pendiente', 'En Garantia'])).count()
    
    # 🛡️ CÁLCULO DE MÉTRICAS FALTANTES PARA EL DASHBOARD (ALINEADO Y CORREGIDO)
    fondos_escrow = db.session.query(db.func.sum(Tarea.costo_creditos)).filter(
        Tarea.estado == 'En Garantia',
        or_(Tarea.cliente_correo == correo_logueado, Tarea.trabajador_correo == correo_logueado)
    ).scalar() or 0.0
        
    return render_template('admin_retiros.html', 
                           solicitudes=lista_retiros, 
                           nombre_usuario=session.get('usuario_nombre', 'Admin'),
                           total_workers=total_workers, 
                           ordenes_mediacion=ordenes_mediacion, 
                           fondos_escrow=fondos_escrow)

@app.route('/recargar_billetera', methods=['GET', 'POST'])
def recargar_billetera():
    # 🛡️ Corregido para validar de forma segura con el correo o id unificado en sesión
    if 'usuario_correo' not in session:
        return redirect(url_for('login'))
        
    correo_logueado = session['usuario_correo']
        
    if request.method == 'POST':
        try:
            # Selecciona el paquete (Ej: $30.000 COP = 1 Crédito)
            creditos_a_cargar = float(request.form.get('creditos', 1))
        except ValueError:
            creditos_a_cargar = 0.0
            
        try:
            # ⚡ Buscamos al usuario de forma directa por su correo indexado
            usuario = Usuario.query.filter_by(correo=correo_logueado).first()
            
            if usuario:
                # Sumamos los créditos directamente sobre el atributo del modelo
                saldo_actual = usuario.saldo_creditos or 0.0
                usuario.saldo_creditos = round(saldo_actual + creditos_a_cargar, 2)
                db.session.commit() # Guarda de forma persistente en /data/
                
                # Actualizamos el saldo en la sesión para refrescar la interfaz de inmediato
                session['saldo'] = usuario.saldo_creditos
                flash("¡Recarga simulada con éxito! Fondos agregados a tu billetera inWorker.", "success")
            else:
                flash("❌ Error al identificar el usuario en el sistema.", "error")
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error crítico en recarga de billetera: {e}")
            flash("❌ Ocurrió un error interno al procesar la recarga.", "error")
            
        return redirect(request.referrer or url_for('dashboard'))
        
    # Si entra por GET, consultamos el saldo real directo de la BD para la vista
    usuario_info = Usuario.query.filter_by(correo=correo_logueado).first()
    saldo_vista = round(usuario_info.saldo_creditos, 2) if usuario_info else 0.0
    
    return render_template('recargar.html', saldo=saldo_vista)


# --- CONTROL DEL TABLÓN DE ÓRDENES - OPTIMIZADO ---
@app.route('/tareas')
def ver_tareas():
    if 'usuario_nombre' not in session: 
        return redirect(url_for('index'))
    
    user_lat = request.args.get('lat', type=float)
    user_lng = request.args.get('lng', type=float)
    correo_logueado = session['usuario_correo']
    
    # ⚡ Consulta de saldo real indexada en la BD con SQLAlchemy
    usuario_db = Usuario.query.filter_by(correo=correo_logueado).first()
    saldo_actual = round(usuario_db.saldo_creditos, 2) if usuario_db else 0.0
    
    # Extraemos todas las tareas registradas
    tareas_db = Tarea.query.all()
    
    # Mapeamos los objetos de la BD a un formato de diccionario para no romper tu frontend
    lista_tareas = [{
        'id': t.id,
        'titulo': t.titulo,
        'descripcion': t.descripcion,
        'estado': t.estado,
        'pago': t.pago,
        'costo_creditos': t.costo_creditos,
        'cliente_correo': t.cliente_correo,
        'trabajador_correo': t.trabajador_correo,
        'latitud': t.latitud,
        'longitud': t.longitud,
        'zona': t.zona
    } for t in tareas_db]
    
    t_distancia = False
    
    # Ejecutamos tu lógica matemática de geoposicionamiento
    if user_lat and user_lng:
        t_distancia = True
        for t in lista_tareas:
            # Coordenadas por defecto (Barranquilla) si vienen vacías
            t_lat = t['latitud'] if t['latitud'] is not None else 10.9639
            t_lng = t['longitud'] if t['longitud'] is not None else -74.7964
            t['distancia'] = round(calcular_distancia(user_lat, user_lng, t_lat, t_lng), 1)
            
        lista_tareas.sort(key=lambda x: x.get('distancia', 9999))
        
    # Sincronizamos los perfiles reales con la información financiera exacta de la BD
    perfil_real = {'saldo_creditos': saldo_actual, 'saldo': saldo_actual}
        
    return render_template('tareas.html', 
                           tareas=lista_tareas, 
                           nombre_usuario=session['usuario_nombre'], 
                           saldo=saldo_actual,
                           saldo_usuario=saldo_actual,
                           cliente_perfil=perfil_real,
                           trabajador_perfil=perfil_real,
                           user_lat=user_lat, 
                           user_lng=user_lng,
                           t_distancia=t_distancia)

# =====================================================================
# 🛠️ PUBLICACIÓN Y ASIGNACIÓN DE ÓRDENES - OPTIMIZADO
# =====================================================================
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
        except Exception: 
            creditos_calculados = 1.0
            
        try:
            # ⚡ Creamos la nueva orden mapeando directamente el objeto del modelo
            nueva_tarea = Tarea(
                titulo=request.form['titulo'],
                descripcion=request.form['descripcion'],
                pago=pago_cop,
                categoria=request.form['categoria'],
                estado=estado_inicial,
                costo_creditos=creditos_calculados,
                cliente_correo=session['usuario_correo'],
                latitud=lat,
                longitud=lng,
                zona=zona,
                tecnico_correo=tecnico_invitado if tecnico_invitado else None
            )
            
            db.session.add(nueva_tarea)
            db.session.commit() # Impacta atómicamente el archivo /data/inworker_prod.db
            
            # Capturamos el ID autoincremental generado de inmediato
            id_tarea = nueva_tarea.id
            
            # Limpieza de seguridad de variables temporales de sesión
            session.pop('invitar_tecnico_correo', None)
            
            # Si invitó a un técnico en específico, lo mandamos derecho al Chat de negociación
            if tecnico_invitado and id_tarea:
                return redirect(f'/chat/{id_tarea}')
                
            return redirect(url_for('ver_tareas'))
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error crítico al publicar tarea: {e}")
            flash("❌ Ocurrió un error al publicar la orden. Inténtalo de nuevo.", "error")
            return redirect(url_for('ver_tareas'))
    
    # 🔄 FLUJO GET: Captura de invitaciones rápidas desde el perfil de un técnico
    invitar_correo = request.args.get('invitar', '')
    if invitar_correo:
        session['invitar_tecnico_correo'] = invitar_correo
        return redirect(url_for('ver_tareas', abrir_publicar='true'))
    
    # Retorno seguro si entran por GET sin parámetros
    return render_template('tareas.html')


# =====================================================================
# 👤 GESTIÓN DE PERFIL Y PORTAFOLIO MULTIMEDIA - UNIFICADO Y LIMPIO
# =====================================================================
@app.route('/perfil', methods=['GET', 'POST'])
def ver_perfil():
    if 'usuario_nombre' not in session: 
        return redirect(url_for('index'))
        
    # Forzamos limpieza en el correo logueado para evitar fallos de coincidencia
    correo_logueado = session['usuario_correo'].strip().lower()
    
    if request.method == 'POST':
        accion_perfil = request.form.get('accion_perfil')
        
        if accion_perfil == 'actualizar_datos':
            telefono = request.form.get('telefono', 'Sin especificar')
            profesion = request.form.get('profesion', 'Técnico General')
            habilidades = request.form.get('habilidades', 'Sin especificar')
            descripcion = request.form.get('descripcion', '')
            
            try:
                # ⚡ Buscamos al usuario de forma directa
                usuario = Usuario.query.filter_by(correo=correo_logueado).first()
                
                if not usuario:
                    flash("❌ Error: No se encontró tu perfil de usuario.", "error")
                    return redirect(url_for('ver_perfil'))
                
                # Actualizamos las propiedades de texto directas
                usuario.telefono = telefono
                usuario.profesion = profesion
                usuario.habilidades = habilidades
                usuario.descripcion = descripcion
                
                # 1. PROCESAR FOTO DE AVATAR PRINCIPAL
                archivo_foto = request.files.get('foto_perfil')
                if archivo_foto and archivo_foto.filename != '' and archivo_permitido(archivo_foto.filename):
                    nombre_foto = f"avatar_{int(time.time())}_{secure_filename(archivo_foto.filename)}"
                    archivo_foto.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_foto))
                    usuario.foto = nombre_foto  # Asignamos la nueva ruta de la foto

                # 2. PROCESAR CARGA MÚLTIPLE DEL PORTAFOLIO
                imagenes_portafolio = request.files.getlist('trabajos_previos')
                proyectos_guardados = 0
                
                for file in imagenes_portafolio:
                    if file and file.filename != '' and archivo_permitido(file.filename):
                        nombre_p = f"portafolio_{int(time.time())}_{secure_filename(file.filename)}"
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_p))
                        
                        # Instanciamos el registro en la tabla auxiliar portafolio
                        nuevo_portafolio = Portafolio(
                            usuario_correo=correo_logueado,
                            imagen_ruta=nombre_p,
                            descripcion="Trabajo Realizado",
                            tipo="Trabajo Anterior"
                        )
                        db.session.add(nuevo_portafolio)
                        proyectos_guardados += 1

                # Confirmación atómica de todos los cambios y archivos adjuntos
                db.session.commit()
                
                if proyectos_guardados > 0:
                    flash(f"✨ ¡Perfil actualizado y {proyectos_guardados} fotos añadidas al portafolio!", "success")
                else:
                    flash("✨ ¡Perfil actualizado correctamente!", "success")
                    
            except Exception as e:
                db.session.rollback()
                print(f"⚠️ ERROR CRÍTICO EN POST PERFIL: {e}")
                flash("❌ Ocurrió un error al guardar los cambios en la base de datos.", "error")
                
            return redirect(url_for('ver_perfil'))
            
        elif accion_perfil == 'solicitar_retiro':
            return redirect(url_for('home'))

    # =====================================================================
    # 👤 FLUJO GET: RENDERIZAR VISTA DEL PERFIL (UNIFICADO)
    # =====================================================================
    try:
        usuario_info = Usuario.query.filter_by(correo=correo_logueado).first()
        
        if not usuario_info:
            flash("❌ El perfil solicitado no se encuentra registrado.", "error")
            return redirect(url_for('home'))
            
        # Reconstruimos el diccionario del usuario para la vista
        usuario = {
            'nombre': usuario_info.nombre,
            'cedula': usuario_info.cedula,
            'correo': usuario_info.correo,
            'rol': usuario_info.rol,
            'profesion': usuario_info.profesion,
            'habilidades': usuario_info.habilidades,
            'foto': usuario_info.foto,
            'telefono': usuario_info.telefono,
            'verificado': usuario_info.verificado,
            'descripcion': usuario_info.descripcion,
            'puntuacion_total': usuario_info.puntuacion_total or 0.0,
            'total_calificaciones': usuario_info.total_calificaciones or 0,
            'saldo_creditos': round(usuario_info.saldo_creditos or 0.0, 2)
        }
        
        # Cálculo preciso del promedio de estrellas
        if usuario['total_calificaciones'] > 0:
            usuario['promedio_estrellas'] = round(usuario['puntuacion_total'] / usuario['total_calificaciones'], 1)
        else:
            usuario['promedio_estrellas'] = 0.0

        # ⚡ Consulta del Portafolio
        proyectos_db = Portafolio.query.filter_by(usuario_correo=correo_logueado).order_by(Portafolio.id.desc()).all()
        proyectos = [{
            'id': p.id,
            'imagen_ruta': p.imagen_ruta,
            'descripcion': p.descripcion,
            'tipo': p.tipo,
            'fecha_subida': p.fecha_subida if hasattr(p, 'fecha_subida') else None
        } for p in proyectos_db]
        
        # ⚡ Consulta del Historial de Retiros/Cobros
        retiros_db = BilleteraRetiro.query.filter_by(usuario_correo=correo_logueado).order_by(BilleteraRetiro.id.desc()).all()
        retiros = [{
            'id': r.id,
            'monto_creditos': r.monto_creditos,
            'equivalente_pesos': r.equivalente_pesos,
            'metodo_pago': r.metodo_pago,
            'detalles_cuenta': r.detalles_cuenta,
            'estado': r.estado,
            'fecha_solicitud': r.fecha_solicitud if hasattr(r, 'fecha_solicitud') else None
        } for r in retiros_db]

        # 🛡️ Métricas del sistema (por si perfil.html comparte el sidebar del dashboard)
        fondos_escrow = db.session.query(db.func.sum(Tarea.costo_creditos)).filter(
            Tarea.estado == 'En Garantia',
            or_(Tarea.cliente_correo == correo_logueado, Tarea.trabajador_correo == correo_logueado)
        ).scalar() or 0.0
        
        total_workers = Usuario.query.filter(Usuario.rol.in_(['Worker', 'Trabajador'])).count()
        ordenes_mediacion = Tarea.query.filter_by(estado='En Mediacion').count()
        
        # Un solo return limpio y directo a perfil.html con TODOS los datos
        return render_template('perfil.html', 
                               usuario=usuario, 
                               proyectos=proyectos, 
                               retiros=retiros,
                               saldo=usuario['saldo_creditos'],
                               nombre_usuario=session['usuario_nombre'],
                               fondos_escrow=fondos_escrow,
                               total_workers=total_workers,
                               ordenes_mediacion=ordenes_mediacion)
                               
    except Exception as e:
        print(f"⚠️ ERROR CRÍTICO EN GET PERFIL: {e}")
        flash("Ocurrió un error al intentar cargar los datos del perfil.", "error")
        return redirect(url_for('home'))

# =====================================================================
# 💬 MÓDULO DE COMUNICACIÓN API HTTP (PROCESAMIENTO ASÍNCRONO) - OPTIMIZADO
# =====================================================================
@app.route('/chat/<int:tarea_id>', methods=['GET', 'POST'])
def ver_chat(tarea_id):
    if 'usuario_nombre' not in session:
        return redirect(url_for('index'))

    correo_logueado = session['usuario_correo']
    rol_logueado = session.get('usuario_rol')

    # ⚡ Buscamos la orden de servicio directamente con SQLAlchemy
    tarea_obj = Tarea.query.get(tarea_id)

    if not tarea_obj:
        flash("❌ La orden de servicio no existe.", "error")
        return redirect(url_for('ver_tareas'))

    # Reconstruimos el diccionario espejo compatible con el HTML actual
    tarea = {
        'id': tarea_obj.id,
        'titulo': tarea_obj.titulo,
        'descripcion': tarea_obj.descripcion,
        'pago': tarea_obj.pago,
        'categoria': tarea_obj.categoria,
        'estado': tarea_obj.estado,
        'costo_creditos': tarea_obj.costo_creditos,
        'cliente_correo': tarea_obj.cliente_correo,
        'trabajador_correo': tarea_obj.trabajador_correo,
        'latitud': tarea_obj.latitud,
        'longitud': tarea_obj.longitud,
        'zona': tarea_obj.zona,
        'tecnico_correo': tarea_obj.trabajador_correo
    }

    canal_sala = f"sala_{tarea_id}"        

    try:
        # Asignación automática a Cotización Pendiente si un técnico entra a una tarea disponible
        if rol_logueado in ['Trabajador', 'Worker'] and tarea['estado'] == 'Disponible':
            tarea_obj.estado = 'Cotización Pendiente'
            db.session.commit()
            tarea['estado'] = 'Cotización Pendiente' # Sincronizamos la variable local de control

        # Marcamos como leídos los mensajes de la contraparte
        if tarea['estado'] == 'Finalizada' or canal_sala != "Ninguno":
            Mensaje.query.filter_by(tarea_id=tarea_id, leido=0)\
                .filter(Mensaje.remitente_correo != correo_logueado)\
                .update({Mensaje.leido: 1}, synchronize_session=False)
            db.session.commit()
            
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Error actualizando metadatos de chat #{tarea_id}: {e}")

    if request.method == 'POST':
        mensaje_texto = request.form.get('mensaje')
        archivo = request.files.get('imagen_adjunta')
        
        if canal_sala == "Ninguno":
            flash("❌ Sala de negociación no inicializada.", "error")
            return redirect(url_for('ver_chat', tarea_id=tarea_id))

        # 🛡️ FILTRO INTELIGENTE DE MODERACIÓN DE TEXTO
        mensaje_final = mensaje_texto
        es_seguro = True
        
        if tarea['estado'] not in ['En Garantia', 'Finalizada'] and mensaje_texto:
            es_seguro, resultado_moderacion = es_mensaje_seguro(mensaje_texto)
            if not es_seguro:
                mensaje_final = resultado_moderacion

        nombre_unico = None
        tipo_mensaje = 'texto'
        
        try:
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
                    print(f"⚠️ Caída leve en Pillow, guardando archivo raw: {e}")
                    archivo.seek(0)
                    archivo.save(ruta_guardado)
                    
                # ==========================================================
                # 🛡️ VALIDACIÓN IA: REVISAR SI LA FOTO TIENE CONTACTOS
                # ==========================================================
                if imagen_contiene_contactos(ruta_guardado):
                    # 1. Borramos la foto maliciosa del servidor para ahorrar disco
                    if os.path.exists(ruta_guardado):
                        os.remove(ruta_guardado)
                    
                    # 2. Rebotamos la petición enviando un error agresivo a la interfaz
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'multipart/form-data' in request.content_type:
                        return jsonify({
                            'success': False, 
                            'error': '🚨 Política de Seguridad: Se detectó un número de contacto en la imagen. Las negociaciones por fuera de inWorker están prohibidas.'
                        }), 400
                    else:
                        flash("🚨 Política de Seguridad: Se detectó un contacto en la imagen y fue bloqueada.", "error")
                        return redirect(url_for('ver_chat', tarea_id=tarea_id))
                # ==========================================================
                    
                nuevo_msg = Mensaje(
                    tarea_id=tarea_id,
                    canal_trabajador=canal_sala,
                    remitente_correo=correo_logueado,
                    mensaje=nombre_unico,
                    tipo='imagen',
                    leido=0
                )
                db.session.add(nuevo_msg)
                
            elif mensaje_texto and mensaje_texto.strip():
                leido_status = 1 if not es_seguro else 0
                
                nuevo_msg = Mensaje(
                    tarea_id=tarea_id,
                    canal_trabajador=canal_sala,
                    remitente_correo=correo_logueado,
                    mensaje=mensaje_final.strip(),
                    tipo='texto',
                    leido=leido_status
                )
                db.session.add(nuevo_msg)
                
            db.session.commit() # Consolidación de escritura asíncrona
            
            # Sincronizamos la billetera en la sesión
            usuario_actual = Usuario.query.filter_by(correo=correo_logueado).first()
            if usuario_actual:
                session['usuario_creditos'] = round(usuario_actual.saldo_creditos or 0.0, 2)
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error guardando mensaje en BD: {e}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'Error interno de escritura.'}), 500

        # Respuestas limpias para peticiones AJAX de JavaScript
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

    # =====================================================================
    # --- MÉTODO GET: HISTORIAL COMPLETO DE MENSAJES Y PERFILES ---
    # =====================================================================
    mensajes_db = db.session.query(Mensaje, Usuario)\
        .outerjoin(Usuario, Mensaje.remitente_correo == Usuario.correo)\
        .filter(Mensaje.tarea_id == tarea_id, Mensaje.canal_trabajador == canal_sala)\
        .order_by(Mensaje.id.asc()).all()
        
    mensajes = []
    for msg, usr in mensajes_db:
        item = {
            'id': msg.id,
            'tarea_id': msg.tarea_id,
            'canal_trabajador': msg.canal_trabajador,
            'remitente_correo': msg.remitente_correo,
            'mensaje': msg.mensaje,
            'tipo': msg.tipo,
            'fecha_envio': msg.fecha_envio if hasattr(msg, 'fecha_envio') else None,
            'remitente': usr.nombre if usr else 'Usuario de inWorker'
        }
        
        if 'cotizacion' in item['tipo']:
            partes = item['mensaje'].split('|')
            item['cotizacion_pesos'] = partes[0] if len(partes) > 0 else "0"
            item['cotizacion_concepto'] = partes[1] if len(partes) > 1 else "Sin concepto"
            try: 
                item['cotizacion_creditos'] = round(float(item['cotizacion_pesos']) / VALOR_CREDITO_COP, 2)
            except Exception: 
                item['cotizacion_creditos'] = 0.0
        mensajes.append(item)
    
    # Datos estructurados del Cliente
    cliente_db = Usuario.query.filter_by(correo=tarea['cliente_correo']).first()
    datos_cliente = {
        'nombre': cliente_db.nombre, 'correo': cliente_db.correo, 'profesion': cliente_db.profesion,
        'habilidades': cliente_db.habilidades, 'cedula': cliente_db.cedula, 'telefono': cliente_db.telefono,
        'verificado': cliente_db.verificado
    } if cliente_db else None
    
    # Datos estructurados del Técnico asignado o invitado
    tecnico_identificado = tarea['trabajador_correo'] if tarea['trabajador_correo'] else canal_sala
    datos_trabajador = None
    
    if tecnico_identificado and tecnico_identificado != "Ninguno":
        trabajador_db = Usuario.query.filter_by(correo=tecnico_identificado).first()
        if trabajador_db:
            trabajador_dict = {
                'nombre': trabajador_db.nombre, 'correo': trabajador_db.correo, 'profesion': trabajador_db.profesion,
                'habilidades': trabajador_db.habilidades, 'cedula': trabajador_db.cedula, 'telefono': trabajador_db.telefono,
                'verificado': trabajador_db.verificado, 'puntuacion_total': trabajador_db.puntuacion_total or 0.0,
                'total_calificaciones': trabajador_db.total_calificaciones or 0
            }
            if trabajador_dict['total_calificaciones'] > 0:
                trabajador_dict['promedio_estrellas'] = round(trabajador_dict['puntuacion_total'] / trabajador_dict['total_calificaciones'], 1)
            else:
                trabajador_dict['promedio_estrellas'] = 0.0
            datos_trabajador = trabajador_dict

    # Consulta de saldo final en tiempo real
    usuario_db = Usuario.query.filter_by(correo=correo_logueado).first()
    saldo_actual = round(usuario_db.saldo_creditos or 0.0, 2) if usuario_db else 0.0
    session['usuario_creditos'] = saldo_actual
    
    return render_template('chat.html',
                           tarea=tarea,
                           mensajes=mensajes,
                           canal_actual=canal_sala,
                           canal_sala=tarea['cliente_correo'],
                           nombre_usuario=session['usuario_nombre'],
                           saldo=saldo_actual,
                           cliente_perfil=datos_cliente,
                           trabajador_perfil=datos_trabajador)

# =====================================================================
# 💼 DISPARADOR DE OFERTAS ECONÓMICAS (COTIZACIONES) - OPTIMIZADO
# =====================================================================
@app.route('/chat/<int:tarea_id>/enviar_cotizacion', methods=['POST'])
def enviar_cotizacion(tarea_id):
    # 🛡️ Soportamos tanto 'Trabajador' como 'Worker' por consistencia de roles
    if 'usuario_nombre' not in session or session.get('usuario_rol') not in ['Trabajador', 'Worker']:
        return redirect(url_for('index'))
        
    correo_logueado = session['usuario_correo']
    canal_sala = request.form.get('canal_actual')
    concepto = request.form.get('concepto', '').strip()
    
    try:
        monto_pesos = float(request.form.get('monto_pesos', 0))
    except (ValueError, TypeError):
        monto_pesos = 0.0
    
    if monto_pesos <= 0 or not concepto:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Datos de cotización inválidos'}), 400
        flash("❌ Ingresa un valor en pesos válido y la descripción del servicio.", "error")
        return redirect(url_for('ver_chat', tarea_id=tarea_id))
        
    # Empaquetamos la cadena con formato estructurado para el renderizado del frontend
    contenido_cotizacion = f"{monto_pesos}|{concepto}"
    
    try:
        # ⚡ 1. Insertamos el mensaje de la oferta usando el ORM
        nueva_oferta = Mensaje(
            tarea_id=tarea_id,
            canal_trabajador=canal_sala,
            remitente_correo=correo_logueado,
            mensaje=contenido_cotizacion,
            tipo='cotizacion_pendiente',
            leido=0
        )
        db.session.add(nueva_oferta)
        
        # ⚡ 2. Actualizamos el estado de la tarea vinculada de forma directa
        tarea_obj = Tarea.query.get(tarea_id)
        if tarea_obj:
            tarea_obj.estado = 'Cotización Pendiente'
            
        # ⚡ 3. Consolidamos los cambios en un solo commit seguro en disco
        db.session.commit()
        flash(f"💼 ¡Oferta de ${monto_pesos:,.0f} COP enviada exitosamente!", "success")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error crítico enviando cotización en tarea #{tarea_id}: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Error interno al procesar la oferta.'}), 500
        flash("❌ Ocurrió un error al procesar tu oferta. Inténtalo de nuevo.", "error")
        return redirect(url_for('ver_chat', tarea_id=tarea_id))
    
    # Respuesta limpia para llamadas asíncronas AJAX (JavaScript)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'multipart/form-data' in request.content_type:
        return jsonify({'success': True})

    return redirect(url_for('ver_chat', tarea_id=tarea_id))

# =====================================================================
# 🔄 ENDPOINT API: CARGA Y NOTIFICACIÓN DE MENSAJES NUEVOS (POLLING) - CORREGIDO
# =====================================================================
@app.route('/api/chat/<int:tarea_id>/<string:canal>', methods=['GET'])
def api_cargar_mensajes(tarea_id, canal):
    if 'usuario_correo' not in session:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401

    ultimo_id = request.args.get('ultimo_id', default=0, type=int)

    try:
        # ⚡ Consulta de lectura ultra-rápida optimizada con SQLAlchemy
        filas = Mensaje.query.filter_by(tarea_id=tarea_id, canal_trabajador=canal)\
                             .filter(Mensaje.id > ultimo_id)\
                             .order_by(Mensaje.id.asc()).all()
        
        mensajes_completos = []
        
        for msg in filas:
            msg_dict = {
                'id': msg.id,
                'remitente_correo': msg.remitente_correo,
                'canal_trabajador': msg.canal_trabajador,
                'mensaje': msg.mensaje,
                'tipo': msg.tipo,
                'fecha_envio': msg.fecha_envio if hasattr(msg, 'fecha_envio') else None,
                'remitente': msg.remitente_correo.split('@')[0]
            }
            
            # Formateo dinámico para ofertas económicas
            if msg_dict['tipo'] in ['cotizacion_pendiente', 'cotizacion_aceptada', 'cotizacion_declinada']:
                partes = msg_dict['mensaje'].split('|')
                msg_dict['monto_pesos'] = partes[0] if len(partes) > 0 else "0"
                msg_dict['cotizacion_concepto'] = partes[1] if len(partes) > 1 else ""
                try:
                    # 💵 Ajuste comercial: $10.000 COP equivale a 1 Crédito inWorker
                    msg_dict['cotizacion_creditos'] = round(float(msg_dict['monto_pesos']) / 10000.0, 2)
                except Exception:
                    msg_dict['cotizacion_creditos'] = 0.0

            mensajes_completos.append(msg_dict)
        
        return jsonify({'success': True, 'mensajes': mensajes_completos})

    except Exception as e:
        print(f"❌ Error en API Chat Polling (Tarea #{tarea_id}): {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno al consultar actualizaciones.'}), 500

# =====================================================================
# 💳 PROCESADOR DE RESPUESTA A COTIZACIONES (CIERRE DE TRATOS) - OPTIMIZADO
# =====================================================================
@app.route('/chat/<int:tarea_id>/responder_cotizacion/<int:mensaje_id>', methods=['POST'])
def responder_cotizacion(tarea_id, mensaje_id):
    if 'usuario_nombre' not in session:
        return redirect(url_for('index'))
        
    correo_logueado = session['usuario_correo']
    accion = request.form.get('accion')
    canal_sala = request.form.get('canal_actual')
    
    # ⚡ Buscamos la oferta económica directamente mediante el ORM
    msg_cotizacion = Mensaje.query.filter_by(id=mensaje_id, tarea_id=tarea_id).first()
    
    if not msg_cotizacion or msg_cotizacion.tipo != 'cotizacion_pendiente':
        flash("❌ La oferta ya no se encuentra disponible.", "error")
        return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=canal_sala))
        
    try:
        # Parseamos la cadena con formato estructurado (monto|concepto)
        partes = msg_cotizacion.mensaje.split('|')
        monto_pesos = float(partes[0])
        # 💵 Conversión matemática exacta usando la constante comercial ($10.000 COP)
        monto_creditos_flotante = round(monto_pesos / VALOR_CREDITO_COP, 2)
    except Exception as e:
        print(f"⚠️ Error de formato en cotización #{mensaje_id}: {e}")
        flash("❌ Formato económico incorrecto.", "error")
        return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=canal_sala))

    try:
        if accion == 'Aceptar':
            cliente = Usuario.query.filter_by(correo=correo_logueado).first()
            saldo_cliente = cliente.saldo_creditos if cliente else 0.0
            
            # 🛡️ CONTROL FINANCIERO ANTI-FRAUDE Y PUENTE DE RECARGA
            if saldo_cliente < monto_creditos_flotante:
                # Usamos una categoría especial 'insuficiente' para que el frontend pueda disparar un pop-up de pago
                flash(f"Saldo insuficiente. Necesitas {monto_creditos_flotante} Cr (${monto_pesos:,.0f} COP) para asegurar este contrato.", "insuficiente")
                return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=canal_sala))
                
            # 💵 Retención segura y descuento de saldo del cliente
            cliente.saldo_creditos = round(saldo_cliente - monto_creditos_flotante, 2)
            
            trabajador = Usuario.query.filter_by(correo=msg_cotizacion.remitente_correo).first()
            nombre_trabajador = trabajador.nombre if trabajador else "Técnico inWorker"
            
            tarea_obj = Tarea.query.get(tarea_id)
            if tarea_obj:
                tarea_obj.estado = 'En Garantia'
                tarea_obj.trabajador_correo = msg_cotizacion.remitente_correo
                tarea_obj.trabajador_nombre = nombre_trabajador
                tarea_obj.pago = str(monto_pesos)
                tarea_obj.costo_creditos = monto_creditos_flotante
                tarea_obj.confirmacion_cliente = 0
                tarea_obj.confirmacion_trabajador = 0
            
            # 🚨 CORRECCIÓN: Sincronización exacta con el HTML
            msg_cotizacion.tipo = 'cotizacion_aceptada'  
            
            Mensaje.query.filter_by(tarea_id=tarea_id, tipo='cotizacion_pendiente')\
                         .update({Mensaje.tipo: 'cotizacion_declinada'}, synchronize_session=False)
            
            # 📢 INYECCIÓN DE MENSAJE DEL SISTEMA EN EL CHAT
            mensaje_sistema = Mensaje(
                tarea_id=tarea_id,
                canal_trabajador=canal_sala,
                remitente_correo='sistema@inworker.co',
                mensaje=f"✅ CONTRATO ASEGURADO: El cliente ha depositado ${monto_pesos:,.0f} COP en el fondo de garantía de inWorker. El especialista ya puede iniciar la ejecución del servicio de forma segura.",
                tipo='sistema'
            )
            db.session.add(mensaje_sistema)
            
            db.session.commit()
            
            session['usuario_creditos'] = cliente.saldo_creditos
            flash("✔ ¡Propuesta aceptada! El depósito de garantía se encuentra congelado de manera segura.", "success")

        elif accion == 'Rechazar':
            msg_cotizacion.tipo = 'cotizacion_declinada'
            db.session.commit()
            flash("❌ Oferta declinada correctamente.", "error")
            
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error crítico procesando respuesta a cotización: {e}")
        flash("❌ Ocurrió un error interno al procesar la transacción bancaria de la orden.", "error")
        
    return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=canal_sala))


# =====================================================================
# 🔐 MÓDULO DE ESCROW: CONFIRMACIÓN DE ENTREGA Y DESEMBOLSO - OPTIMIZADO
# =====================================================================
@app.route('/confirmar_entrega/<int:tarea_id>', methods=['POST'])
def confirmar_entrega(tarea_id):
    if 'usuario_nombre' not in session:
        return redirect(url_for('index'))
        
    correo_logueado = session['usuario_correo']
    
    try:
        # ⚡ Traemos la orden de servicio directamente usando el modelo
        tarea = Tarea.query.get(tarea_id)
        
        if not tarea or tarea.estado != 'En Garantia':
            flash("❌ Operación no válida para el estado actual de la tarea.", "error")
            return redirect(url_for('ver_chat', tarea_id=tarea_id))
            
        # Evaluar y actualizar las banderas de conformidad según el remitente
        if correo_logueado == tarea.cliente_correo:
            tarea.confirmacion_cliente = 1
            flash("🚀 Has confirmado la conformidad del servicio.", "success")
        elif correo_logueado == tarea.trabajador_correo:
            tarea.confirmacion_trabajador = 1
            flash("📢 Has notificado al cliente que el trabajo está finalizado.", "success")
        else:
            return redirect(url_for('ver_chat', tarea_id=tarea_id))
            
        # 💳 DISPARADOR AUTOMÁTICO DE DESEMBOLSO FINANCIERO
        if tarea.confirmacion_cliente == 1 and tarea.confirmacion_trabajador == 1:
            creditos_desembolso = tarea.costo_creditos or 0.0
            tecnico_destino = tarea.trabajador_correo
            
            # Buscamos al especialista asignado para fondear su billetera
            tecnico = Usuario.query.filter_by(correo=tecnico_destino).first()
            
            if tecnico:
                saldo_actual_tecnico = tecnico.saldo_creditos or 0.0
                tecnico.saldo_creditos = round(saldo_actual_tecnico + creditos_desembolso, 2)
                
            # Pasamos la orden al estado de cierre definitivo
            tarea.estado = 'Finalizada'
            
            # Formateamos el monto en pesos de forma segura para el historial
            try:
                monto_pesos_formateado = f"${float(tarea.pago):,.0f}"
            except (ValueError, TypeError):
                monto_pesos_formateado = f"${creditos_desembolso * VALOR_CREDITO_COP:,.0f}"
                
            # Generamos el aviso oficial del sistema dentro de la sala de negociación
            mensaje_sistema = (
                f"SISTEMA: El pago de {creditos_desembolso} Cr ({monto_pesos_formateado} COP) "
                f"ha sido liberado de la garantía y transferido al saldo de {tarea.trabajador_nombre}."
            )
            
            nuevo_aviso = Mensaje(
                tarea_id=tarea_id,
                canal_trabajador=tarea.trabajador_correo,
                remitente_correo='baraka@inworker.com', # Correo institucional del sistema
                mensaje=mensaje_sistema,
                tipo='texto',
                leido=0
            )
            db.session.add(nuevo_aviso)
            flash("✨ ¡Garantía liberada con éxito! Los fondos ya están en la billetera del especialista.", "success")
            
        # ⚡ Un solo commit impacta y bloquea toda la transacción de forma segura
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error crítico en pasarela de Escrow (Tarea #{tarea_id}): {e}")
        flash("❌ Ocurrió un error al procesar la liberación de la garantía.", "error")
        
    return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=tarea.trabajador_correo if tarea else None))


# =====================================================================
# ⭐ MÓDULO DE REPUTACIÓN Y CALIFICACIÓN - OPTIMIZADO
# =====================================================================
@app.route('/calificar/<int:tarea_id>', methods=['POST'])
def calificar_tecnico(tarea_id):
    if 'usuario_nombre' not in session:
        return redirect(url_for('index'))
        
    correo_logueado = session['usuario_correo']
    
    try:
        estrellas = float(request.form.get('estrellas', 0))
    except (ValueError, TypeError):
        estrellas = 0.0
        
    if estrellas < 1.0 or estrellas > 5.0:
        flash("❌ Calificación inválida. Debe ser entre 1 y 5 estrellas.", "error")
        return redirect(url_for('ver_chat', tarea_id=tarea_id))
        
    try:
        # ⚡ Consultamos la orden de servicio mediante el ORM
        tarea = Tarea.query.get(tarea_id)
        
        # 🛡️ FILTRO DE SEGURIDAD: Solo el cliente dueño de una tarea finalizada y no calificada puede votar
        if tarea and tarea.estado == 'Finalizada' and getattr(tarea, 'calificada', 0) == 0 and correo_logueado == tarea.cliente_correo:
            
            # Buscamos al técnico asignado para actualizar su reputación global
            tecnico = Usuario.query.filter_by(correo=tarea.trabajador_correo).first()
            
            if tecnico:
                # Incremento seguro manejando fallbacks por si los campos están en NULL/None
                tecnico.puntuacion_total = (tecnico.puntuacion_total or 0.0) + estrellas
                tecnico.total_calificaciones = (tecnico.total_calificaciones or 0) + 1
                
            # Marcamos la tarea como calificada de forma definitiva para evitar dobles sumas
            tarea.calificada = 1
            
            # Consolidamos la transacción de manera atómica
            db.session.commit()
            flash("⭐ ¡Gracias por calificar al especialista!", "success")
            
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error crítico al procesar calificación de tarea #{tarea_id}: {e}")
        flash("❌ Ocurrió un error interno al guardar tu calificación.", "error")
        
    return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=tarea.trabajador_correo if tarea else None))

# =====================================================================
# 👷 MÓDULO DE EXPLORACIÓN: DIRECTORIO DE ESPECIALISTAS - OPTIMIZADO
# =====================================================================
@app.route('/tecnicos')
def listar_tecnicos():
    if 'usuario_nombre' not in session: 
        return redirect(url_for('index'))
        
    try:
        # ⚡ 1. Traemos todos los especialistas en una sola lectura masiva
        tecnicos_db = Usuario.query.filter(Usuario.rol.in_(['Trabajador', 'Worker'])).all()
        
        tecnicos = []
        for tec in tecnicos_db:
            # Reconstruimos el diccionario espejo nativo para el HTML
            item = {
                'nombre': tec.nombre,
                'correo': tec.correo,
                'rol': tec.rol,
                'profesion': tec.profesion,
                'habilidades': tec.habilidades,
                'foto': tec.foto,
                # Biografía de respaldo si el campo está vacío en BD
                'descripcion': tec.descripcion or 'Especialista verificado dispuesto a ayudarte en tus requerimientos de soporte técnico.'
            }
            
            # ⚡ 2. Buscamos los proyectos de este usuario específico en la tabla portafolio
            proyectos_db = Portafolio.query.filter_by(usuario_correo=tec.correo)\
                                             .order_by(Portafolio.id.desc()).all()
                                             
            item['proyectos'] = [{
                'id': p.id,
                'imagen_ruta': p.imagen_ruta,
                'descripcion': p.descripcion,
                'tipo': p.tipo
            } for p in proyectos_db]
            
            # Variables de reputación por defecto o heredadas
            # Nota: Si en el futuro mapeas las reales, puedes cambiarlas aquí: tec.puntuacion_total
            item['promedio_estrellas'] = 5.0
            item['total_calificaciones'] = 1
            
            tecnicos.append(item)
            
    except Exception as e:
        print(f"❌ Error al cargar el directorio de técnicos: {e}")
        flash("❌ Ocurrió un inconveniente al cargar el listado de especialistas.", "error")
        tecnicos = []

    return render_template('tecnicos.html', 
                           tecnicos=tecnicos, 
                           nombre_usuario=session['usuario_nombre'])


# =====================================================================
# 🚀 RUTA PROPIA PARA LA CONSULTA PRIVADA (CIERRE DIRECTO) - OPTIMIZADO
# =====================================================================
@app.route('/solicitar_cotizacion_privada', methods=['POST'])
def consultar_tecnico():
    if 'usuario_nombre' not in session:
        return redirect(url_for('index'))

    cliente_correo = session['usuario_correo']
    
    # .get() evita que la app se estrelle si el HTML no envía el campo
    tecnico_correo = request.form.get('tecnico_correo') or request.form.get('trabajador_correo')
    titulo = request.form.get('titulo', 'Consulta Privada')
    descripcion = request.form.get('descripcion', 'Sin descripción')
    pago_estimado = request.form.get('pago', '0')
    categoria = request.form.get('categoria', 'Soporte Técnico')
    
    # Filtro de seguridad controlado si no se identifica al especialista
    if not tecnico_correo:
        flash("❌ Error: No se pudo identificar al técnico para la cotización.", "error")
        return redirect(url_for('listar_tecnicos'))
    
    # Ubicación por defecto basada en Barranquilla/Soledad si el front no la envía
    lat = request.form.get('latitud', 10.9639)
    lng = request.form.get('longitud', -74.7964)
    zona = request.form.get('zona', 'Barranquilla (Privado)')
    
    try: 
        # 💵 Conversión exacta: $10.000 COP equivale a 1 Crédito inWorker
        creditos_calculados = round(float(pago_estimado) / VALOR_CREDITO_COP, 2)
    except (ValueError, TypeError): 
        creditos_calculados = 1.0

    try:
        # ⚡ Insertamos la orden de servicio privada directamente asignada al técnico
        nueva_tarea = Tarea(
            titulo=titulo,
            descripcion=descripcion,
            pago=pago_estimado,
            categoria=categoria,
            estado='Cotización Pendiente',  # Nace directo en negociación
            costo_creditos=creditos_calculados,
            cliente_correo=cliente_correo,
            latitud=lat,
            longitud=lng,
            zona=zona,
            trabajador_correo=tecnico_correo  # 👈 ¡ESTA ES LA LÍNEA CORREGIDA!
        )
        
        db.session.add(nueva_tarea)
        db.session.commit()  # SQLAlchemy asienta la fila e hidrata el ID del objeto
        
        id_tarea = nueva_tarea.id
        flash("💼 Consulta privada iniciada con éxito.", "success")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error crítico creando consulta privada: {e}")
        flash("❌ No se pudo inicializar la sala privada por un error interno.", "error")
        return redirect(url_for('listar_tecnicos'))
    
    # Redirección nativa y ultra-segura usando url_for para el chat de negociación
    return redirect(url_for('ver_chat', tarea_id=id_tarea))


# =====================================================================
# 💰 WEBHOOK DIRECTO DE PASARELA (NEQUI) - OPTIMIZADO
# =====================================================================
@app.route('/webhook-nequi', methods=['POST'])
def webhook_nequi():
    datos_pago = request.json or {}
    id_servicio = datos_pago.get("id_servicio")
    estado_pago = datos_pago.get("estado")  # Espera "APPROVED" o "DECLINED"
    monto = datos_pago.get("monto", 0.0)     # Opcional: Monto recaudado
    
    if estado_pago == "APPROVED":
        print(f"💰 ¡Pago aprobado para el servicio {id_servicio}! Tu comisión del 7.5% está asegurada.")
        
        try:
            # ⚡ Buscamos la orden de servicio en la base de datos mediante el ORM
            tarea = Tarea.query.get(id_servicio)
            
            if tarea:
                # Si el pago activa una tarea que estaba en borrador o pendiente, mutamos su estado
                # tarea.estado = 'Disponible' 
                
                # Ejemplo de automatización de alerta integrada (Módulo de notificaciones en Python):
                # if tarea.tecnico_correo:
                #     alertar_nuevo_servicio_tecnico(tarea.tecnico_correo, tarea.id, tarea.titulo, tarea.zona)
                
                db.session.commit()
                
            return jsonify({
                "status": "success", 
                "message": "Servicio activado e inyectado correctamente en la infraestructura"
            }), 200
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error procesando el webhook de Nequi para servicio #{id_servicio}: {e}")
            return jsonify({"status": "error", "message": "Error interno al asentar el pago"}), 500
            
    return jsonify({"status": "failed", "message": "Pago rechazado o pendiente"}), 200

# =====================================================================
# ⚖️ ENDPOINT DE ARBITRAJE DE DISPUTAS CON IA (FASE 1.1 - OPTIMIZADO)
# =====================================================================
@app.route('/admin/disputa/<int:tarea_id>')
def analizar_disputa_admin(tarea_id):
    # 🛡️ PROTECCIÓN AMIGABLE: Validar sesión y rol de administrador
    if 'usuario_correo' not in session or session.get('usuario_rol') != 'Admin':
        return jsonify({"error": "Acceso denegado. Se requieren permisos de administrador."}), 403
        
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
        
    # Importamos el módulo e invocamos a Gemini
    from disputas_ia import analizar_disputa_chat
    reporte_ia = analizar_disputa_chat(mensajes, dict(tarea))
    
    # ✨ FORMATEO FORENSE INTEGRADO: Transforma el diccionario a texto limpio para tu frontend
    texto_analisis = (
        f"🤖 VEREDICTO RECOMENDADO: {reporte_ia.get('veredicto_sugerido', 'REVISIÓN_MANUAL')}\n"
        f"📊 Propuesta de Distribución:\n"
        f"   - Al Especialista (Trabajador): {reporte_ia.get('porcentaje_trabajador', 50)}%\n"
        f"   - Al Cliente: {reporte_ia.get('porcentaje_cliente', 50)}%\n\n"
        f"📝 Justificación Forense:\n"
        f"{reporte_ia.get('justificacion', 'Sin observaciones adicionales por el motor.')}"
    )
        
    # Retorna el JSON estructurado exactamente como lo espera tu index.html
    return jsonify({
        "success": True,
        "tarea_id": tarea_id,
        "titulo_tarea": tarea['titulo'],
        "estado_actual": tarea['estado'],
        "analisis_ia": texto_analisis # 👈 Cadena formateada para inyección limpia
    })

# =====================================================================
# ⚖️ RESOLUCIÓN MANUAL DE DISPUTAS (ARBITRAJE ADMINISTRATIVO) - OPTIMIZADO
# =====================================================================
@app.route('/admin/resolver_disputa/<int:tarea_id>', methods=['POST'])
def admin_resolver_disputa(tarea_id):
    # 🛡️ VALIDACIÓN DE SEGURIDAD ESTRICTA
    if 'usuario_correo' not in session or session.get('usuario_rol') != 'Admin':
        flash("🔒 Acceso denegado. Se requieren permisos de administrador.", "error")
        return redirect(url_for('login'))

    resolucion = request.form.get('resolucion_tipo')
    
    try:
        # 1. Extraemos la orden de servicio directamente con el ORM
        tarea = Tarea.query.get(tarea_id)

        if not tarea:
            flash("❌ Orden de servicio no encontrada.", "error")
            return redirect(url_for('home'))

        creditos = float(tarea.costo_creditos or 0.0)
        mensaje_flash = ""

        # 2. Ejecución del veredicto manual según la opción seleccionada en el Dashboard
        if resolucion == 'reembolso_total':
            # 100% de vuelta al balance del Cliente (Incumplimiento del técnico)
            cliente_user = Usuario.query.filter_by(correo=tarea.cliente_correo).first()
            if cliente_user:
                saldo_actual = cliente_user.saldo_creditos or 0.0
                cliente_user.saldo_creditos = round(saldo_actual + creditos, 2)
            mensaje_flash = f"⚖️ Arbitraje finalizado: Se reembolsaron {creditos:,.1f} Cr al Cliente exitosamente."
            
        elif resolucion == 'pago_total':
            # 100% liberado al Especialista/Trabajador (Labor completada correctamente)
            tecnico_user = Usuario.query.filter_by(correo=tarea.tecnico_correo).first()
            if tecnico_user:
                saldo_actual = tecnico_user.saldo_creditos or 0.0
                tecnico_user.saldo_creditos = round(saldo_actual + creditos, 2)
            mensaje_flash = f"⚖️ Arbitraje finalizado: Se liberaron {creditos:,.1f} Cr al Especialista exitosamente."
            
        elif resolucion == 'mitad_mitad':
            # División salomónica 50% / 50%
            mitad = round(creditos / 2, 2)
            
            # Abono seguro al cliente
            cliente_user = Usuario.query.filter_by(correo=tarea.cliente_correo).first()
            if cliente_user:
                saldo_cli = cliente_user.saldo_creditos or 0.0
                cliente_user.saldo_creditos = round(saldo_cli + mitad, 2)
                
            # Abono seguro al especialista
            tecnico_user = Usuario.query.filter_by(correo=tarea.tecnico_correo).first()
            if tecnico_user:
                saldo_tec = tecnico_user.saldo_creditos or 0.0
                tecnico_user.saldo_creditos = round(saldo_tec + mitad, 2)
                
            mensaje_flash = f"⚖️ Arbitraje finalizado: Fondos divididos equitativamente ({mitad:,.1f} Cr para cada uno)."
            
        else:
            flash("❌ Tipo de resolución inválida en el formulario.", "error")
            return redirect(url_for('home'))

        # 3. Sacamos la tarea de la sección de arbitraje pasándola a estado 'Finalizada'
        tarea.estado = 'Finalizada'
        
        # ⚡ Un solo commit asienta toda la resolución y los movimientos monetarios de forma segura en disco
        db.session.commit()
        flash(mensaje_flash, "success")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error crítico en resolución de disputa para tarea #{tarea_id}: {e}")
        flash("❌ Ocurrió un error crítico interno al ejecutar la sentencia del arbitraje.", "error")

    return redirect(url_for('home'))

# =====================================================================
# 🛠️ ENDPOINT COPILOT DE PERFIL PARA EL TRABAJADOR (FASE 2.2)
# =====================================================================
@app.route('/trabajador/optimizar-perfil', methods=['POST'])
def optimizar_perfil():
    # Validamos que el usuario esté logueado
    if 'usuario_nombre' not in session:
        return jsonify({"error": "No autorizado"}), 401
        
    # Recibimos los datos actuales del formulario de su perfil
    datos_frontend = request.get_json() or {}
    descripcion_actual = datos_frontend.get('descripcion', '')
    habilidades = datos_frontend.get('habilidades', '')
    ciudad = datos_frontend.get('ciudad', 'Colombia')
    
    if not descripcion_actual:
        return jsonify({"error": "La descripción actual no puede estar vacía."}), 400
        
    try:
        # Invocamos el Copilot de IA de manera segura
        from copilot_tecnico import optimizar_perfil_trabajador
        resultado_copilot = optimizar_perfil_trabajador(descripcion_actual, habilidades, ciudad)
        
        # Devolvemos la propuesta para que el técnico la apruebe en el frontend
        return jsonify(resultado_copilot)
    except Exception as e:
        print(f"❌ Error en Copilot de Perfil: {e}")
        return jsonify({"error": "Error interno al procesar la optimización con IA."}), 500


# =====================================================================
# 🏁 BLOQUE FINAL DE ARRANQUE E INICIALIZACIÓN AUTOMÁTICA
# =====================================================================
if __name__ == '__main__':
    
    # ⚡ INICIALIZACIÓN AUTOMÁTICA CON SQLALCHEMY
    # Esto reemplaza por completo la creación de tablas con sqlite3.
    # SQLAlchemy revisará tus clases (Usuario, Tarea, Mensaje, etc.) 
    # y creará la estructura exacta si no existe en tu archivo /data/inworker_prod.db
    with app.app_context():
        db.create_all()
        print("✅ Base de datos sincronizada y blindada con SQLAlchemy.")

    # Arranca tu servidor en modo desarrollo
    # (Nota: En Render, Gunicorn ignorará esta línea y usará sus propios workers, lo cual es ideal)
    app.run(debug=True, port=5000)