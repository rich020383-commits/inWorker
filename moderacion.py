import re

def es_mensaje_seguro(texto_mensaje):
    """
    Analiza el texto de un chat para detectar datos de contacto (teléfonos, correos, links, direcciones).
    Retorna (True, texto_original) si es seguro.
    Retorna (False, mensaje_advertencia) si infringe las políticas de Barakah Tech Hub S.A.S.
    """
    if not texto_mensaje:
        return True, ""

    texto_minusculas = texto_mensaje.lower()

    # 1. Normalización: Convierte números escritos en palabras a dígitos comunes en Colombia
    numeros_palabras = {
        'cero': '0', 'uno': '1', 'dos': '2', 'tres': '3', 'cuatro': '4',
        'cinco': '5', 'seis': '6', 'siete': '7', 'ocho': '8', 'nueve': '9',
        'trez': '3', 'seiz': '6'
    }

    texto_normalizado = texto_minusculas
    for palabra, digito in numeros_palabras.items():
        texto_normalizado = re.sub(r'\b' + palabra + r'\b', digito, texto_normalizado)

    # Quitar espacios y caracteres especiales para detectar números camuflados (Ej: 3.1.2 4.5.6)
    texto_compacto = re.sub(r'[\s\.\-_,/\*]', '', texto_normalizado)

    # 2. Patrones de Detección Avanzada
    # Celulares colombianos: 10 dígitos empezando en 3 (admite separadores ya eliminados)
    # Fijos: código de área (1,4,5,6,7,8) + 7 dígitos, con límites de palabra
    patron_telefono = r'\b3\d{9}\b|\b[145678]\d{6}\b' # Sin el \d{7} genérico que bloqueaba precios y partes
    patron_correo = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    patron_enlaces = r'(www\.|http://|https://|\.com|\.co|\.net|instagram|facebook|wpp|whatsapp|face|insta)'

    palabras_bloqueadas = ['calle', 'carrera', 'diagonal', 'avenida', ' nro', ' cll', ' cra', ' #', ' nomenclatura', 'manzana', ' mz ']
    contiene_direccion = any(palabra in texto_minusculas for palabra in palabras_bloqueadas)

    # 3. Evaluación del Mensaje
    if (re.search(patron_telefono, texto_compacto) or
        re.search(patron_correo, texto_minusculas) or
        re.search(patron_enlaces, texto_minusculas) or
        contiene_direccion):

        advertencia = (
            "⚠️ Sistema de seguridad inWorker: Por tu protección y para conservar la garantía de Escrow, "
            "no está permitido compartir números, correos, redes sociales ni direcciones antes de congelar el depósito."
        )
        return False, advertencia

    return True, texto_mensaje