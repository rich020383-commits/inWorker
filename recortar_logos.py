from PIL import Image
import os

# Asegurar la existencia de la carpeta
os.makedirs('static/img', True)

try:
    # Cargar la imagen original de la hoja de marca
    img = Image.open('hoja_marca.jpg')
    ancho, alto = img.size
    
    # 1. Recortar el Logo Horizontal Oficial (Isotipo + Texto inWorker)
    # Se ubica en la franja superior de la hoja de marca
    box_logo = (int(ancho * 0.05), int(alto * 0.10), int(ancho * 0.95), int(alto * 0.35))
    logo_horizontal = img.crop(box_logo)
    # Redimensionarlo un poco para que mantenga buena resolución en el header sin pesar de más
    logo_horizontal.thumbnail((400, 150), Image.Resampling.LANCZOS)
    logo_horizontal.save('static/img/logo_horizontal.png', 'PNG')
    print("✔ 'logo_horizontal.png' regenerado con éxito.")

    # 2. Recortar el Icono de Seguridad (Apretón de manos de Confianza y Seguridad)
    # Ubicado en la esquina inferior izquierda de la sección de conceptos de marca
    box_seguridad = (int(ancho * 0.23), int(alto * 0.82), int(ancho * 0.38), int(alto * 0.93))
    icono_seguridad = img.crop(box_seguridad)
    icono_seguridad.thumbnail((120, 120), Image.Resampling.LANCZOS)
    icono_seguridad.save('static/img/icono_seguridad.png', 'PNG')
    print("✔ 'icono_seguridad.png' regenerado con éxito.")

    # 3. Recortar el Sello de Calidad (Escudo azul de Profesionalismo y Calidad)
    # Ubicado en la esquina inferior derecha de la sección de conceptos de marca
    box_calidad = (int(ancho * 0.77), int(alto * 0.82), int(ancho * 0.93), int(alto * 0.93))
    icono_calidad = img.crop(box_calidad)
    icono_calidad.thumbnail((120, 120), Image.Resampling.LANCZOS)
    icono_calidad.save('static/img/icono_calidad.png', 'PNG')
    print("✔ 'icono_calidad.png' regenerado con éxito.")
    
    print("\n¡Listo hermano! Archivos calibrados correctamente. Corre el script de nuevo.")

except FileNotFoundError:
    print("Error: No se encontró 'hoja_marca.jpg' en la raíz de tu proyecto.")