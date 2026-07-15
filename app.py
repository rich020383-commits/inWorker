import os
import re
import math
import time
import threading
import hashlib
import random  # 🥷 Inyectado para Sistema de Embajadores
import string  # 🥷 Inyectado para Sistema de Embajadores
from PIL import Image
from google import genai
from moderacion import es_mensaje_seguro
from disputas_ia import analizar_disputa_chat

# 🔧 CONFIGURACIÓN AVANZADA CON FLASK-SQLALCHEMY
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, current_app, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, text
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash 
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

# Inicialización de la App
ruta_actual = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(ruta_actual, "templates"))
app.secret_key = "llave_ultra_secreta_2026"

# Cliente Gemini
client = genai.Client()

# 📧 CONFIGURACIÓN DE FLASK-MAIL Y SUBIDAS
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
serializer = URLSafeTimedSerializer(app.secret_key)

# 📸 CONFIGURACIÓN Y VALIDACIÓN DE IMÁGENES PERMITIDAS
EXTENSIONES_PERMITIDAS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = os.path.join(ruta_actual, 'static', 'uploads')

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def archivo_permitido(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in EXTENSIONES_PERMITIDAS

# =====================================================================
# 🤝 SISTEMA DE EMBAJADORES (LÓGICA CORE)
# =====================================================================
def generar_codigo_embajador():
    """Genera un código alfanumérico único de 6 caracteres (Ej: A1B2C3)."""
    letras = string.ascii_uppercase + string.digits
    return ''.join(random.choice(letras) for i in range(6))

# =====================================================================
# 🛡️ IA DE MODERACIÓN VISUAL (GEMINI VISION)
# =====================================================================
def imagen_contiene_contactos(ruta_imagen):
    """
    Uusa Gemini Vision para leer el texto de la foto y detectar si intentan 
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

# =====================================================================
# 📧 ENVÍO DE CORREOS EN SEGUNDO PLANO
# =====================================================================
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
                        <a href="https://inworker.co/dashboard" style="background-color: #0052cc; color: white; padding: 12px 25px; text-align: center; text-decoration: none; font-weight: bold; border-radius: 5px;">Ingresar a mi Cuenta</a>
                    </div>
                    <p style="font-size: 12px; color: #777777;">Si tienes alguna duda o inconveniente, responde a este correo y nuestro equipo de soporte te atenderá de inmediato.</p>
                </div>
                <div style="background-color: #f9f9f9; padding: 15px; text-align: center; font-size: 12px; color: #999999; border-top: 1px solid #e0e0e0;">
                    © 2026 inWorker. Todos los derechos reservados.
                </div>
            </div>
            """
            mail.send(msg)
            print(f"📧 Correo de bienvenida enviado con éxito en segundo plano a: {correo_destino}")
        except Exception as e:
            print(f"❌ Error real en el envío del correo de bienvenida por SMTP: {e}")

def enviar_notificacion_asignacion(app_contexto, correo_destino, nombre_tecnico, titulo_tarea):
    """ Envía un correo premium al técnico cuando recibe una solicitud directa """
    with app_contexto.app_context():
        try:
            msg = Message(
                f'🔥 ¡Nueva Asignación en inWorker! - {titulo_tarea}',
                recipients=[correo_destino]
            )
            msg.html = f"""
            <html>
                <body style="font-family: 'Arial', sans-serif; background-color: #f8fafc; padding: 20px;">
                    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 30px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                        <h2 style="color: #2563eb; margin-bottom: 5px; font-weight: 900;">¡Hola, {nombre_tecnico}!</h2>
                        <p style="color: #475569; font-size: 16px; line-height: 1.5;">Tienes una nueva asignación o solicitud de cotización esperándote en <strong>inWorker</strong>.</p>
                        
                        <div style="background-color: #f1f5f9; padding: 20px; border-radius: 10px; margin: 25px 0; border-left: 4px solid #2563eb;">
                            <h3 style="color: #1e293b; margin-top: 0; margin-bottom: 5px; font-size: 18px;">{titulo_tarea}</h3>
                            <p style="color: #64748b; margin-bottom: 0; font-size: 14px;">Un cliente te ha seleccionado directamente. Entra ahora para enviar tu cotización antes de que busque a otro especialista.</p>
                        </div>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="https://inworker.co/dashboard" style="display: inline-block; background-color: #2563eb; color: white; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: bold; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">
                                Ir a la Sala de Negociación
                            </a>
                        </div>
                        
                        <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 30px 0 20px 0;">
                        <p style="color: #94a3b8; font-size: 11px; text-align: center;">Este es un mensaje automático del ecosistema inWorker. Por favor no respondas a este correo.</p>
                    </div>
                </body>
            </html>
            """
            mail.send(msg)
            print(f"📧 Alerta de asignación enviada con éxito a: {correo_destino}")
        except Exception as e:
            print(f"❌ Error en el envío de alerta al técnico: {e}")

# ========================================================
# 📦 REDIRECCIÓN DE BASE DE DATOS (PRODUCCIÓN Y LOCAL)
# ========================================================
# Busca la variable de entorno DATABASE_URL (Supabase en Render). 
# Si no la encuentra (como en tu PC local), usa SQLite por defecto.
uri = os.environ.get("DATABASE_URL", "sqlite:///inworker_prod.db")

# Ajuste crítico de compatibilidad para PostgreSQL en SQLAlchemy
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
    kyc_cedula = db.Column(db.String(255), nullable=True)
    kyc_selfie = db.Column(db.String(255), nullable=True)
    telefono = db.Column(db.String(50), default='Sin especificar')
    verificado = db.Column(db.Integer, default=0)
    saldo_creditos = db.Column(db.Float, default=0.0) # Inician en 0 Cr
    puntuacion_total = db.Column(db.Float, default=0.0)
    total_calificaciones = db.Column(db.Integer, default=0)
    descripcion = db.Column(db.Text, default='')
    
    # 🤝 SISTEMA DE EMBAJADORES Y REFERIDOS (PROGRAMA DE CRECIMIENTO)
    codigo_embajador = db.Column(db.String(50), unique=True, nullable=True) 
    referido_por = db.Column(db.String(50), nullable=True) 
    fecha_registro = db.Column(db.DateTime, default=db.func.current_timestamp())
    servicios_red = db.Column(db.Integer, default=0)
    nivel_embajador = db.Column(db.Integer, default=1)

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
    
    # 📍 NUEVAS COORDENADAS POR DEFECTO: BOGOTÁ, D.C.
    latitud = db.Column(db.Float, default=4.6097)
    longitud = db.Column(db.Float, default=-74.0817)
    
    confirmacion_cliente = db.Column(db.Integer, default=0)
    confirmacion_trabajador = db.Column(db.Integer, default=0)
    calificada = db.Column(db.Integer, default=0)
    
    # 🏙️ ZONA ESTÁNDAR ACTUALIZADA
    zona = db.Column(db.String(100), default='Bogotá, D.C.')

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
    comprobante_pago = db.Column(db.String(255), nullable=True)

class Recarga(db.Model):
    __tablename__ = 'recargas'
    id = db.Column(db.Integer, primary_key=True)
    usuario_correo = db.Column(db.String(120), nullable=False)
    monto_cop = db.Column(db.Float, nullable=False)
    creditos = db.Column(db.Float, nullable=False)
    comprobante = db.Column(db.String(255), nullable=False)
    metodo = db.Column(db.String(50), default='Nequi')
    estado = db.Column(db.String(50), default='Pendiente') # Pendiente, Aprobada, Rechazada
    # Usamos db.func.current_timestamp() para mantener la coherencia con tus otras tablas
    fecha = db.Column(db.DateTime, default=db.func.current_timestamp())


# ========================================================
# 🚀 EJECUCIÓN DEL CONTEXTO Y SEEDING DE SEGURIDAD
# ========================================================
with app.app_context():
    # 1. Crea automáticamente el archivo físico dentro del SSD (/data/) con las tablas indexadas
    db.create_all()
    print("¡Estructura de Base de Datos persistente e indexada montada con éxito!")
    
    # ⚡ INICIO DEL PARCHE DE MIGRACIÓN KYC: Forzar actualización de columnas en Render
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE usuarios ADD COLUMN kyc_cedula VARCHAR(255)"))
            conn.commit()
            print("✅ Columna 'kyc_cedula' inyectada con éxito en la base de datos persistente.")
    except Exception:
        pass # Si falla, significa que la columna ya existe, lo ignoramos

    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE usuarios ADD COLUMN kyc_selfie VARCHAR(255)"))
            conn.commit()
            print("✅ Columna 'kyc_selfie' inyectada con éxito en la base de datos persistente.")
    except Exception:
        pass # Si falla, significa que la columna ya existe, lo ignoramos
    # ⚡ FIN DEL PARCHE
    
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

from flask import request, jsonify
import time

# =========================================================================
# 🧠 ENDPOINT UPWARD AI: Auto-Redactor REAL con Gemini API
# =========================================================================
@app.route('/api/ia/redactar', methods=['POST'])
def api_ia_redactar():
    if 'usuario_correo' not in session:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
        
    data = request.get_json()
    texto_cliente = data.get('texto', '')
    
    if not texto_cliente:
        return jsonify({'success': False, 'error': 'Texto vacío'}), 400

    try:
        # 1. El Prompt Maestro de Upward AI (¡ACTUALIZADO CON EL NUEVO ECOSISTEMA!)
        prompt_maestro = f"""
        Eres Upward AI, el asistente experto de inWorker (un marketplace integral de servicios técnicos, profesionales y de bienestar).
        Un cliente ha descrito su problema o necesidad de forma muy básica o informal:
        "{texto_cliente}"
        
        Tu tarea:
        1. Reescribe esta necesidad en un lenguaje profesional, claro y directo (máximo 2 párrafos cortos), listo para ser publicado como una orden de trabajo o solicitud de servicio.
        2. Al final del texto, agrega un salto de línea y sugiere OBLIGATORIAMENTE cuál de las siguientes categorías exactas debe elegir el cliente en el formulario (debes elegir la que mejor se adapte):
        [Abogado Penal, Abogado Laboral, Abogado de Familia, Contabilidad y Finanzas, Asesoría Tributaria, Trámites Legales, Clases de Matemáticas, Clases de Idiomas, Clases de Música, Refuerzo Escolar, Tutoría Universitaria, Manicure y Pedicure, Keratinas y Alisados, Maquillaje Profesional, Barbería y Corte, Masajes Relajantes, Plomería, Electricidad, Construcción, Maestro de obras, Pintura, Carpintería, Ebanistería, Remodelación, Techos y cubiertas, Pisos y revestimientos, Impermeabilización, Fumigación, Cerrajería, Aire acondicionado, Calentadores de agua, Bombas de agua, Ventanas y puertas, Vidriería, Soldadura, Herrería, Gypsum / Drywall, Servicio de gas, Reparación de electrodomésticos, Ingeniería civil, Ingeniería eléctrica, Ingeniería mecánica, Arquitectura, Topografía, Control de plagas, Captación y reúso de agua, Muralismo, Soporte Técnico, Instalación de Cámaras (CCTV), Redes y Telecomunicaciones, Desarrollo Web, Niñera / Cuidado Infantil, Asistencia a Personas Mayores, Paseador y Cuidador de Perros, Enfermería a Domicilio, Conductor Designado, Trasteos y Mudanzas, Intermediación de Alquiler de Equipos, Operación de Excavadoras, Operación de Bulldozers, Mecánica a Domicilio, Electricidad Automotriz, Cerrajería Automotriz, Limpieza y Aseo General, Jardinería]
        
        Ejemplo de formato de salida:
        "Se requiere un profesional para la revisión y gestión de..."
        
        Sugerencia de categoría: Abogado Laboral
        """
        
        # 2. Llamada real a la API de Gemini
        client = genai.Client()
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_maestro,
        )
        
        texto_optimizado = response.text

        return jsonify({
            'success': True,
            'texto_optimizado': texto_optimizado
        })
        
    except Exception as e:
        print(f"❌ Error crítico en Upward AI (Gemini): {e}")
        return jsonify({
            'success': False, 
            'error': 'Nuestros servidores de IA están congestionados. Por favor, describe tu requerimiento manualmente.'
        }), 500

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
        
        # 🤝 NUEVO: Capturamos el código de quién lo invitó (si existe)
        referido_por = request.form.get('referido_por', '').strip().upper()

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
            saldo_creditos=0.0,
            codigo_embajador=generar_codigo_embajador(), # 🎁 Nace con su propio código
            referido_por=referido_por if referido_por else None # 🕵️‍♂️ Registra quién lo trajo
        )
        
        db.session.add(nuevo_usuario)
        db.session.commit() # Guarda físicamente en PostgreSQL (Supabase)
        
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
# PASO 1: Envía el correo con el token
# =====================================================================
@app.route('/recuperar-contrasena', methods=['GET', 'POST'])
def recuperar_contrasena():
    if request.method == 'POST':
        correo = request.form.get('correo_recuperacion')
        usuario = Usuario.query.filter_by(correo=correo).first()
        
        if usuario:
            token = serializer.dumps(correo, salt='recuperar-claves-inworker')
            # _external=True hace que Flask arme el https://inworker.co automáticamente
            link_recuperacion = url_for('restablecer_clave', token=token, _external=True)
            
            # --- LÓGICA DE ENVÍO DE CORREO (La pieza que faltaba) ---
            try:
                msg = Message(
                    subject="Recupera tu contraseña en inWorker",
                    recipients=[correo]
                )
                msg.html = f"""
                <div style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 10px;">
                    <h2 style="color: #2563EB;">Recuperación de contraseña</h2>
                    <p style="color: #334155;">Hola,</p>
                    <p style="color: #334155;">Hemos recibido una solicitud para restablecer tu contraseña en el ecosistema <strong>inWorker</strong>.</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{link_recuperacion}" style="background-color: #2563EB; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold;">Restablecer mi contraseña</a>
                    </div>
                    <p style="color: #64748b; font-size: 12px;">Si el botón no funciona, copia y pega este enlace en tu navegador:<br>{link_recuperacion}</p>
                    <hr style="border: none; border-top: 1px solid #e2e8f0; margin-top: 30px;">
                    <p style="color: #94a3b8; font-size: 10px;">Si no fuiste tú, puedes ignorar este mensaje de forma segura.</p>
                </div>
                """
                mail.send(msg)
                flash("📧 Te hemos enviado un enlace de recuperación.", "success")
                
            except Exception as e:
                # Si Google rechaza la conexión o falla algo, ahora SÍ lo veremos en Render
                print(f"🔥 Error crítico enviando correo a {correo}: {str(e)}")
                flash("⚠️ Hubo un problema al enviar el correo. Revisa tu conexión.", "error")
            # --------------------------------------------------------

        else:
            flash("❌ Correo no registrado.", "error")
        return redirect(url_for('login', action='recuperar'))
        
    return redirect(url_for('login', action='recuperar'))

# =====================================================================
# PASO 2: Valida el token y muestra el formulario (Aquí va el render_template)
# =====================================================================
@app.route('/restablecer-clave/<token>', methods=['GET', 'POST'])
def restablecer_clave(token):
    # 1. Validar el token
    try:
        correo = serializer.loads(token, salt='recuperar-claves-inworker', max_age=3600)
    except:
        flash("❌ Enlace inválido o expirado.", "error")
        return redirect(url_for('login'))

    # 2. Si es POST, el usuario está guardando la nueva clave
    if request.method == 'POST':
        nueva_clave = request.form.get('contrasena')
        usuario = Usuario.query.filter_by(correo=correo).first()
        
        if usuario:
            usuario.contrasena = nueva_clave # O usa tu método de hash
            db.session.commit()
            flash("✅ Contraseña actualizada.", "success")
            return redirect(url_for('login'))
            
    # 3. SI ES GET (entrar a la página), este es el render que temías dañar.
    # Se pone al final de todo para que solo se ejecute si no hubo un POST.
    return render_template('restablecer.html', token=token)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard', methods=['GET'])
def home():
    # 🛡️ PROTECCIÓN AMIGABLE: Validamos usando el correo
    if 'usuario_correo' not in session: 
        flash("🔒 Por favor, inicia sesión para acceder al panel.", "error")
        return redirect(url_for('login'))
        
    correo_logueado = session.get('usuario_correo')
    VALOR_CREDITO_COP = 10000 # Regla de oro de inWorker
    
    # 🔔 CONTEO DE NOTIFICACIONES (Cruzando con la tabla Tarea para evitar errores)
    try:
        mensajes_nuevos = db.session.query(Mensaje).join(Tarea, Mensaje.tarea_id == Tarea.id).filter(
            db.or_(Tarea.cliente_correo == correo_logueado, Tarea.trabajador_correo == correo_logueado),
            Mensaje.remitente_correo != correo_logueado,
            Mensaje.leido == 0
        ).count()
    except Exception as e:
        print(f"Aviso silencioso - Error contando mensajes: {e}")
        mensajes_nuevos = 0
    
    # 📊 SECCIÓN DE MÉTRICAS DEL DASHBOARD (Agregaciones optimizadas)
    total_workers = Usuario.query.filter_by(rol='Trabajador').count()
    
    # 🚀 Filtramos las órdenes en mediación SOLO para este usuario según su rol
    rol_usuario = session.get('usuario_rol')
    if rol_usuario == 'Cliente':
        tareas_activas_objs = Tarea.query.filter_by(cliente_correo=correo_logueado).filter(Tarea.estado.in_(['Cotización Pendiente', 'En Garantia'])).all()
        ordenes_mediacion = len(tareas_activas_objs)
    else:
        tareas_activas_objs = Tarea.query.filter_by(trabajador_correo=correo_logueado).filter(Tarea.estado.in_(['Cotización Pendiente', 'En Garantia'])).all()
        ordenes_mediacion = len(tareas_activas_objs)
    
    # 🚀 SUMA TOTAL PARA LA CAMPANITA (Solo mensajes nuevos)
    alertas_totales = mensajes_nuevos

    # Suma limpia de fondos en Escrow (Maneja si es None devolviendo 0.0)
    fondos_escrow = db.session.query(db.func.sum(db.func.cast(Tarea.pago, db.Float)))\
        .filter(Tarea.estado == 'En Garantia').scalar() or 0.0
    
    # 💰 CONSULTA REAL DE SALDO EN BASE DE DATOS Y EXTRACCIÓN DE PERFIL
    usuario_info = Usuario.query.filter_by(correo=correo_logueado).first()
    saldo_real = round(usuario_info.saldo_creditos, 2) if usuario_info else 0.0
    
    # ⚖️ CONSULTA DE DISPUTAS ACTIVAS PARA LA CONSOLA DE ARBITRAJE
    disputas_query = Tarea.query.filter_by(estado='En Arbitraje Admin').order_by(Tarea.id.desc()).all()
    
    # Adaptación a diccionarios planos para mantener compatibilidad con tu frontend actual
    lista_disputas = [{
        'id': d.id,
        'titulo': d.titulo,
        'estado': d.estado,
        'reportado_por': getattr(d, 'reportado_por', 'No especificado'),
        'motivo_disputa': getattr(d, 'motivo_disputa', 'Sin motivo'),
        'costo_creditos': d.costo_creditos
    } for d in disputas_query]
    
    # 💸 INICIALIZAMOS LISTAS VACÍAS (ESTO EVITA EL ERROR 500)
    recargas_pendientes = []
    retiros_pendientes = []
    tecnicos_pendientes_kyc = [] # 👈 AÑADIDO PARA KYC
    
    # 💸 CONSULTAS EXCLUSIVAS DEL OJO DE DIOS (Solo Admin)
    if rol_usuario == 'Admin':
        # Consultamos las recargas de saldo (Clientes)
        recargas_pendientes = Recarga.query.filter_by(estado='Pendiente').order_by(Recarga.fecha.asc()).all()
        # Consultamos los retiros de nómina (Técnicos)
        retiros_pendientes = BilleteraRetiro.query.filter(BilleteraRetiro.estado.in_(['Pendiente', 'Procesando'])).order_by(BilleteraRetiro.fecha_solicitud.asc()).all()
        
        # Buscamos a los técnicos pendientes de KYC (Fotos subidas pero sin verificar) 👈 AÑADIDO PARA KYC
        tecnicos_pendientes_kyc = Usuario.query.filter(
            Usuario.rol.in_(['Trabajador', 'Worker']),
            Usuario.verificado == 0,
            Usuario.kyc_cedula != None,
            Usuario.kyc_cedula != ''
        ).all()

    # Armamos el diccionario dinámico para las plantillas
    perfil_real = {'saldo_creditos': saldo_real, 'saldo': saldo_real}

    # 📥 GENERACIÓN DE LA BANDEJA DE ENTRADA (Chats Activos)
    bandeja_entrada = []
    try:
        for t in tareas_activas_objs:
            # Contar no leídos para esta tarea específica
            no_leidos = db.session.query(Mensaje).filter(
                Mensaje.tarea_id == t.id, 
                Mensaje.leido == 0,
                Mensaje.remitente_correo != correo_logueado
            ).count()
            
            # Extraer el último mensaje para el snippet
            ultimo_mensaje = db.session.query(Mensaje).filter(Mensaje.tarea_id == t.id).order_by(Mensaje.id.desc()).first()
            snippet = ultimo_mensaje.mensaje if ultimo_mensaje else "Inicia la conversación..."
            
            bandeja_entrada.append({
                'id': t.id,
                'titulo': t.titulo,
                'estado': t.estado,
                'no_leidos': no_leidos,
                'snippet': snippet
            })
            
        # Ordenamos la bandeja: Primero los que tienen mensajes sin leer, luego por ID más reciente
        bandeja_entrada.sort(key=lambda x: (x['no_leidos'] > 0, x['id']), reverse=True)
    except Exception as e:
        print(f"Error generando bandeja de entrada: {e}")

    # 🚀 RETORNAMOS TODAS LAS VARIABLES INYECTADAS
    return render_template('index.html', 
                           nombre_usuario=session.get('usuario_nombre'),
                           total_workers=total_workers,
                           ordenes_mediacion=ordenes_mediacion,
                           fondos_escrow=fondos_escrow,
                           saldo=saldo_real,
                           saldo_usuario=saldo_real,
                           cliente_perfil=perfil_real,
                           trabajador_perfil=perfil_real,
                           lista_disputas=lista_disputas,
                           notificaciones_sin_leer=alertas_totales,
                           usuario=usuario_info,
                           bandeja_entrada=bandeja_entrada,
                           recargas=recargas_pendientes,
                           retiros_pendientes=retiros_pendientes,
                           tecnicos_pendientes_kyc=tecnicos_pendientes_kyc) # 👈 AÑADIDO PARA KYC

# =====================================================================
# 🛡️ MÓDULO ADMIN: AUDITORÍA DE IDENTIDAD (KYC)
# =====================================================================

@app.route('/admin/kyc/<int:id>/aprobar', methods=['POST'])
def aprobar_kyc(id):
    if session.get('usuario_rol') != 'Admin':
        flash("Acceso denegado.", "error")
        return redirect(url_for('home'))
        
    tecnico = Usuario.query.get_or_404(id)
    tecnico.verificado = 1
    db.session.commit()
    
    flash(f"✅ Identidad de {tecnico.nombre} aprobada con éxito. Ahora es Nivel Pro.", "success")
    return redirect(request.referrer or url_for('home'))


@app.route('/admin/kyc/<int:id>/rechazar', methods=['POST'])
def rechazar_kyc(id):
    if session.get('usuario_rol') != 'Admin':
        flash("Acceso denegado.", "error")
        return redirect(url_for('home'))
        
    tecnico = Usuario.query.get_or_404(id)
    
    # Le borramos las fotos fallidas para que el sistema le pida subirlas de nuevo
    tecnico.kyc_cedula = None
    tecnico.kyc_selfie = None
    tecnico.verificado = 0
    db.session.commit()
    
    flash(f"❌ Documentos de {tecnico.nombre} rechazados. Deberá subirlos nuevamente.", "error")
    return redirect(request.referrer or url_for('home'))

# =====================================================================
# 💸 ADMIN: GESTIÓN Y CONTROL DE RETIROS DE TÉCNICOS
# =====================================================================

@app.route('/admin/retiro/<int:retiro_id>/procesar', methods=['POST'])
def admin_procesar_retiro(retiro_id):
    """Cambia el estado a Procesando (Avisa al técnico que el dinero va en camino)"""
    if session.get('usuario_rol') != 'Admin':
        flash("🚫 Acceso denegado.", "error")
        return redirect(url_for('home'))
        
    retiro = BilleteraRetiro.query.get_or_404(retiro_id)
    if retiro.estado == 'Pendiente':
        retiro.estado = 'Procesando'
        db.session.commit()
        flash(f"⏳ Retiro en proceso. El técnico {retiro.usuario_correo} verá que su pago está en camino.", "info")
    return redirect(url_for('home'))

@app.route('/admin/retiro/<int:retiro_id>/desembolsar', methods=['POST'])
def admin_desembolsar_retiro(retiro_id):
    """Recibe la foto de tu Nequi, liquida el retiro, guarda el soporte y AVISA AL TÉCNICO"""
    if session.get('usuario_rol') != 'Admin':
        flash("🚫 Acceso denegado.", "error")
        return redirect(url_for('home'))
        
    retiro = BilleteraRetiro.query.get_or_404(retiro_id)
    
    if 'comprobante_pago' not in request.files:
        flash("⚠️ Debes adjuntar la captura de pantalla de la transferencia.", "error")
        return redirect(url_for('home'))
        
    file = request.files['comprobante_pago']
    
    if file and archivo_permitido(file.filename):
        # 1. Guardamos la imagen
        filename = secure_filename(f"desembolso_retiro_{retiro.id}_{int(time.time())}.{file.filename.rsplit('.', 1)[1].lower()}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # 2. Actualizamos la BD
        retiro.comprobante_pago = filename
        retiro.estado = 'Desembolsado'
        db.session.commit()
        
        # 📧 3. DISPARAMOS EL CORREO AL TÉCNICO
        try:
            msg = Message(
                '💰 ¡Tu dinero ha sido desembolsado! - inWorker',
                recipients=[retiro.usuario_correo]
            )
            msg.html = f"""
            <html>
                <body style="font-family: Arial, sans-serif; background-color: #f8fafc; padding: 20px;">
                    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; padding: 30px; border: 1px solid #e2e8f0;">
                        <h2 style="color: #10b981; text-align: center;">¡Transferencia Exitosa! 💸</h2>
                        <p style="color: #475569; font-size: 16px;">Hola, te confirmamos que hemos procesado tu solicitud de retiro.</p>
                        
                        <div style="background-color: #f1f5f9; padding: 15px; border-radius: 8px; margin: 20px 0;">
                            <p style="margin: 5px 0; color: #334155;"><strong>Monto:</strong> ${retiro.equivalente_pesos:,.0f} COP</p>
                            <p style="margin: 5px 0; color: #334155;"><strong>Método:</strong> {retiro.metodo_pago}</p>
                            <p style="margin: 5px 0; color: #334155;"><strong>Destino:</strong> {retiro.detalles_cuenta}</p>
                        </div>
                        
                        <p style="color: #64748b; font-size: 14px;">El dinero ya debería estar reflejado en tu cuenta. Puedes verificar el soporte de pago ingresando a tu panel de inWorker.</p>
                        
                        <div style="text-align: center; margin-top: 30px;">
                            <a href="https://inworker.co/dashboard" style="background-color: #10b981; color: white; padding: 12px 25px; text-decoration: none; border-radius: 6px; font-weight: bold;">Ir a mi Billetera</a>
                        </div>
                    </div>
                </body>
            </html>
            """
            mail.send(msg)
        except Exception as e:
            print(f"⚠️ El desembolso se hizo, pero falló el envío de correo: {e}")
        
        flash(f"✅ ¡Nómina pagada! Soporte guardado y correo enviado a {retiro.usuario_correo}.", "success")
    else:
        flash("❌ Archivo no permitido o dañado. Usa JPG, PNG o PDF.", "error")
        
    return redirect(url_for('home'))

# =====================================================================
# 💸 MÓDULO FINANCIERO: PROCESAMIENTO DE RETIROS (INDEPENDIENTE)
# =====================================================================
@app.route('/solicitar_retiro', methods=['POST'])
def solicitar_retiro():
    if 'usuario_correo' not in session:
        return redirect(url_for('login'))
        
    correo_logueado = session['usuario_correo']
    usuario = Usuario.query.filter_by(correo=correo_logueado).first()
    
    try:
        creditos_retiro = float(request.form.get('creditos_retiro', 0))
    except ValueError:
        creditos_retiro = 0.0
        
    metodo = request.form.get('metodo_pago', 'No especificado').upper()
    detalles = request.form.get('detalles_cuenta', '')
    
    saldo_actual = usuario.saldo_creditos if usuario else 0.0
    VALOR_CREDITO_COP = 10000
    
    # 1. Validación de saldo
    if creditos_retiro > 0 and creditos_retiro <= saldo_actual:
        monto_bruto_cop = creditos_retiro * VALOR_CREDITO_COP
        
        # 2. Regla: Retiro mínimo de $50.000 COP (5 créditos)
        if monto_bruto_cop < 50000:
            flash("❌ El retiro mínimo es de 5 créditos ($50.000 COP).", "error")
            return redirect(url_for('home'))
            
        # 3. Regla: Comisión inWorker (12%)
        comision_plataforma = monto_bruto_cop * 0.12
        
        # 4. Regla: Costo Interbancario
        costo_bancario = 0
        bancos_sin_costo = ['NEQUI', 'BANCOLOMBIA']
        if not any(banco in metodo for banco in bancos_sin_costo):
            costo_bancario = 3500
            
        # 5. Calculamos el Neto
        monto_neto = monto_bruto_cop - comision_plataforma - costo_bancario
        
        if monto_neto <= 0:
            flash("❌ El monto no cubre los gastos de transferencia y plataforma.", "error")
            return redirect(url_for('home'))
            
        nuevo_saldo = round(saldo_actual - creditos_retiro, 2)
        
        try:
            # Descontamos el saldo
            usuario.saldo_creditos = nuevo_saldo
            
            # Armamos el desglose para la BD del Admin
            desglose_admin = f"{detalles} | Bruto: ${monto_bruto_cop} | Com 12%: ${comision_plataforma} | Transf: ${costo_bancario}"
            
            # Registramos en la tabla BilleteraRetiro
            nuevo_retiro = BilleteraRetiro(
                usuario_correo=correo_logueado,
                monto_creditos=creditos_retiro,
                equivalente_pesos=monto_neto, 
                metodo_pago=metodo,
                detalles_cuenta=desglose_admin, 
                estado='Pendiente'
            )
            db.session.add(nuevo_retiro)
            db.session.commit()
            
            msg = f"✅ Solicitud exitosa. Recibirás ${monto_neto:,.0f} COP (descontando 12% de plataforma"
            msg += f" y ${costo_bancario:,.0f} por giro a otros bancos)." if costo_bancario > 0 else ")."
                
            flash(msg, "success")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error al procesar el retiro: {e}")
            flash("❌ Ocurrió un error al procesar tu transacción. Fondos protegidos.", "error")
    else:
        flash("❌ Fondos insuficientes o cantidad de créditos inválida.", "error")
        
    return redirect(url_for('home'))

@app.route('/ir_al_chat_reciente')
def ir_al_chat_reciente():
    correo = session.get('usuario_correo')
    if not correo:
        return redirect(url_for('login'))
        
    try:
        # Busca el mensaje más reciente de una de mis tareas, que yo NO haya enviado, y sin leer
        mensaje = db.session.query(Mensaje).join(Tarea, Mensaje.tarea_id == Tarea.id).filter(
            db.or_(Tarea.cliente_correo == correo, Tarea.trabajador_correo == correo),
            Mensaje.remitente_correo != correo,
            Mensaje.leido == 0
        ).order_by(Mensaje.id.desc()).first()
        
        if mensaje:
            # 🚀 AQUÍ ESTÁ LA CORRECCIÓN: Te enviamos a 'ver_chat' que es tu ruta real
            return redirect(url_for('ver_chat', tarea_id=mensaje.tarea_id))
    except Exception as e:
        print(f"❌ Error en ir_al_chat_reciente: {e}")
        
    # Si falla o no hay mensajes, lo mandamos al tablón
    return redirect(url_for('ver_tareas'))

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
    print(f"--- NUEVA PETICIÓN DE IA (COPILOTO PERFIL) ---")
    print(f"Profesión recibida: {profesion}")
    print(f"Habilidades recibidas: {habilidades_actuales}")
    
    prompt = f"""
    Eres el Copiloto inWorker, el asistente de inteligencia artificial experto en marca personal dentro de inWorker (un marketplace integral que abarca desde servicios técnicos y construcción, hasta asesorías legales, financieras, tutorías educativas y belleza).
    
    Tu tarea es redactar un extracto de perfil impecable, atractivo y altamente vendedor, basado estrictamente en los datos del trabajador independiente.
    
    INFORMACIÓN REAL DEL USUARIO:
    - Oficio/Profesión seleccionada: {profesion}
    - Habilidades y Experiencia ingresadas: {habilidades_actuales}
    
    REQUISITOS DEL TEXTO (INSTRUCCIONES ESTRICTAS):
    1. El tono debe ADAPTARSE a la profesión: altamente formal y riguroso para áreas legales/financieras; técnico y resolutivo para construcción/tecnología; cercano y empático para cuidado/educación/belleza.
    2. Redacta obligatoriamente en PRIMERA PERSONA del singular ("Soy...", "Ofrezco...", "Me especializo en...").
    3. Dale prioridad absoluta a TODAS las habilidades, herramientas y tecnologías que el usuario mencionó. Realza su experiencia sin inventar datos que no existan en su descripción original.
    4. El texto debe transmitir máxima confianza, calidad y enfoque a resultados para persuadir al cliente a contratar.
    5. Permite que la extensión se adapte de forma natural (máximo 2 o 3 párrafos cortos y contundentes).
    6. Devuelve ÚNICAMENTE el texto sugerido final. No agregues introducciones, saludos, notas, confirmaciones ni comillas.
    """
    
    try:
        # Asegúrate de tener 'client' instanciado, ej: client = genai.Client()
        client = genai.Client() 
        
        # 🚀 Consumo estable con el nuevo SDK de Gemini
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        texto_optimizado = response.text.strip()
        
        print(f"✅ Respuesta exitosa del Copiloto Gemini: {texto_optimizado}")
        return jsonify({'sugerencia': texto_optimizado})
        
    except Exception as e:
        print(f"❌ ERROR REAL EN NUEVO SDK DE GEMINI: {e}")
        # El respaldo amigable por si la API falla o excede la cuota
        respaldo = f"Profesional especializado en {profesion}. Comprometido con la excelencia operativa, la puntualidad y en brindar soluciones eficientes y de la más alta calidad a través de la plataforma inWorker."
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

# --- MÓDULO ADMINISTRATIVO DE GESTIÓN DE RETIROS Y DISPUTAS (COBROS) - OPTIMIZADO ---
@app.route('/admin/retiros', methods=['GET', 'POST'])
def admin_retiros():
    if 'usuario_nombre' not in session or session.get('usuario_rol') != 'Admin':
        return redirect(url_for('dashboard')) # Mejor mandarlo al dashboard que al index vacío
        
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
                    solicitud.estado = 'Completado' # 🚨 Ajustado para que encaje con el CSS de tu HTML
                    flash(f"✅ Transferencia #{solicitud_id} marcada como Completada.", "success")
                    
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
            
        return redirect(url_for('admin_retiros'))

    # 📊 CONSTRUCCIÓN DE LA LISTA DE RETIROS CON JOIN DE MODELOS Y ORDENAMIENTO
    from sqlalchemy.sql.expression import case
    orden = case((BilleteraRetiro.estado == 'Pendiente', 1), else_=2)

    solicitudes_db = db.session.query(BilleteraRetiro, Usuario)\
        .outerjoin(Usuario, db.func.lower(db.func.trim(BilleteraRetiro.usuario_correo)) == db.func.lower(db.func.trim(Usuario.correo)))\
        .order_by(orden, BilleteraRetiro.id.desc()).all()
        
    # Formateamos exactamente como lo pide tu HTML usando un mapeo plano
    lista_retiros = []
    for ret, usr in solicitudes_db:
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
    
    # 🛡️ CÁLCULO DE FONDOS ESCROW GLOBALES (Para el Admin)
    fondos_escrow = db.session.query(db.func.sum(Tarea.costo_creditos)).filter(
        Tarea.estado == 'En Garantia'
    ).scalar() or 0.0
        
    # =====================================================================
    # ⚖️ NUEVO: CONSULTA DE DISPUTAS ACTIVAS PARA EL ADMIN
    # =====================================================================
    disputas_query = Tarea.query.filter_by(estado='En Arbitraje Admin').order_by(Tarea.id.desc()).all()
    
    lista_disputas = [{
        'id': d.id,
        'titulo': d.titulo,
        'estado': d.estado,
        'cliente_correo': d.cliente_correo,
        'trabajador_correo': d.trabajador_correo,
        'costo_creditos': d.costo_creditos
    } for d in disputas_query]
        
    return render_template('admin_retiros.html', 
                           solicitudes=lista_retiros, 
                           disputas=lista_disputas, # 👈 AQUÍ INYECTAMOS LAS DISPUTAS AL HTML
                           nombre_usuario=session.get('usuario_nombre', 'Admin'),
                           total_workers=total_workers, 
                           ordenes_mediacion=ordenes_mediacion, 
                           fondos_escrow=fondos_escrow)

import os
import time

# =====================================================================
# 💳 MÓDULO DE PAGOS: INICIO DE RECARGA CON BOLD (PASARELA)
# =====================================================================
# =====================================================================
# 💳 RUTA PARA PROCESAR EL FORMULARIO DE RECARGA (CON COMISIÓN INCLUIDA)
# =====================================================================
@app.route('/recargar_billetera', methods=['GET', 'POST'])
def recargar_billetera():
    if 'usuario_correo' not in session:
        return redirect(url_for('login'))
        
    correo_logueado = session['usuario_correo']
        
    if request.method == 'POST':
        try:
            # 1. Capturamos AMBOS valores enviados desde el frontend
            creditos_a_cargar = float(request.form.get('creditos', 1))
            monto_pesos = float(request.form.get('monto_cobrar', 0)) # Este ya trae los $1.500 del banco
        except ValueError:
            creditos_a_cargar = 0.0
            monto_pesos = 0.0
            
        # ¡ELIMINAMOS la multiplicación * 10000 porque el frontend ya hace el cálculo total!
            
        if monto_pesos <= 0:
            flash("❌ Debes ingresar una cantidad válida.", "error")
            return redirect(url_for('recargar_billetera'))
            
        if monto_pesos > 1000000:
            flash("❌ Por seguridad, la recarga máxima permitida es de $1.000.000 COP por transacción.", "error")
            return redirect(url_for('recargar_billetera'))
            
        try:
            usuario = Usuario.query.filter_by(correo=correo_logueado).first()
            
            if usuario:
                bold_public_key = os.environ.get('BOLD_API_KEY', '')
                bold_integrity_key = os.environ.get('BOLD_INTEGRITY_KEY', '')
                
                # 2. 💡 JUGADA MAESTRA: Metemos los créditos en la referencia
                # Ejemplo resultante: RECARGA-8-3-1783534234 (Usuario 8, compra 3 créditos)
                referencia_pago = f"RECARGA-{usuario.id}-{int(creditos_a_cargar)}-{int(time.time())}"
                
                monto_str = str(int(monto_pesos))
                
                # 🔐 MAGIA CRIPTOGRÁFICA: Generamos el Sello para descongelar Bold
                cadena_firma = f"{referencia_pago}{monto_str}COP{bold_integrity_key}"
                firma_integridad = hashlib.sha256(cadena_firma.encode('utf-8')).hexdigest()
                
                return render_template('pago_bold.html', 
                                       creditos=int(creditos_a_cargar),
                                       monto_pesos=monto_str,
                                       bold_public_key=bold_public_key,
                                       firma_integridad=firma_integridad,  
                                       referencia_pago=referencia_pago,
                                       usuario=usuario)
            else:
                flash("❌ Error al identificar el usuario en el sistema.", "error")
                
        except Exception as e:
            print(f"❌ Error crítico preparando pasarela Bold: {e}")
            flash("❌ Ocurrió un error interno al conectar con el banco.", "error")
            
        return redirect(request.referrer or url_for('dashboard'))
        
    # GET: Mostrar vista normal
    usuario_info = Usuario.query.filter_by(correo=correo_logueado).first()
    saldo_vista = round(usuario_info.saldo_creditos, 2) if usuario_info else 0.0
    
    return render_template('recargar.html', saldo=saldo_vista)

import os
import time
from werkzeug.utils import secure_filename
from datetime import datetime

# =====================================================================
# 💸 MÓDULO FINANCIERO: RECEPCIÓN DE NEQUI (VERIFICACIÓN EN COLA)
# =====================================================================
@app.route('/reportar_pago_nequi', methods=['POST'])
def reportar_pago_nequi():
    if 'usuario_correo' not in session:
        return redirect(url_for('index'))

    correo_logueado = session['usuario_correo']
    monto_transferido = request.form.get('monto_transferido', type=float)
    comprobante = request.files.get('comprobante_nequi')

    if not monto_transferido or not comprobante or comprobante.filename == '':
        flash("❌ Debes ingresar el monto y adjuntar la captura de pantalla.", "error")
        return redirect(url_for('recargar_billetera'))

    try:
        # 1. Guardamos la foto del comprobante
        nombre_unico = f"nequi_{int(time.time())}_{secure_filename(comprobante.filename)}"
        ruta_guardado = os.path.join(app.config['UPLOAD_FOLDER'], nombre_unico)
        comprobante.save(ruta_guardado)

        # 2. Matemática inWorker (10,000 COP = 1 Crédito)
        VALOR_CREDITO_COP = 10000
        creditos_comprados = round(monto_transferido / VALOR_CREDITO_COP, 2)

        # 3. Creamos el registro en estado PENDIENTE (No inyectamos saldo aún)
        nueva_recarga = Recarga(
            usuario_correo=correo_logueado,
            monto_cop=monto_transferido,
            creditos=creditos_comprados,
            comprobante=nombre_unico,
            estado='Pendiente'
        )
        db.session.add(nueva_recarga)
        db.session.commit()

        # 🚨 ALERTA PARA TI
        print(f"🚨 ACCIÓN REQUERIDA: Verificar Nequi de {monto_transferido} COP. Usuario: {correo_logueado}.")

        # 4. Mensaje psicológico al cliente igualando la experiencia Bold
        flash("⏳ Hemos recibido tu comprobante. Tu recarga está siendo procesada y se reflejará en tu billetera en aproximadamente 5 a 10 minutos.", "info")
        return redirect(url_for('dashboard'))

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error procesando pago Nequi: {e}")
        flash("❌ Ocurrió un error al enviar tu comprobante. Intenta de nuevo.", "error")
        return redirect(url_for('recargar_billetera'))

# =====================================================================
# 🛡️ ADMIN: LIBERACIÓN DE CRÉDITOS NEQUI (LOS BOTONES)
# =====================================================================
@app.route('/admin/auditar_recarga/<int:recarga_id>/<accion>', methods=['POST'])
def auditar_recarga(recarga_id, accion):
    # 🔒 Filtro de seguridad: Solo tú puedes presionar estos botones
    if session.get('usuario_rol') != 'Admin':
        flash("🚫 Acceso denegado. Solo administradores.", "error")
        return redirect(url_for('home'))
    
    try:
        recarga = Recarga.query.get_or_404(recarga_id)
        usuario = Usuario.query.filter_by(correo=recarga.usuario_correo).first()

        if recarga.estado != 'Pendiente':
            flash("⚠️ Esta recarga ya fue procesada anteriormente.", "warning")
            return redirect(url_for('home')) # 🎯 Te devuelve al Dashboard

        if accion == 'aprobar':
            # ✅ VERIFICACIÓN EXITOSA: Inyectamos el dinero en la billetera
            usuario.saldo_creditos = round((usuario.saldo_creditos or 0.0) + recarga.creditos, 2)
            recarga.estado = 'Aprobada'
            flash(f"✅ Recarga aprobada. Se inyectaron {recarga.creditos} créditos a {usuario.correo}.", "success")

        elif accion == 'rechazar':
            # 🚨 FRAUDE: Se rechaza sin tocar el saldo
            recarga.estado = 'Rechazada'
            flash(f"🚫 Recarga rechazada para {usuario.correo}. Comprobante inválido.", "error")

        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error auditando recarga: {e}")
        flash("Error interno procesando la auditoría.", "error")

    return redirect(url_for('home')) # 🎯 Te devuelve al Dashboard central

# --- CONTROL DEL TABLÓN DE ÓRDENES - OPTIMIZADO Y CON BUSCADOR ---
@app.route('/tareas')
def ver_tareas():
    if 'usuario_nombre' not in session: 
        return redirect(url_for('index'))
    
    # 1. Capturamos los parámetros de la URL (Geolocalización + Búsqueda)
    user_lat = request.args.get('lat', type=float)
    user_lng = request.args.get('lng', type=float)
    query_busqueda = request.args.get('q', '').strip()
    categoria_filtro = request.args.get('categoria_filtro', '').strip()
    
    correo_logueado = session['usuario_correo']
    
    # ⚡ Consulta de saldo real indexada en la BD con SQLAlchemy
    usuario_db = Usuario.query.filter_by(correo=correo_logueado).first()
    saldo_actual = round(usuario_db.saldo_creditos, 2) if usuario_db else 0.0
    
    # 🔔 CONTEO DE NOTIFICACIONES (Mensajes sin leer)
    rol_logueado = session.get('usuario_rol')
    mensajes_nuevos = 0

    try:
        if rol_logueado == 'Cliente':
            mensajes_nuevos = db.session.query(db.func.count(Mensaje.id))\
                .join(Tarea, Mensaje.tarea_id == Tarea.id)\
                .filter(
                    Tarea.cliente_correo == correo_logueado,
                    Mensaje.remitente_correo != correo_logueado,
                    Mensaje.leido == 0
                ).scalar() or 0
        elif rol_logueado in ['Trabajador', 'Worker']:
            mensajes_nuevos = db.session.query(db.func.count(Mensaje.id))\
                .join(Tarea, Mensaje.tarea_id == Tarea.id)\
                .filter(
                    (Tarea.trabajador_correo == correo_logueado) | 
                    (Mensaje.canal_trabajador == 'sala_' + db.func.cast(Tarea.id, db.String)),
                    Mensaje.remitente_correo != correo_logueado,
                    Mensaje.leido == 0
                ).scalar() or 0
    except Exception as e:
        print(f"Aviso: Error al contar notificaciones en tareas: {e}")
        mensajes_nuevos = 0

    # 🔍 INICIO DEL MOTOR DE BÚSQUEDA Y FILTRADO
    consulta = Tarea.query.filter(Tarea.estado != 'Finalizada')

    # Filtro Semántico (Título o Descripción)
    if query_busqueda:
        termino_sql = f"%{query_busqueda}%"
        consulta = consulta.filter(db.or_(
            Tarea.titulo.ilike(termino_sql),
            Tarea.descripcion.ilike(termino_sql)
        ))

    # Filtro de Categoría Exacta
    if categoria_filtro:
        consulta = consulta.filter(Tarea.categoria == categoria_filtro)

    # Extraemos las tareas aplicando los filtros y ordenando por más recientes
    tareas_db = consulta.order_by(Tarea.id.desc()).all()
    # 🔍 FIN DEL MOTOR DE BÚSQUEDA
    
    # Mapeamos los objetos de la BD a un formato de diccionario
    lista_tareas = [{
        'id': t.id,
        'titulo': t.titulo,
        'descripcion': t.descripcion,
        'estado': t.estado,
        'pago': t.pago,
        'categoria': t.categoria, # <-- Añadido para que el HTML renderice el badge
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
            
        # Ordenamos por distancia (los más cercanos primero)
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
                           t_distancia=t_distancia,
                           notificaciones_sin_leer=mensajes_nuevos)

# =====================================================================
# 🚀 MÓDULO DE CRECIMIENTO: BÓVEDA DE EMBAJADOR Y GAMIFICACIÓN
# =====================================================================
@app.route('/embajador')
def panel_embajador():
    if 'usuario_correo' not in session:
        return redirect(url_for('index'))

    correo_logueado = session['usuario_correo']
    usuario_actual = Usuario.query.filter_by(correo=correo_logueado).first()

    # 🔍 MAREACIÓN EXACTA SUPABASE: Contamos cuántos usuarios fueron invitados por su código
    total_referidos = 0
    if usuario_actual.codigo_embajador:
        total_referidos = Usuario.query.filter_by(referido_por=usuario_actual.codigo_embajador).count()

    # Sistema Automático de Niveles (Gamificación inWorker)
    nivel_actual = "Bronce 🥉"
    siguiente_nivel = "Plata 🥈"
    meta_siguiente = 5
    
    if total_referidos >= 50:
        nivel_actual = "Diamante 💎"
        siguiente_nivel = "Máximo Rango"
        meta_siguiente = total_referidos
        progreso = 100
    elif total_referidos >= 20:
        nivel_actual = "Oro 🥇"
        siguiente_nivel = "Diamante 💎"
        meta_siguiente = 50
        progreso = int((total_referidos / 50) * 100)
    elif total_referidos >= 5:
        nivel_actual = "Plata 🥈"
        siguiente_nivel = "Oro 🥇"
        meta_siguiente = 20
        progreso = int((total_referidos / 20) * 100)
    else:
        nivel_actual = "Bronce 🥉"
        siguiente_nivel = "Plata 🥈"
        meta_siguiente = 5
        progreso = int((total_referidos / 5) * 100) if total_referidos > 0 else 0

    return render_template('embajador.html',
                           usuario=usuario_actual,
                           total_referidos=total_referidos,
                           nivel=nivel_actual,
                           siguiente_nivel=siguiente_nivel,
                           meta=meta_siguiente,
                           progreso=progreso)

# =====================================================================
# 📄 MÓDULO LEGAL: CERTIFICADO DE INGRESOS INDEPENDIENTE
# =====================================================================
@app.route('/certificado_ingresos')
def certificado_ingresos():
    if 'usuario_correo' not in session:
        return redirect(url_for('index'))

    correo_logueado = session['usuario_correo']
    usuario_actual = Usuario.query.filter_by(correo=correo_logueado).first()

    VALOR_CREDITO_COP = 10000
    # Multiplicamos el saldo de créditos actual por el valor comercial del crédito
    ingresos_estimados_cop = round((usuario_actual.saldo_creditos or 0.0) * VALOR_CREDITO_COP, 0)
    
    from datetime import datetime
    import locale
    
    # Intentamos ponerlo en español para la estética formal, si no, usa el fallback nativo
    try:
        locale.setlocale(locale.LC_TIME, 'es_CO.utf8')
    except Exception:
        try:
            locale.setlocale(locale.LC_TIME, 'es_ES.utf8')
        except Exception:
            pass
            
    fecha_actual = datetime.now().strftime("%d de %B de %Y")

    return render_template('certificado.html', 
                           usuario=usuario_actual, 
                           ingresos=ingresos_estimados_cop,
                           fecha=fecha_actual)

# =====================================================================
# 🛠️ PUBLICACIÓN Y ASIGNACIÓN DE ÓRDENES - OPTIMIZADO Y CORREGIDO
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
        
        # Limpiamos el campo por si vienen espacios en blanco
        tecnico_invitado = request.form.get('tecnico_invitado', '').strip()
        estado_inicial = 'Cotización Pendiente' if tecnico_invitado else 'Disponible'
        
        # Si la tarea es pública, lo dejamos como None para la BD
        correo_asignado = tecnico_invitado if tecnico_invitado else None
        
        try: 
            creditos_calculados = round(float(pago_cop) / VALOR_CREDITO_COP, 2)
        except Exception: 
            creditos_calculados = 1.0
            
        try:
            # ⚡ Creamos la nueva orden con la columna CORRECTA (trabajador_correo)
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
                trabajador_correo=correo_asignado  # 🔧 SOLUCIÓN EXACTA AQUÍ
            )
            
            db.session.add(nueva_tarea)
            db.session.commit() # Impacta atómicamente la base de datos
            
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
# 👤 GESTIÓN DE PERFIL, PORTAFOLIO Y KYC - UNIFICADO Y SEGURO
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
            
            # 💡 MAGIA BACKEND: Capturamos la sugerencia y la fusionamos si aplica
            sugerencia = request.form.get('sugerencia_profesion')
            if profesion == 'Otra' and sugerencia:
                # Se guarda en la DB exactamente como "Otra: [texto del usuario]"
                profesion = f"Otra: {sugerencia.strip()}"
            
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

                # 🛡️ 2. PROCESAR KYC (MÓDULO DE IDENTIDAD)
                foto_cedula = request.files.get('kyc_cedula')
                foto_selfie = request.files.get('kyc_selfie')
                kyc_actualizado = False
                
                if foto_cedula and foto_cedula.filename != '' and archivo_permitido(foto_cedula.filename):
                    nombre_ced = f"KYC_FRONTAL_{int(time.time())}_{secure_filename(foto_cedula.filename)}"
                    foto_cedula.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_ced))
                    usuario.kyc_cedula = nombre_ced
                    kyc_actualizado = True
                    
                if foto_selfie and foto_selfie.filename != '' and archivo_permitido(foto_selfie.filename):
                    nombre_selfie = f"KYC_SELFIE_{int(time.time())}_{secure_filename(foto_selfie.filename)}"
                    foto_selfie.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_selfie))
                    usuario.kyc_selfie = nombre_selfie
                    kyc_actualizado = True

                # 3. PROCESAR CARGA MÚLTIPLE DEL PORTAFOLIO
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
                
                # Mensajes dinámicos según lo que hizo el usuario
                if kyc_actualizado:
                    flash("✅ Documentos de identidad enviados correctamente. Nuestro equipo los validará en breve.", "success")
                elif proyectos_guardados > 0:
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

        # 🛡️ Métricas del sistema
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
# 💬 MÓDULO DE COMUNICACIÓN API HTTP (PROCESAMIENTO ASÍNCRONO) - BLINDADO
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
            tarea['estado'] = 'Cotización Pendiente'

        # 🔔 LIMPIEZA DE CAMPANITA
        Mensaje.query.filter(
            Mensaje.tarea_id == tarea_id,
            Mensaje.remitente_correo != correo_logueado,
            Mensaje.leido == 0
        ).update({"leido": 1}, synchronize_session=False)
        db.session.commit()
            
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Error actualizando metadatos de chat #{tarea_id}: {e}")

    if request.method == 'POST':
        mensaje_texto = request.form.get('mensaje')
        
        # 🛠️ Extraemos la lista completa y filtramos el input vacío
        archivos_enviados = request.files.getlist('imagen_adjunta')
        archivo = next((f for f in archivos_enviados if f and f.filename.strip()), None)
        
        if canal_sala == "Ninguno":
            flash("❌ Sala de negociación no inicializada.", "error")
            return redirect(url_for('ver_chat', tarea_id=tarea_id))

        # 🛡️ FILTRO INTELIGENTE DE MODERACIÓN DE TEXTO
        mensaje_final = mensaje_texto or "" 
        es_seguro = True
        
        if tarea['estado'] not in ['En Garantia', 'Finalizada'] and mensaje_texto:
            es_seguro, resultado_moderacion = es_mensaje_seguro(mensaje_texto)
            if not es_seguro:
                mensaje_final = resultado_moderacion

        nombre_unico = None
        tipo_mensaje = 'texto'
        
        try:
            # Si el archivo real pasó el filtro, lo procesamos
            if archivo and archivo_permitido(archivo.filename):
                # 📦 IMPORTS DE SEGURIDAD INYECTADOS ADENTRO
                from werkzeug.utils import secure_filename
                import time
                import os
                from PIL import Image
                
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
                    if os.path.exists(ruta_guardado):
                        os.remove(ruta_guardado)
                    
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
                
            elif mensaje_final.strip():
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
                
            db.session.commit() 
            
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
                'mensaje': (mensaje_final.strip() if mensaje_final else "") if tipo_mensaje == 'texto' else nombre_unico,
                'tipo': tipo_mensaje
            })

        return redirect(url_for('ver_chat', tarea_id=tarea_id))

    # =====================================================================
    # --- MÉTODO GET: HISTORIAL COMPLETO DE MENSAJES Y PERFILES ---
    # =====================================================================
    VALOR_CREDITO_COP = 10000
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
    
    # Datos estructurados del Técnico
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

    # Consulta de saldo final
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
# 💼 DISPARADOR DE OFERTAS ECONÓMICAS E HITOS ADICIONALES
# =====================================================================
@app.route('/chat/<int:tarea_id>/enviar_cotizacion', methods=['POST'])
def enviar_cotizacion(tarea_id):
    if 'usuario_nombre' not in session or session.get('usuario_rol') not in ['Trabajador', 'Worker']:
        return redirect(url_for('index'))
        
    correo_logueado = session['usuario_correo']
    canal_sala = request.form.get('canal_actual')
    concepto_original = request.form.get('concepto', '').strip()
    
    # 💡 MAGIA NUEVA: Capturar si esto viene del Modal de Hitos Adicionales
    es_hito_adicional = request.form.get('es_hito_adicional') == 'true'
    tipo_cobro = request.form.get('tipo_cobro', 'Cotización')
    
    # Enriquecer el concepto visualmente en la base de datos si es un extra
    if es_hito_adicional:
        concepto = f"{tipo_cobro}: {concepto_original}"
    else:
        concepto = concepto_original
    
    try:
        monto_pesos = float(request.form.get('monto_pesos', 0))
    except (ValueError, TypeError):
        monto_pesos = 0.0
    
    if monto_pesos <= 0 or not concepto_original:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Datos de cotización inválidos'}), 400
        flash("❌ Ingresa un valor en pesos válido y la descripción del cobro.", "error")
        return redirect(url_for('ver_chat', tarea_id=tarea_id))

    # 🚨 REGLA: Límite máximo por recibo individual de Escrow
    if monto_pesos > 1000000:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'El valor máximo permitido por cobro es de $1.000.000 COP.'}), 400
        flash("❌ El valor máximo permitido por recibo es de $1.000.000 COP por razones de seguridad de la pasarela.", "error")
        return redirect(url_for('ver_chat', tarea_id=tarea_id))
        
    contenido_cotizacion = f"{monto_pesos}|{concepto}"
    
    try:
        tarea_obj = Tarea.query.get(tarea_id)
        if not tarea_obj:
            return jsonify({'success': False, 'error': 'Requerimiento no encontrado'}), 404

        # Bloqueo estricto: Si ya cerraron el trato, no se cobra más
        if tarea_obj.estado == 'Finalizada':
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'El servicio ya fue cerrado y calificado.'}), 400
            flash("❌ Esta tarea ya está finalizada, no puedes generar más cobros.", "error")
            return redirect(url_for('ver_chat', tarea_id=tarea_id))

        # Crear la burbuja del cobro en el chat (como una factura pendiente)
        nueva_oferta = Mensaje(
            tarea_id=tarea_id,
            canal_trabajador=canal_sala,
            remitente_correo=correo_logueado,
            mensaje=contenido_cotizacion,
            tipo='cotizacion_pendiente',
            leido=0
        )
        db.session.add(nueva_oferta)
        
        # 💡 ACTUALIZACIÓN INTELIGENTE DE ESTADO: 
        # Solo regresamos la tarea a "Cotización Pendiente" si era la primera oferta de todas.
        # Si es un hito y ya estaban trabajando (En Garantia), no tocamos el estado principal.
        if not es_hito_adicional and tarea_obj.estado == 'Disponible':
            tarea_obj.estado = 'Cotización Pendiente'
            
        db.session.commit()
        
        msg_exito = f"📌 Cobro adicional por ${monto_pesos:,.0f} COP enviado." if es_hito_adicional else f"💼 Oferta de ${monto_pesos:,.0f} COP enviada exitosamente."
        flash(msg_exito, "success")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error crítico enviando cotización en tarea #{tarea_id}: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Error interno al procesar el cobro.'}), 500
        flash("❌ Ocurrió un error al procesar tu transacción. Inténtalo de nuevo.", "error")
        return redirect(url_for('ver_chat', tarea_id=tarea_id))
    
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
        
        # 💵 Conversión matemática exacta basada en tu regla de oro: 1 Crédito = $10.000 COP
        monto_creditos_flotante = round(monto_pesos / 10000, 2)
        
    except Exception as e:
        print(f"⚠️ Error de formato en cotización #{mensaje_id}: {e}")
        flash("❌ Formato económico incorrecto.", "error")
        return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=canal_sala))

    try:
        if accion == 'Aceptar':
            cliente = Usuario.query.filter_by(correo=correo_logueado).first()
            saldo_cliente = cliente.saldo_creditos if cliente else 0.0
            
            # 🛡️ CONTROL FINANCIERO: Si no le alcanza, lo mandamos directo a recargar con Bold
            if saldo_cliente < monto_creditos_flotante:
                flash(f"Saldo insuficiente. Esta labor requiere {monto_creditos_flotante} Créditos (${monto_pesos:,.0f} COP). ¡Recarga de forma segura aquí!", "error")
                return redirect(url_for('recargar_billetera'))
                
            # 💵 Retención segura en el fondo de garantía (Escrow) de inWorker
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
            
            # 🚨 Sincronización de estados en los mensajes del chat
            msg_cotizacion.tipo = 'cotizacion_aceptada'  
            
            # Declinamos las demás ofertas que estén pendientes en este mismo chat
            Mensaje.query.filter_by(tarea_id=tarea_id, tipo='cotizacion_pendiente')\
                         .update({Mensaje.tipo: 'cotizacion_declinada'}, synchronize_session=False)
            
            # 📢 Inyección del mensaje automático del sistema
            mensaje_sistema = Mensaje(
                tarea_id=tarea_id,
                canal_trabajador=canal_sala,
                remitente_correo='sistema@inworker.co',
                mensaje=f"✅ CONTRATO ASEGURADO: El cliente ha depositado ${monto_pesos:,.0f} COP en el fondo de garantía de inWorker. El especialista ya puede iniciar la ejecución del servicio de forma segura.",
                tipo='sistema'
            )
            db.session.add(mensaje_sistema)
            
            db.session.commit()
            
            # Sincronizamos las variables globales de sesión para actualizar la interfaz al instante
            session['saldo'] = cliente.saldo_creditos
            session['usuario_creditos'] = cliente.saldo_creditos
            flash("✔ ¡Propuesta aceptada! El depósito de garantía se encuentra congelado de manera segura.", "success")

        elif accion == 'Rechazar':
            msg_cotizacion.tipo = 'cotizacion_declinada'
            
            # Si se rechaza la cotización, la tarea vuelve a estar abierta para recibir otras ofertas
            tarea_obj = Tarea.query.get(tarea_id)
            if tarea_obj:
                tarea_obj.estado = 'Abierta'
                
            db.session.commit()
            flash("❌ Oferta declinada correctamente. El chat sigue abierto para más cotizaciones.", "error")
            
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
    VALOR_CREDITO_COP = 10000 # Regla de oro de inWorker
    
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
            creditos_totales = tarea.costo_creditos or 0.0
            tecnico_destino = tarea.trabajador_correo
            
            # Buscamos al especialista asignado para fonear su billetera
            tecnico = Usuario.query.filter_by(correo=tecnico_destino).first()
            
            if tecnico:
                # 🧮 REGLA DE ORO INWORKER: El técnico recibe el 88% neto
                creditos_tecnico = round(creditos_totales * 0.88, 2)
                saldo_actual_tecnico = tecnico.saldo_creditos or 0.0
                tecnico.saldo_creditos = round(saldo_actual_tecnico + creditos_tecnico, 2)
                
                # 🕵️‍♂️ MOTOR NINJA DE EMBAJADORES (DISPERSIÓN EN PILOTO AUTOMÁTICO)
                if tecnico.referido_por:
                    padrino = Usuario.query.filter_by(codigo_embajador=tecnico.referido_por).first()
                    
                    if padrino:
                        # 1. Validar ventana de tiempo (6 meses = 180 días)
                        from datetime import datetime
                        # Obtenemos la fecha actual en la base de datos o local
                        fecha_actual = db.func.current_timestamp()
                        
                        # Para evitar líos de zonas horarias en la comparación de Python, usamos una consulta directa o restamos días de forma segura
                        diferencia_tiempo = datetime.utcnow() - tecnico.fecha_registro
                        
                        if diferencia_tiempo.days <= 180:
                            # 2. Calcular la retención de inWorker (12%)
                            retencion_inworker = creditos_totales * 0.12
                            
                            # 3. Calcular el Rango del Padrino por volumen de reclutados
                            referidos_count = Usuario.query.filter_by(referido_por=padrino.codigo_embajador).count()
                            
                            if referidos_count <= 10:
                                porcentaje_padrino = 0.10  # Bronce
                            elif referidos_count <= 25:
                                porcentaje_padrino = 0.15  # Plata
                            elif referidos_count <= 50:
                                porcentaje_padrino = 0.20  # Oro
                            else:
                                porcentaje_padrino = 0.30  # Diamante (Gancho maestro)
                            
                            # 4. Asignar Comisión en créditos al Embajador
                            comision_padrino = round(retencion_inworker * porcentaje_padrino, 2)
                            
                            if comision_padrino > 0:
                                padrino.saldo_creditos = round((padrino.saldo_creditos or 0.0) + comision_padrino, 2)
                                print(f"🎁 Comisión de {comision_padrino} Cr asignada al Embajador {padrino.nombre} por el técnico {tecnico.nombre}")
            
            # Pasamos la orden al estado de cierre definitivo
            tarea.estado = 'Finalizada'
            
            # Formateamos el monto neto en pesos del Técnico para el historial
            try:
                monto_pesos_tecnico = f"${float(creditos_tecnico * VALOR_CREDITO_COP):,.0f}"
            except Exception:
                monto_pesos_tecnico = f"${creditos_tecnico * VALOR_CREDITO_COP:,.0f}"
                
            # Generamos el aviso oficial del sistema dentro de la sala de negociación
            mensaje_sistema = (
                f"SISTEMA: El servicio ha sido cerrado. El pago neto de {creditos_tecnico} Cr ({monto_pesos_tecnico} COP) "
                f"ha sido liberado de la garantía y transferido al saldo de {tarea.trabajador_nombre}. "
                f"¡Gracias por usar inWorker!"
            )
            
            nuevo_aviso = Mensaje(
                tarea_id=tarea_id,
                canal_trabajador=tarea.trabajador_correo,
                remitente_correo='baraka@inworker.com',
                mensaje=mensaje_sistema,
                tipo='texto',
                leido=0
            )
            db.session.add(nuevo_aviso)
            flash("✨ ¡Garantía liberada con éxito! Los fondos netos ya están en la billetera del especialista.", "success")
            
        # ⚡ Un solo commit impacta y bloquea toda la transacción de forma segura
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error crítico en pasarela de Escrow (Tarea #{tarea_id}): {e}")
        flash("❌ Ocurrió un error al procesar la liberación de la garantía.", "error")
        
    return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=tarea.trabajador_correo if tarea else None))


# =====================================================================
# ⭐ MÓDULO DE REPUTACIÓN Y CIERRE DEFINITIVO DE TAREA - OPTIMIZADO
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
        
        # 🛡️ FILTRO DE SEGURIDAD ACTUALIZADO: 
        # Ya no exigimos que el estado sea 'Finalizada' previamente, porque ESTA acción es la que finaliza el ciclo.
        if tarea and getattr(tarea, 'calificada', 0) == 0 and correo_logueado == tarea.cliente_correo:
            
            # Buscamos al técnico asignado para actualizar su reputación global
            tecnico = Usuario.query.filter_by(correo=tarea.trabajador_correo).first()
            
            if tecnico:
                # Incremento seguro manejando fallbacks por si los campos están en NULL/None
                tecnico.puntuacion_total = (tecnico.puntuacion_total or 0.0) + estrellas
                tecnico.total_calificaciones = (tecnico.total_calificaciones or 0) + 1
                
            # 💡 AQUÍ CERRAMOS EL CANDADO MAESTRO
            tarea.estado = 'Finalizada'
            tarea.calificada = 1
            
            # 🤖 Mensaje de cierre en la Sala de Negociación
            mensaje_sistema = Mensaje(
                tarea_id=tarea_id,
                canal_trabajador=tarea.trabajador_correo, # Usamos el correo del técnico como canal de sala
                remitente_correo='sistema@inworker.co',
                mensaje=f"⭐ SERVICIO CERRADO Y CALIFICADO. El cliente ha finalizado este requerimiento y ha otorgado {estrellas} estrellas al especialista. ¡Gracias por usar el ecosistema inWorker!",
                tipo='sistema'
            )
            db.session.add(mensaje_sistema)
            
            # Consolidamos la transacción de manera atómica
            db.session.commit()
            flash("⭐ ¡Servicio finalizado y especialista calificado con éxito!", "success")
            
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error crítico al procesar calificación de tarea #{tarea_id}: {e}")
        flash("❌ Ocurrió un error interno al guardar tu calificación.", "error")
        
    # Redirigimos al chat (que ahora mostrará la pantalla de "Chat Cerrado" porque el estado es Finalizada)
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
        return redirect(url_for('listar_tecnicos'))  # Cambia 'listar_tecnicos' si tu ruta se llama distinto
    
    # 📍 NUEVA UBICACIÓN POR DEFECTO: BOGOTÁ D.C.
    lat = request.form.get('latitud', 4.6097)
    lng = request.form.get('longitud', -74.0817)
    zona = request.form.get('zona', 'Bogotá (Privado)')
    
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

        # 🚀 INYECCIÓN DEL "PUNTO 2": DISPARAR EL CORREO AL TÉCNICO EN SEGUNDO PLANO
        tecnico_data = Usuario.query.filter_by(correo=tecnico_correo).first()
        if tecnico_data:
            hilo_alerta = threading.Thread(
                target=enviar_notificacion_asignacion, 
                args=(current_app._get_current_object(), tecnico_data.correo, tecnico_data.nombre, nueva_tarea.titulo)
            )
            hilo_alerta.start()
        
        flash("💼 Consulta privada iniciada con éxito y especialista notificado.", "success")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error crítico creando consulta privada: {e}")
        flash("❌ No se pudo inicializar la sala privada por un error interno.", "error")
        return redirect(url_for('listar_tecnicos'))
    
    # Redirección nativa y ultra-segura usando url_for para el chat de negociación
    return redirect(url_for('ver_chat', tarea_id=id_tarea))

# =====================================================================
# 💰 WEBHOOK CENTRAL DE BOLD (ACTUALIZADO CON NUEVA REFERENCIA)
# =====================================================================
@app.route('/webhook-bold', methods=['POST'])
def webhook_bold():
    payload = request.json or {}
    print(f"🔔 WEBHOOK BOLD RECIBIDO: {payload}")
    
    try:
        # 1. Extraemos el tipo de evento directamente del JSON de Bold
        estado = payload.get('type') or ''
        print(f"🔍 [Paso 1] Estado del evento detectado: '{estado}'")
        
        if 'APPROVED' in str(estado).upper() or 'SUCCESS' in str(estado).upper():
            data = payload.get('data', {})
            
            # 2. Navegamos de forma segura en la estructura profunda de Bold
            referencia = data.get('metadata', {}).get('reference', '')
            print(f"🔍 [Paso 2] Referencia extraída: '{referencia}'")
            
            if not referencia.startswith('RECARGA-'):
                print(f"⚠️ [Ignorado] La referencia '{referencia}' no es una recarga de billetera.")
                return jsonify({"status": "ignored", "message": "No es una recarga"}), 200
            
            # 3. Rompemos la referencia para sacar el ID y los CRÉDITOS
            # Nuevo formato: RECARGA-{ID}-{CREDITOS}-{TIMESTAMP}
            partes = referencia.split('-')
            
            # Verificamos que tenga al menos 3 partes
            if len(partes) >= 3:
                usuario_id = int(partes[1])
                # ¡LA MAGIA! Sacamos los créditos exactos que pidió el usuario desde la referencia
                creditos_comprados = float(partes[2]) 
                
                print(f"🔍 [Paso 3] ID de usuario extraído: {usuario_id}")
                print(f"🔍 [Paso 4] Créditos extraídos de la referencia: {creditos_comprados}")
                
                # Extraemos el total pagado solo para el registro o para el correo (ya incluye la comisión)
                monto = float(data.get('amount', {}).get('total', 0))
                print(f"🔍 [Paso 5] Monto bruto pagado en Bold: ${monto} COP")
                
                # 4. Buscamos al usuario en la BD
                usuario = Usuario.query.get(usuario_id)
                if usuario:
                    saldo_anterior = usuario.saldo_creditos or 0.0
                    
                    # Sumamos los créditos limpios, sin importar cuánto cobró Bold
                    usuario.saldo_creditos = round(saldo_anterior + creditos_comprados, 2)
                    
                    # Guardamos físicamente en la Base de Datos
                    db.session.commit()
                    print(f"✅ [ÉXITO BASE DE DATOS] Usuario ID {usuario.id} actualizado. Saldo anterior: {saldo_anterior} -> Nuevo Saldo: {usuario.saldo_creditos}")
                    
                    # 📩 SOPORTE DE CORREO:
                    # Descomenta esta línea si vas a usar tu función de envío de correos
                    # enviar_correo_recarga(usuario.correo, usuario.nombre, monto, referencia)
                    
                    return jsonify({"status": "success", "message": "Créditos inyectados correctamente en BD"}), 200
                else:
                    print(f"❌ [ERROR] No se encontró ningún usuario en la BD con el ID: {usuario_id}")
                    return jsonify({"status": "error", "message": "Usuario no encontrado"}), 404
            else:
                print("❌ [ERROR] La estructura de la referencia está mal formada o es una versión vieja.")
                return jsonify({"status": "error", "message": "Referencia mal formada"}), 400
        else:
            print(f"⚠️ [Ignorado] El pago no está aprobado. Estado actual: '{estado}'")
            return jsonify({"status": "ignored", "message": "Transacción no aprobada"}), 200
            
    except Exception as e:
        db.session.rollback()
        print(f"❌ [ERROR CRÍTICO INTERNO]: {e}")
        return jsonify({"status": "error", "message": "Error interno del servidor"}), 500

# =====================================================================
# 🔄 ACTUALIZADOR AUTOMÁTICO DE SESIÓN (Sincroniza BD con la Pantalla)
# =====================================================================
@app.before_request
def actualizar_saldo_sesion():
    # Si el usuario tiene una sesión activa, actualizamos sus créditos desde la BD real
    if 'usuario_id' in session:
        try:
            usuario = Usuario.query.get(session['usuario_id'])
            if usuario:
                session['usuario_creditos'] = usuario.saldo_creditos or 0.0
        except Exception:
            pass # Evita que se caiga la app si la base de datos está ocupada

# =====================================================================
# 🏁 TRABAJADOR: ENTREGAR TRABAJO Y SOLICITAR PAGO
# =====================================================================
@app.route('/chat/<int:tarea_id>/solicitar_liberacion', methods=['POST'])
def solicitar_liberacion(tarea_id):
    if 'usuario_correo' not in session:
        return redirect(url_for('login'))
        
    canal_sala = request.form.get('canal_actual')
    correo_logueado = session['usuario_correo']
    
    try:
        # 1. Opcional pero recomendado: Actualizamos el estado de la tarea
        tarea = Tarea.query.get(tarea_id)
        if tarea and tarea.trabajador_correo == correo_logueado:
            tarea.estado = 'Esperando Liberacion' # O el estado que manejes en tu flujo
            
        # 2. Inyectamos un mensaje en el chat avisando al cliente
        mensaje_sistema = Mensaje(
            tarea_id=tarea_id,
            canal_trabajador=canal_sala,
            remitente_correo=correo_logueado,
            mensaje="🛎️ HE TERMINADO: El técnico ha marcado este servicio como 'Entregado'. Cliente, por favor revisa el trabajo y si todo está correcto, libera los fondos.",
            tipo='sistema'
        )
        db.session.add(mensaje_sistema)
        db.session.commit()
        
        flash("✅ Has notificado al cliente que el trabajo está terminado. Espera la liberación de fondos.", "success")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error al solicitar liberación: {e}")
        flash("❌ Error interno al enviar la notificación.", "error")
        
    # 🚨 Paréntesis de cierre corregido aquí abajo:
    return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=canal_sala))

# =====================================================================
# 💸 CLIENTE: LIBERAR FONDOS AL TRABAJADOR (CIERRE DE HITO / CICLO)
# =====================================================================
@app.route('/chat/<int:tarea_id>/liberar_fondos', methods=['POST'])
def liberar_fondos(tarea_id):
    if 'usuario_correo' not in session:
        return redirect(url_for('login'))
        
    canal_sala = request.form.get('canal_actual')
    
    try:
        tarea = Tarea.query.get_or_404(tarea_id)
        
        # Validamos que esté en garantía y tenga un técnico asignado
        if tarea.estado != 'En Garantia' or not tarea.trabajador_correo:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'Esta orden no está en garantía.'}), 400
            flash("❌ Esta orden no está en garantía o no tiene un trabajador asignado.", "error")
            return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=canal_sala))
            
        # Buscamos al trabajador para pagarle
        trabajador = Usuario.query.filter_by(correo=tarea.trabajador_correo).first()
        if not trabajador:
            flash("❌ Error: No se encontró la cuenta del técnico.", "error")
            return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=canal_sala))
            
        # Buscamos al cliente para validar el Bono de Doble Punta
        cliente = Usuario.query.filter_by(correo=tarea.cliente_correo).first()
            
        # 💰 TRANSFERENCIA DE CRÉDITOS Y DIVISIÓN DE COMISIONES
        costo_servicio = tarea.costo_creditos or 0.0
        
        # 🧮 REGLA DE ORO INWORKER: El técnico recibe el 88% neto
        creditos_tecnico = round(costo_servicio * 0.88, 2)
        saldo_tecnico_actual = trabajador.saldo_creditos or 0.0
        trabajador.saldo_creditos = round(saldo_tecnico_actual + creditos_tecnico, 2)
        
        # 🕵️‍♂️ MOTOR DE EMBAJADORES (PROGRAMA DE CRECIMIENTO EN PILOTO AUTOMÁTICO)
        if trabajador.referido_por:
            padrino = Usuario.query.filter_by(codigo_embajador=trabajador.referido_por).first()
            
            if padrino:
                # 1. Calcular la retención total de inWorker (12%)
                retencion_inworker = costo_servicio * 0.12
                
                # 2. Inicializar lógica de comisiones y bonos según el nivel del Padrino
                nivel = padrino.nivel_embajador or 1
                porcentaje_base = 0.18
                porcentaje_bono = 0.03
                
                if nivel == 2:    # Líder
                    porcentaje_base = 0.22
                    porcentaje_bono = 0.04
                elif nivel == 3:  # Director Regional
                    porcentaje_base = 0.25
                    porcentaje_bono = 0.05
                
                # 3. ¿El cliente que pagó también fue referido por este mismo Padrino? (Bono de Doble Punta)
                cliente_es_referido_propio = cliente and cliente.referido_por == padrino.codigo_embajador
                
                if cliente_es_referido_propio:
                    porcentaje_final = porcentaje_base + porcentaje_bono
                    print(f"🔥 ¡Bono de Doble Punta activado! {padrino.nombre} se lleva el {porcentaje_final * 100}%")
                else:
                    porcentaje_final = porcentaje_base
                    print(f"💼 Comisión base asignada: {porcentaje_final * 100}%")
                
                # 4. Asignar Comisión en créditos al Embajador
                comision_padrino = round(retencion_inworker * porcentaje_final, 2)
                
                if comision_padrino > 0:
                    padrino.saldo_creditos = round((padrino.saldo_creditos or 0.0) + comision_padrino, 2)
                    print(f"🎁 Comisión de {comision_padrino} Cr asignada al Embajador {padrino.nombre}")
                
                # 5. Sumar +1 servicio completado a la red de este Embajador
                padrino.servicios_red = (padrino.servicios_red or 0) + 1
                
                # 6. Lógica de ascensos automáticos por mérito (Servicios Efectivos)
                nuevo_nivel = padrino.nivel_embajador
                if padrino.servicios_red >= 1000 and padrino.nivel_embajador < 3:
                    nuevo_nivel = 3  # Asciende a Director Regional
                elif padrino.servicios_red >= 100 and padrino.nivel_embajador < 2:
                    nuevo_nivel = 2  # Asciende a Líder
                
                if nuevo_nivel != padrino.nivel_embajador:
                    padrino.nivel_embajador = nuevo_nivel
                    print(f"🏆 ¡EL EMBAJADOR {padrino.nombre} HA ASCENDIDO AL NIVEL {nuevo_nivel}! Servicios red: {padrino.servicios_red}")

        # 💡 CIRUGÍA NINJA: Mantenemos el chat vivo y reseteamos el ciclo de pago
        tarea.estado = 'Cotización Pendiente'
        tarea.confirmacion_cliente = 0
        tarea.confirmacion_trabajador = 0
        
        # Inyectamos el mensaje del sistema invitando a continuar
        mensaje_sistema = Mensaje(
            tarea_id=tarea_id,
            canal_trabajador=canal_sala,
            remitente_correo='sistema@inworker.co',
            mensaje=f"🎉 ¡PAGO LIBERADO! Se han transferido {creditos_tecnico} Créditos netos a la billetera del especialista.\n\n🔒 El chat sigue abierto y protegido por inWorker. Si desean continuar con un siguiente paso, el especialista puede generar un nuevo cobro desde aquí.",
            tipo='sistema'
        )
        db.session.add(mensaje_sistema)
        
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type and 'multipart/form-data' in request.content_type:
            return jsonify({'success': True})
            
        flash("🎉 ¡Fondos liberados con éxito!", "success")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error crítico al liberar fondos: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Error interno al procesar el pago.'}), 500
        flash("❌ Ocurrió un error al procesar el pago al técnico.", "error")
        
    return redirect(url_for('ver_chat', tarea_id=tarea_id, trabajador_email=canal_sala))

# =====================================================================
# ⚖️ ENDPOINT DE ARBITRAJE DE DISPUTAS CON IA (FASE 1.1 - BLINDADO)
# =====================================================================
@app.route('/admin/disputa/<int:tarea_id>')
def analizar_disputa_admin(tarea_id):
    # 🛡️ PROTECCIÓN AMIGABLE: Validar sesión y rol de administrador
    if 'usuario_correo' not in session or session.get('usuario_rol') != 'Admin':
        return jsonify({"error": "Acceso denegado. Se requieren permisos de administrador."}), 403
        
    # 1. Usar SQLAlchemy en lugar de sqlite3 crudo para no bloquear el disco en Render
    tarea = Tarea.query.get(tarea_id)
    
    if not tarea:
        return jsonify({"error": "La tarea no existe"}), 404
        
    # 2. Traer el historial de mensajes del chat de esa tarea
    mensajes_db = Mensaje.query.filter_by(tarea_id=tarea_id).order_by(Mensaje.id.asc()).all()
    mensajes = [{"remitente_correo": m.remitente_correo, "mensaje": m.mensaje, "fecha_envio": m.fecha_envio} for m in mensajes_db]
    
    if not mensajes:
        return jsonify({"error": "No hay mensajes en el chat de esta tarea para analizar."}), 400
        
    # Importamos el módulo e invocamos a Gemini
    from disputas_ia import analizar_disputa_chat
    
    # Armamos el diccionario para la IA
    tarea_dict = {
        "id": tarea.id, "titulo": tarea.titulo, "estado": tarea.estado, 
        "cliente_correo": tarea.cliente_correo, "trabajador_correo": tarea.trabajador_correo
    }
    
    reporte_ia = analizar_disputa_chat(mensajes, tarea_dict)
    
    # ✨ FORMATEO FORENSE INTEGRADO
    texto_analisis = (
        f"🤖 VEREDICTO RECOMENDADO: {reporte_ia.get('veredicto_sugerido', 'REVISIÓN_MANUAL')}\n"
        f"📊 Propuesta de Distribución:\n"
        f"   - Al Especialista (Trabajador): {reporte_ia.get('porcentaje_trabajador', 50)}%\n"
        f"   - Al Cliente: {reporte_ia.get('porcentaje_cliente', 50)}%\n\n"
        f"📝 Justificación Forense:\n"
        f"{reporte_ia.get('justificacion', 'Sin observaciones adicionales por el motor.')}"
    )
        
    return jsonify({
        "success": True,
        "tarea_id": tarea_id,
        "titulo_tarea": tarea.titulo,
        "estado_actual": tarea.estado,
        "analisis_ia": texto_analisis
    })

# =====================================================================
# ⚖️ RESOLUCIÓN MANUAL DE DISPUTAS (ARBITRAJE ADMINISTRATIVO) - BLINDADO
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

        # 2. Ejecución del veredicto manual según la opción seleccionada
        if resolucion == 'reembolso_total':
            # 100% de vuelta al balance del Cliente
            cliente_user = Usuario.query.filter_by(correo=tarea.cliente_correo).first()
            if cliente_user:
                cliente_user.saldo_creditos = round((cliente_user.saldo_creditos or 0.0) + creditos, 2)
            mensaje_flash = f"⚖️ Arbitraje finalizado: Se reembolsaron {creditos:,.1f} Cr al Cliente exitosamente."
            
        elif resolucion == 'pago_total':
            # 100% liberado al Especialista/Trabajador (CORRECCIÓN AQUÍ: era trabajador_correo)
            tecnico_user = Usuario.query.filter_by(correo=tarea.trabajador_correo).first()
            if tecnico_user:
                tecnico_user.saldo_creditos = round((tecnico_user.saldo_creditos or 0.0) + creditos, 2)
            mensaje_flash = f"⚖️ Arbitraje finalizado: Se liberaron {creditos:,.1f} Cr al Especialista exitosamente."
            
        elif resolucion == 'mitad_mitad':
            # División salomónica 50% / 50%
            mitad = round(creditos / 2, 2)
            
            cliente_user = Usuario.query.filter_by(correo=tarea.cliente_correo).first()
            if cliente_user:
                cliente_user.saldo_creditos = round((cliente_user.saldo_creditos or 0.0) + mitad, 2)
                
            tecnico_user = Usuario.query.filter_by(correo=tarea.trabajador_correo).first()
            if tecnico_user:
                tecnico_user.saldo_creditos = round((tecnico_user.saldo_creditos or 0.0) + mitad, 2)
                
            mensaje_flash = f"⚖️ Arbitraje finalizado: Fondos divididos equitativamente ({mitad:,.1f} Cr para cada uno)."
            
        else:
            flash("❌ Tipo de resolución inválida en el formulario.", "error")
            return redirect(url_for('home'))

        # 3. Sacamos la tarea de la sección de arbitraje
        tarea.estado = 'Finalizada'
        
        # ⚡ Un solo commit asienta toda la resolución
        db.session.commit()
        flash(mensaje_flash, "success")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error crítico en resolución de disputa para tarea #{tarea_id}: {e}")
        flash("❌ Ocurrió un error interno al ejecutar el arbitraje.", "error")

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

# =========================================================================
# 🔒 ENDPOINT: ELIMINACIÓN SEGURA DE CUENTA (VERSIÓN SQLALCHEMY)
# =========================================================================
@app.route('/api/usuario/eliminar_cuenta', methods=['POST'])
def api_eliminar_cuenta():
    if 'usuario_correo' not in session:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
        
    correo_usuario = session['usuario_correo']
    
    try:
        # 1. Traer los datos del usuario usando tu modelo SQLAlchemy
        usuario = Usuario.query.filter_by(correo=correo_usuario).first()
        
        if not usuario:
            return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404

        # 🛑 CANDADO 1: Validar el saldo usando la columna 'saldo_creditos'
        # Usamos getattr() para que Python no falle si el modelo no está 100% mapeado
        saldo_actual = getattr(usuario, 'saldo_creditos', 0)
        
        if saldo_actual and float(saldo_actual) > 0:
            return jsonify({
                'success': False, 
                'error': f'No puedes eliminar tu cuenta si aún tienes saldo disponible ({saldo_actual} créditos). Por favor, solicita un retiro primero.'
            }), 400

        # 🛑 CANDADO 2: Validar que no tenga servicios en Escrow
        # Asumiendo que tu modelo se llama Tarea
        tareas_activas = Tarea.query.filter(
            ((Tarea.cliente_correo == correo_usuario) | (Tarea.trabajador_correo == correo_usuario)),
            Tarea.estado.in_(['En Garantia', 'Cotización Pendiente', 'En Progreso'])
        ).count()
        
        if tareas_activas > 0:
            return jsonify({
                'success': False, 
                'error': 'No puedes eliminar tu cuenta. Tienes servicios o contratos en ejecución con fondos en garantía (Escrow).'
            }), 400

        # 🥷 BORRADO SEGURO (Soft Delete)
        usuario.estado_cuenta = 'Inactivo'
        usuario.telefono = 'ELIMINADO'
        usuario.habilidades = 'Cuenta eliminada voluntariamente.'
        usuario.verificado = 0
        
        # Guardamos los cambios
        db.session.commit()
        
        # 🧼 Limpiamos la sesión del navegador
        session.clear()
        
        return jsonify({
            'success': True,
            'message': 'Tu cuenta ha sido dada de baja de manera segura y tus datos personales han sido removidos conforme a la ley.'
        })

    except Exception as e:
        db.session.rollback()  # Revertir cualquier cambio a medias si algo explota
        print(f"❌ Error crítico al eliminar cuenta de {correo_usuario}: {e}")
        return jsonify({'success': False, 'error': f'Error interno en el servidor: {str(e)}'}), 500

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