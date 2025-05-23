# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Créer une instance de SQLAlchemy
db = SQLAlchemy()

# Modèle Utilisateur
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    decouvert = db.Column(db.Float, default=0)
    jour_paie = db.Column(db.Integer, default=1)

    transactions = db.relationship('Transaction', backref='user', lazy=True)

# Modèle Transaction
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    libelle = db.Column(db.String(255), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    type_compte = db.Column(db.String(100), nullable=False)
    categorie = db.Column(db.String(100), nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Transaction {self.libelle} - {self.montant} €>'
    
    
class SoldeHistorique(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    solde = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<SoldeHistorique {self.date} - {self.solde} €>'

    
class DatePaieConfirmee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mois = db.Column(db.String(7), nullable=False)  # exemple : '2025-04'
    date_paie = db.Column(db.Date, nullable=False)

