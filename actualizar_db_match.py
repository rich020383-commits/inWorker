import sqlite3
import os

ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_db = os.path.join(ruta_actual, 'inworker.db')

conexion = sqlite3.connect(ruta_db)
cursor = conexion.cursor()

try:
    # Agregamos la columna para saber qué trabajador aceptó la tarea
    cursor.execute("ALTER TABLE tareas ADD COLUMN trabajador_asignado TEXT")
    print("¡Base de datos actualizada con éxito para el sistema de Match!")
except sqlite3.OperationalError:
    print("La columna 'trabajador_asignado' ya existía en la tabla.")

conexion.commit()
conexion.close()