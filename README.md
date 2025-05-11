# 💸 Finance Dashboard

Application Flask de suivi financier personnel.  
Permet d'importer des transactions, visualiser ses revenus/dépenses et suivre l’évolution de son solde avec filtres dynamiques.

---

## ✅ Fonctionnalités principales

- 📥 **Import de fichiers CSV** par type de compte
- 📊 **Graphiques** par :
  - Solde global
  - Solde par cycle de paie
  - Catégories de revenus et dépenses
- 📆 **Filtres de date** et échelle temporelle (jour, mois, année)
- 📌 **Encadré flottant** avec :
  - Solde actuel
  - Prochaine paie
  - Jours restants
  - Découvert autorisé
- 🛠️ Interface simple, responsive avec Bootstrap

## 

🚀 Installation du projet

1. Cloner le dépôt
git clone https://github.com/MA-SYLLA/finance_dashboard.git
cd finance_dashboard

2. Créer et activer l’environnement virtuel
python -m venv venv
venv\Scripts\activate  # Windows
# ou
source venv/bin/activate  # macOS/Linux

3. Installer les dépendances
pip install -r requirements.txt

⚙️ Configuration
Créer un fichier .env à la racine du projet avec :
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=change_this_key
Créer également le dossier instance/ manuellement si nécessaire pour héberger finance.db.

💻 Lancement de l'application
flask run
L'application sera accessible à l'adresse :
http://localhost:5000

📁 Structure du projet
Dossier/Fichier	Rôle
app.py	Fichier principal contenant les routes Flask
models.py	Modèles SQLAlchemy (User, Transaction)
utils.py	Fonctions utilitaires (ex: get_solde_info)
process_csv.py	Fonction d'importation CSV
templates/	Fichiers HTML Jinja2
static/	CSS et JS
instance/	Contient la base de données locale

📌 À venir (prochaines évolutions possibles)
Export PDF ou PNG des graphiques

Export Excel des transactions

Graphiques par compte bancaire

Affichage multi-utilisateur

Déploiement en ligne (Render, Heroku, etc.)

👤 Auteur
Mohamed Aly

github.com/MA-SYLLA

📄 Licence
Projet open-source libre d’utilisation et de modification.