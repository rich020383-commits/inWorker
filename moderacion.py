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
    # Fijos actuales: '60' + código de área + 7 dígitos (10 dígitos, ej: 6012345678)
    # Fijos antiguos: 7 dígitos SOLO si van agrupados con separador (ej: '234 5678',
    #                 '234-5678'), para no bloquear cédulas ni valores escritos seguidos.
    #                 Se busca sobre texto_normalizado (mantiene espacios/guiones).
    # Se usan lookarounds en lugar de \b porque al compactar el texto el número
    # queda pegado a letras (ej: 'fijo6012345678') y \b deja de coincidir.
    patron_telefono = r'(?<!\d)3\d{9}(?!\d)|(?<!\d)60\d{8}(?!\d)'
    # Mismo razonamiento: lookarounds en vez de \b (tras compactar el número puede
    # quedar pegado a letras, ej: '1234567largo').
    patron_fijo_separado = r'(?<!\d)\d{3}[\s\-]\d{4}(?!\d)'
    patron_correo = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    patron_enlaces = r'(www\.|http://|https://|\.com|\.co|\.net|instagram|facebook|wpp|whatsapp|face|insta)'

    palabras_bloqueadas = ['calle', 'carrera', 'diagonal', 'avenida', ' nro', ' cll', ' cra', ' #', ' nomenclatura', 'manzana', ' mz ']
    contiene_direccion = any(palabra in texto_minusculas for palabra in palabras_bloqueadas)

    # 3. Evaluación del Mensaje
    if (re.search(patron_telefono, texto_compacto) or
        re.search(patron_fijo_separado, texto_normalizado) or
        re.search(patron_correo, texto_minusculas) or
        re.search(patron_enlaces, texto_minusculas) or
        contiene_direccion):

        advertencia = (
            "⚠️ Sistema de seguridad inWorker: Por tu protección y para conservar la garantía de Escrow, "
            "no está permitido compartir números, correos, redes sociales ni direcciones antes de congelar el depósito."
        )
        return False, advertencia

    return True, texto_mensaje