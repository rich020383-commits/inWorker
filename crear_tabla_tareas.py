import sqlite3
import os

ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_db = os.path.join(ruta_actual, 'inworker.db')

conexion = sqlite3.connect(ruta_db)
cursor = conexion.cursor()

# 🔥 Borramos la tabla vieja si existe para asegurar que se cree limpia
cursor.execute('DROP TABLE IF EXISTS tareas')

# Creamos la tabla con las 11 columnas exactas que pide tu app.py
cursor.execute('''
    CREATE TABLE tareas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        descripcion TEXT NOT NULL,
        pago TEXT NOT NULL,
        categoria TEXT NOT NULL,
        estado TEXT DEFAULT 'Disponible',
        costo_creditos REAL,
        cliente_correo TEXT,
        latitud REAL,
        longitud REAL,
        zona TEXT,
        tecnico_correo TEXT, -- La columna que nos dio el dolor de cabeza
        fecha_publicacion DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

conexion.commit()
conexion.close()

print("¡Tabla 'tareas' sincronizada al 100% con app.py y creada con éxito!")