# disputas_ia.py
from google import genai
from google.genai import types
import os

def analizar_disputa_chat(historial_mensajes, datos_tarea):
    """
    Envía el historial de un chat en conflicto a la API de Gemini para evaluar quién tiene la razón
    según los términos de Barakah Tech Hub S.A.S. utilizando el nuevo SDK 'google-genai'.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "TU_API_KEY_TEMPORAL")

    # Si no hay API KEY configurada todavía, devolvemos una simulación segura para que no se caiga
    if not os.environ.get("GEMINI_API_KEY") or api_key == "TU_API_KEY_TEMPORAL":
        return {
            "veredicto_sugerido": "REVISIÓN_MANUAL",
            "porcentaje_trabajador": 50,
            "porcentaje_cliente": 50,
            "justificacion": "API Key de Gemini no configurada en el entorno de Render. Se requiere revisión manual."
        }

    # Formateamos el historial del chat para la IA
    chat_plano = ""
    for msg in historial_mensajes:
        chat_plano += f"[{msg['fecha_envio']}] {msg['remitente_correo']}: {msg['mensaje']}\n"

    # Construimos el Prompt Pericial
    prompt = f"""
    Eres el árbitro de mediación automatizado de la plataforma inWorker (desarrollado por BARAKAH TECH HUB S.A.S.).
    Tu labor es auditar las conversaciones de un servicio que entró en disputa para decidir cómo liberar los fondos retenidos en Escrow de forma justa.

    DATOS DEL CONTRATO/SERVICIO:
    - ID de Tarea: {datos_tarea.get('id')}
    - Título del Servicio: {datos_tarea.get('titulo')}
    - Descripción Original: {datos_tarea.get('descripcion')}
    - Presupuesto en Custodia: {datos_tarea.get('costo_creditos')} Créditos

    HISTORIAL DE NEGOCIACIÓN EN EL CHAT:
    {chat_plano}

    INSTRUCCIONES DE EVALUACIÓN:
    1. Determina si el Trabajador demostró o entregó evidencia de haber realizado la labor.
    2. Determina si el Cliente está reteniendo el pago de manera injustificada o si tiene motivos reales de insatisfacción.
    3. Recomienda una división justa de los Créditos en custodia (0% a 100%).

    RESPONDE ESTRICTAMENTE EN EL SIGUIENTE FORMATO JSON:
    {{
      "veredicto_sugerido": "LIBERAR_AL_TECNICO" o "REEMBOLSAR_AL_CLIENTE" o "DIVIDIR_FONDOS",
      "porcentaje_trabajador": número de 0 a 100,
      "porcentaje_cliente": número de 0 a 100,
      "justificacion": "Escribe aquí un resumen ejecutivo de 3 líneas explicando detalladamente qué pasó en el chat y por qué tomas esta decisión."
    }}
    """

    try:
        # Inicializamos el cliente moderno del paquete 'google-genai'
        client = genai.Client(api_key=api_key)
        
        # Consumo con estructura estricta de JSON en el nuevo SDK
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        import json
        return json.loads(response.text.strip())
        
    except Exception as e:
        # Resguardo de seguridad por si falla la conexión de red o parsing
        return {
            "veredicto_sugerido": "REVISIÓN_MANUAL",
            "porcentaje_trabajador": 50,
            "porcentaje_cliente": 50,
            "justificacion": f"Falla técnica en el motor de arbitraje: {str(e)}"
        }