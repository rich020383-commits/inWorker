import sqlite3
import os

# Buscamos la ruta de la carpeta actual
ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_db = os.path.join(ruta_actual, 'inworker.db')

# Conectamos con la base de datos (se crea el archivo si no existe)
conexion = sqlite3.connect(ruta_db)
cursor = conexion.cursor()

# Creamos la tabla de empleados con la estructura sólida
cursor.execute('''
    CREATE TABLE IF NOT EXISTS empleados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        puesto TEXT NOT NULL,
        estado TEXT NOT NULL,
        rendimiento INTEGER NOT NULL,
        tareas_activas INTEGER DEFAULT 0,
        fecha_ingreso DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

# Insertamos unos empleados de prueba para que la tabla no nazca vacía
empleados_iniciales = [
    ('Carlos Mendoza', 'Desarrollador Backend', 'Activo', 94, 2),
    ('Laura Rodríguez', 'Diseñadora UI/UX', 'Activo', 88, 1),
    ('Mateo Pérez', 'Soporte Técnico', 'En Pause', 75, 2)
]

cursor.executemany('''
    INSERT INTO empleados (nombre, puesto, estado, rendimiento, tareas_activas)
    VALUES (?, ?, ?, ?, ?)
''', empleados_iniciales)

# Guardamos los cambios y cerramos
conexion.commit()
conexion.close()

print("¡Base de datos 'inworker.db' creada con éxito con datos de prueba!")