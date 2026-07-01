# disputas_ia.py
import google.generativeai as genai
import os

# Configuración de la API (Gemini es gratis para desarrollo en Google AI Studio)
# Debes configurar la variable de entorno GEMINI_API_KEY en Render o local
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "TU_API_KEY_TEMPORAL"))

def analizar_disputa_chat(historial_mensajes, datos_tarea):
    """
    Envía el historial de un chat en conflicto a Gemini para evaluar quién tiene la razón
    según los términos de Barakah Tech Hub S.A.S.
    """
    # Si no hay API KEY configurada todavía, devolvemos una simulación segura para que no se caiga
    if not os.environ.get("GEMINI_API_KEY") and "TU_API_KEY_TEMPORAL" in os.environ.get("GEMINI_API_KEY", "TU_API_KEY_TEMPORAL"):
        return {
            "veredicto_sugerido": "REVISIÓN_MANUAL",
            "porcentaje_trabajador": 50,
            "porcentaje_cliente": 50,
            "justificacion": "API Key de Gemini no configurada en el servidor. Se requiere revisión manual."
        }

    # Formateamos el historial del chat para la IA
    chat_plano = ""
    for msg in historial_mensajes:
        chat_plano += f"[{msg['fecha_envio']}] {msg['remitente_correo']}: {msg['mensaje']}\n"

    # Diseñamos el prompt del sistema para el arbitraje
    prompt = f"""
    Actúa como un Árbitro Legal y Mediador Comercial Privado para la plataforma inWorker (propiedad de BARAKAH TECH HUB S.A.S. en Colombia).
    Tu trabajo es analizar de forma imparcial el siguiente chat de negociación para resolver una disputa por créditos congelados (Escrow).

    DATOS DE LA ORDEN DE SERVICIO (TAREA):
    - Título: {datos_tarea['titulo']}
    - Descripción: {datos_tarea['descripcion']}
    - Valor Pactado (COP): {datos_tarea['pago']}
    - Créditos en disputa: {datos_tarea['costo_creditos']} Cr

    HISTORIAL DEL CHAT DE NEGOCIACIÓN:
    {chat_plano}

    INSTRUCCIONES DE EVALUACIÓN:
    1. Determina si el Trabajador demostró o entregó evidencia de haber realizado la labor.
    2. Determina si el Cliente está reteniendo el pago de manera injustificada o si tiene motivos reales de insatisfacción.
    3. Recomienda una división justa de los Créditos en custodia (0% a 100%).

    RESPONDE ESTRICTAMENTE EN EL SIGUIENTE FORMATO JSON (No agregues texto afuera del JSON):
    {{
      "veredicto_sugerido": "LIBERAR_AL_TECNICO" o "REEMBOLSAR_AL_CLIENTE" o "DIVIDIR_FONDOS",
      "porcentaje_trabajador": número de 0 a 100,
      "porcentaje_cliente": número de 0 a 100,
      "justificacion": "Escribe aquí un resumen ejecutivo de 3 líneas explicando detalladamente qué pasó en el chat y por qué tomas esta decisión."
    }}
    """

    try:
        model = genai.GenerativeModel("gemini-2.5-flash") # El modelo más rápido y óptimo
        response = model.generate_content(prompt)
        
        # Limpieza simple de la respuesta para asegurar que sea JSON puro
        texto_limpio = response.text.strip().replace("```json", "").replace("```", "")
        import json
        return json.loads(texto_limpio)
    except Exception as e:
        return {
            "veredicto_sugerido": "ERROR_PROCESAMIENTO",
            "porcentaje_trabajador": 50,
            "porcentaje_cliente": 50,
            "justificacion": f"Error técnico al invocar el motor de IA: {str(e)}"
        }