from app import app, db
from sqlalchemy import text

print("🚀 Conectando a Supabase para actualizar la estructura...")

with app.app_context():
    try:
        # 1. Inyectamos la columna para el código único del embajador
        print(" Adding: codigo_embajador...")
        db.session.execute(text("""
            ALTER TABLE usuarios 
            ADD COLUMN IF NOT EXISTS codigo_embajador VARCHAR(50) UNIQUE;
        """))
        
        # 2. Inyectamos la columna para rastrear quién invitó a este usuario
        print(" Adding: referido_por...")
        db.session.execute(text("""
            ALTER TABLE usuarios 
            ADD COLUMN IF NOT EXISTS referido_por VARCHAR(50);
        """))
        
        # Guardamos los cambios de forma segura en PostgreSQL
        db.session.commit()
        print("\n✅ ¡Columnas inyectadas con éxito en Supabase!")
        print("Tu Admin sigue intacto y la base de datos ya está lista para los referidos.")
        
    except Exception as e:
        db.session.rollback()
        print(f"\n❌ Error al aplicar la cirugía en la base de datos: {e}")