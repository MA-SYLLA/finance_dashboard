# init_db.py

from app import db, app

# On utilise le contexte de l'application pour accéder à la base
with app.app_context():
    db.create_all()
    print("✅ Base de données initialisée avec succès.")
