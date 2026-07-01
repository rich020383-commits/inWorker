import sqlite3

bases = ["inworker.db", "inworker_prod.db"]

for db in bases:
    try:
        conexion = sqlite3.connect(db)
        cursor = conexion.cursor()
        # Metemos la columna faltante
        cursor.execute("ALTER TABLE usuarios ADD COLUMN descripcion TEXT DEFAULT '';")
        conexion.commit()
        conexion.close()
        print(f"✅ Columna agregada con éxito en: {db}")
    except sqlite3.OperationalError:
        print(f"⚠️ En {db} ya existía la columna o el archivo no se usa.")