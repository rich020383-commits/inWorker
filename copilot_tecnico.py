# copilot_tecnico.py
import google.generativeai as genai
import os

# Usará la misma API KEY que ya configuramos en Render
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "TU_API_KEY_TEMPORAL"))

def optimizar_perfil_trabajador(descripcion_actual, habilidades, ciudad):
    """
    Toma los datos planos de un técnico y redacta una biografía profesional atractiva
    para aumentar su tasa de contratación en inWorker.
    """
    if not os.environ.get("GEMINI_API_KEY") and "TU_API_KEY_TEMPORAL" in os.environ.get("GEMINI_API_KEY", "TU_API_KEY_TEMPORAL"):
        return {
            "biografia_optimizada": descripcion_actual,
            "sugerencia_tags": habilidades
        }

    prompt = f"""
    Eres un experto en Marketing Personal y Reclutamiento de Talento Humano en Colombia.
    Tu objetivo es transformar la descripción de perfil de un trabajador técnico en la plataforma inWorker para que se vea altamente profesional, confiable y comercial.

    DATOS ACTUALES DEL TRABAJADOR:
    - Ubicación: {ciudad}
    - Habilidades/Servicios: {habilidades}
    - Descripción actual: "{descripcion_actual}"

    INSTRUCCIONES:
    1. Redacta una biografía profesional de máximo 4 líneas.
    2. Usa un tono cercano, confiable y muy técnico (orientado al público colombiano).
    3. Resalta el cumplimiento, la calidad y la seguridad del servicio.
    4. Devuelve el resultado ESTRICTAMENTE en formato JSON.

    FORMATO DE RESPUESTA JSON:
    {{
      "biografia_optimizada": "Escribe aquí la nueva descripción redactada impecablemente.",
      "consejo_adicional": "Un consejo corto de 1 línea para que el técnico mejore su portafolio de evidencias."
    }}
    """

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        
        import json
        texto_limpio = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(texto_limpio)
    except Exception as e:
        return {
            "biografia_optimizada": descripcion_actual,
            "consejo_adicional": f"No se pudo optimizar en este momento: {str(e)}"
        }