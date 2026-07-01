import sqlite3
import os

ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_db = os.path.join(ruta_actual, 'inworker.db')

conexion = sqlite3.connect(ruta_db)
cursor = conexion.cursor()

# Creamos la tabla de usuarios con el campo 'rol'
cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        correo TEXT UNIQUE NOT NULL,
        contrasena TEXT NOT NULL,
        rol TEXT NOT NULL,
        fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

# Insertamos un usuario administrador de prueba
try:
    cursor.execute('''
        INSERT INTO usuarios (nombre, correo, contrasena, rol)
        VALUES (?, ?, ?, ?)
    ''', ('Andres Admin', 'andres@inworker.com', '123456', 'Administrador'))
    print("¡Usuario de prueba creado con éxito!")
except sqlite3.IntegrityError:
    print("El usuario de prueba ya existía.")

conexion.commit()
conexion.close()

print("¡Tabla 'usuarios' creada con éxito en la base de datos!")