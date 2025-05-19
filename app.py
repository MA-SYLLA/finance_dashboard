from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from datetime import date
import os
import pandas as pd

from models import db, User, Transaction, DatePaieConfirmee
from process_csv import process_csv
from utils import get_solde_info, get_periode_budgetaire, detecter_dates_paie

app = Flask(__name__)
app.secret_key = 'supersecretkey'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'finance.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

@app.context_processor
def inject_user():
    user = session.get('user')
    return {'user': user}

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/home')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))

    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()

    filter_type = request.args.get('filter_type')
    filter_value = request.args.get('filter_value')

    today = date.today()
    start_date = end_date = None

    if filter_type == 'day' and filter_value:
        try:
            selected_date = datetime.strptime(filter_value, "%Y-%m-%d").date()
            start_date = end_date = selected_date
        except:
            flash("Date invalide", "warning")
            return redirect(url_for('home'))

    elif filter_type == 'month' and filter_value:
        try:
            year, month = map(int, filter_value.split('-'))
            mois_cible = f"{year}-{month:02d}"
            confirmée = DatePaieConfirmee.query.filter_by(user_id=user.id, mois=mois_cible).first()

            if confirmée:
                start_date = confirmée.date_paie
                prochaine = DatePaieConfirmee.query.filter(
                    DatePaieConfirmee.user_id == user.id,
                    DatePaieConfirmee.date_paie > start_date
                ).order_by(DatePaieConfirmee.date_paie.asc()).first()

                if prochaine:
                    end_date = prochaine.date_paie - timedelta(days=1)
                else:
                    end_date = start_date + timedelta(days=30)
            else:
                start_date = date(year, month, 1)
                end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        except:
            flash("Mois invalide", "warning")
            return redirect(url_for('home'))

    elif filter_type == 'year' and filter_value:
        try:
            year = int(filter_value)
            confirmées = DatePaieConfirmee.query.filter(
                DatePaieConfirmee.user_id == user.id,
                DatePaieConfirmee.date_paie >= date(year, 1, 1),
                DatePaieConfirmee.date_paie <= date(year, 12, 31)
            ).order_by(DatePaieConfirmee.date_paie.asc()).all()

            if confirmées:
                start_date = confirmées[0].date_paie
                dernière = confirmées[-1].date_paie
                end_date = dernière + timedelta(days=30)
            else:
                start_date = date(year, 1, 1)
                end_date = date(year, 12, 31)

        except:
            flash("Année invalide", "warning")
            return redirect(url_for('home'))

    else:
        confirmées = DatePaieConfirmee.query.filter_by(user_id=user.id).order_by(DatePaieConfirmee.date_paie).all()
        for i, d in enumerate(confirmées):
            if d.date_paie <= today:
                if i + 1 < len(confirmées):
                    next_date = confirmées[i + 1].date_paie
                    if today < next_date:
                        start_date = d.date_paie
                        end_date = next_date - timedelta(days=1)
                        break
                else:
                    start_date = d.date_paie
                    end_date = d.date_paie + timedelta(days=30)
                    break

        if not start_date:
            start_date = today.replace(day=1)
            end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    transactions = Transaction.query.filter(
        Transaction.user_id == user.id,
        Transaction.type_compte == "Compte Courant",
        Transaction.date >= start_date,
        Transaction.date <= end_date
    ).all()

    total_transactions = len(transactions)
    total_revenus = sum(t.montant for t in transactions if t.montant > 0)
    total_depenses = abs(sum(t.montant for t in transactions if t.montant < 0))
    solde = total_revenus - total_depenses
    decouvert = user.decouvert or 0
    solde_disponible = solde + decouvert

    return render_template(
        'home.html',
        total_transactions=total_transactions,
        total_revenus=round(total_revenus, 2),
        total_depenses=round(total_depenses, 2),
        solde=round(solde, 2),
        decouvert=round(decouvert, 2),
        solde_disponible=round(solde_disponible, 2),
        user=user,
        active_page='home',
        start_date=start_date,
        end_date=end_date
    )

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nom = request.form.get('nom')
        prenom = request.form.get('prenom')
        email = request.form.get('email')
        password = request.form.get('password')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Un compte avec cet email existe déjà.', 'danger')
            return redirect(url_for('register'))

        password_hash = generate_password_hash(password)
        new_user = User(nom=nom, prenom=prenom, email=email, password_hash=password_hash)
        db.session.add(new_user)
        db.session.commit()

        session['user'] = {'prenom': prenom, 'email': email}
        flash(f'Bienvenue {prenom} ! Votre compte a été créé.', 'success')
        return redirect(url_for('home'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session['user'] = {'prenom': user.prenom, 'email': user.email}
            flash('Connexion réussie.', 'success')
            return redirect(url_for('home'))

        flash('Email ou mot de passe incorrect.', 'danger')
        return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Déconnexion réussie.', 'success')
    return redirect(url_for('login'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        new_password = request.form.get('new_password')

        user = User.query.filter_by(email=email).first()
        if user:
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('Mot de passe mis à jour avec succès.', 'success')
            return redirect(url_for('login'))

        flash('Adresse email non trouvée.', 'danger')
        return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html')

@app.route('/transactions')
def transactions():
    if 'user' not in session:
        flash('Veuillez vous connecter.', 'warning')
        return redirect(url_for('login'))

    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()
    transactions = Transaction.query.filter_by(user_id=user.id).all()

    solde_info = get_solde_info(user)

    return render_template('transactions.html', transactions=transactions, solde_info=solde_info, active_page='transactions')

@app.route('/add_transaction', methods=['GET', 'POST'])
def add_transaction():
    if 'user' not in session:
        flash('Veuillez vous connecter.', 'warning')
        return redirect(url_for('login'))

    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()
    solde_info = get_solde_info(user)

    if request.method == 'POST':
        date_str = request.form.get('date')
        libelle = request.form.get('libelle')
        montant = float(request.form.get('montant'))
        type_compte = request.form.get('type_compte')
        categorie = request.form.get('categorie') or None

        date = datetime.strptime(date_str, "%Y-%m-%d").date()

        transaction = Transaction(
            date=date,
            libelle=libelle,
            montant=montant,
            type_compte=type_compte,
            categorie=categorie,
            user_id=user.id
        )
        db.session.add(transaction)
        db.session.commit()

        flash('Transaction ajoutée avec succès.', 'success')
        return redirect(url_for('transactions'))

    return render_template('add_transaction.html', solde_info=solde_info, active_page='add_transaction')

@app.route('/delete_transaction/<int:id>', methods=['POST'])
def delete_transaction(id):
    if 'user' not in session:
        flash('Veuillez vous connecter.', 'warning')
        return redirect(url_for('login'))

    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()
    solde_info = get_solde_info(user)

    transaction = Transaction.query.get(id)
    if transaction:
        db.session.delete(transaction)
        db.session.commit()
        flash('Transaction supprimée.', 'success')
    else:
        flash('Transaction non trouvée.', 'danger')

    return redirect(url_for('transactions'))

@app.route('/update_category/<int:id>', methods=['POST'])
def update_category(id):
    if 'user' not in session:
        flash('Veuillez vous connecter.', 'warning')
        return redirect(url_for('login'))

    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()
    solde_info = get_solde_info(user)

    new_category = request.form.get('categorie')

    transaction = Transaction.query.get(id)
    if transaction:
        transaction.categorie = new_category
        db.session.commit()
        flash('Catégorie mise à jour.', 'success')

    return redirect(url_for('transactions'))

@app.route('/transactions/clear_category/<int:id>')
def clear_category(id):
    transaction = Transaction.query.get_or_404(id)
    transaction.categorie = None
    db.session.commit()
    flash("Catégorie supprimée", "success")
    return redirect(url_for('transactions'))


@app.route('/import_csv', methods=['POST'])
def import_csv():
    if 'user' not in session:
        flash('Veuillez vous connecter.', 'warning')
        return redirect(url_for('login'))

    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()
    solde_info = get_solde_info(user)

    file = request.files.get('file')
    type_compte = request.form.get('type_compte')

    if not file or not type_compte:
        flash('Merci de choisir un fichier CSV et un type de compte.', 'danger')
        return redirect(url_for('home'))

    process_csv(file.stream, type_compte, user.id)
    
    from utils import detecter_dates_a_valider

    dates_suggerees = detecter_dates_a_valider(user.id)

    if dates_suggerees:
        session['dates_suggerees'] = [{
            "mois": d["mois"],
            "date": d["date"].strftime('%Y-%m-%d'),
            "message": d["message"]
        } for d in dates_suggerees]

    flash('Fichier CSV importé avec succès.', 'success')
    return redirect(url_for('home'))

@app.route('/valider_paie', methods=['POST'])
def valider_paie():
    if 'user' not in session:
        flash("Veuillez vous connecter.", "warning")
        return redirect(url_for('login'))

    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()

    mois = request.form.get('mois')
    date_str = request.form.get('date_paie')

    if not mois or not date_str:
        flash("Données manquantes.", "danger")
        return redirect(url_for('home'))

    try:
        date_paie = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Format de date invalide.", "danger")
        return redirect(url_for('home'))

    # Vérifie si la date est déjà confirmée
    existe = DatePaieConfirmee.query.filter_by(user_id=user.id, mois=mois).first()
    if not existe:
        nouvelle = DatePaieConfirmee(user_id=user.id, mois=mois, date_paie=date_paie)
        db.session.add(nouvelle)
        db.session.commit()

    # Nettoie la date validée de la session
    if 'dates_suggerees' in session:
        restantes = [d for d in session['dates_suggerees'] if d['mois'] != mois]
        if restantes:
            session['dates_suggerees'] = restantes
        else:
            session.pop('dates_suggerees', None)

    return redirect(url_for('home'))


@app.route('/set_decouvert', methods=['POST'])  
def set_decouvert():
    if 'user' not in session:
        flash('Veuillez vous connecter.', 'warning')
        return redirect(url_for('login'))

    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()

    try:
        montant_str = request.form.get('montant_decouvert', '').strip()
        montant = int(float(montant_str))  # ← transforme en entier
        user.decouvert = montant
        db.session.commit()
        flash('Découvert autorisé mis à jour avec succès.', 'success')
    except (ValueError, TypeError):
        flash("Valeur invalide pour le découvert.", "danger")

    return redirect(url_for('home'))

@app.route('/graph_par_compte')
def graph_par_compte():
    if 'user' not in session:
        flash('Veuillez vous connecter.', 'warning')
        return redirect(url_for('login'))

    # Récupération de l'utilisateur
    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()
    solde_info = get_solde_info(user)

    # Lecture des filtres date
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    # Base de la requête
    query = Transaction.query.filter_by(user_id=user.id)

    # Application du filtre date début
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            query = query.filter(Transaction.date >= start_date)
        except ValueError:
            flash("Date de début invalide", "warning")

    # Application du filtre date fin
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            query = query.filter(Transaction.date <= end_date)
        except ValueError:
            flash("Date de fin invalide", "warning")

    # Exécution de la requête
    transactions = query.all()

    # 🔍 Debug : transactions filtrées
    print(">>> Filtres actifs :")
    print("Start:", start_date_str, "| End:", end_date_str)
    print(">>> Transactions filtrées :")
    for t in transactions:
        print(f"- {t.date} | {t.type_compte} | {t.montant}")

    # Agrégation des montants par compte (sans retraits pour le livrets)
    comptes = {}
    for t in transactions:
        compte = t.type_compte
        montant = t.montant
    
        comptes[compte] = comptes.get(compte, 0) + montant
        
    # 👉 Appliquer la règle spécifique au livret : pas de négatif
    if 'Livret' in comptes and comptes['Livret'] < 0:
         comptes['Livret'] = 0

    # 🔍 Debug : totaux par compte
    print(">>> Totaux par compte :")
    for compte, total in comptes.items():
        print(f"{compte}: {total:.2f}")

    # Données pour le graphique et le tableau
    labels = list(comptes.keys())
    values = [round(v, 2) for v in comptes.values()]
    data = list(comptes.items())

    return render_template(
        'graph.html',
        labels=labels,
        values=values,
        data=data,
        solde_info=solde_info,
        start_date=start_date_str,
        end_date=end_date_str,
        active_page='graph_par_compte'
    )

@app.route('/graph_categorie_depenses')
def graph_categorie_depenses():
    if 'user' not in session:
        flash('Veuillez vous connecter.', 'warning')
        return redirect(url_for('login'))

    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()
    solde_info = get_solde_info(user)

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    query = Transaction.query.filter_by(user_id=user.id).filter(Transaction.montant < 0)

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            query = query.filter(Transaction.date >= start_date)
        except ValueError:
            flash("Date de début invalide", "warning")

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            query = query.filter(Transaction.date <= end_date)
        except ValueError:
            flash("Date de fin invalide", "warning")

    transactions = query.all()
    categories = set(t.categorie for t in transactions if t.categorie)
    labels = list(categories)
    values = [sum(t.montant for t in transactions if t.categorie == cat) for cat in categories]
    data = list(zip(labels, values))

    return render_template(
        'graph_categorie_depenses.html',
        labels=labels,
        values=values,
        data=data,
        solde_info=solde_info,
        active_page='graph_par_categorie_depenses',
        start_date=start_date_str,
        end_date=end_date_str,
        zip=zip
    )

@app.route('/graph_categorie_revenus')
def graph_categorie_revenus():
    if 'user' not in session:
        flash('Veuillez vous connecter.', 'warning')
        return redirect(url_for('login'))

    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()
    solde_info = get_solde_info(user)

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    query = Transaction.query.filter_by(user_id=user.id).filter(Transaction.montant > 0)

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            query = query.filter(Transaction.date >= start_date)
        except ValueError:
            flash("Date de début invalide", "warning")

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            query = query.filter(Transaction.date <= end_date)
        except ValueError:
            flash("Date de fin invalide", "warning")

    transactions = query.all()
    categories = set(t.categorie for t in transactions if t.categorie)
    labels = list(categories)
    values = [sum(t.montant for t in transactions if t.categorie == cat) for cat in categories]
    data = list(zip(labels, values))

    return render_template(
        'graph_categorie_revenus.html',
        labels=labels,
        values=values,
        data=data,
        solde_info=solde_info,
        active_page='graph_par_categorie_revenus',
        start_date=start_date_str,
        end_date=end_date_str,
        zip=zip
    )

@app.route('/graph_solde')
def graph_solde():
    if 'user' not in session:
        flash('Veuillez vous connecter.', 'warning')
        return redirect(url_for('login'))

    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    time_scale = request.args.get('time_scale', 'month')
    cumul = request.args.get('cumul') == 'true'

    solde_info = get_solde_info(user)

    query = Transaction.query.filter_by(user_id=user.id)
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            query = query.filter(Transaction.date >= start_date)
        except ValueError:
            flash("Date de début invalide", "warning")
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            query = query.filter(Transaction.date <= end_date)
        except ValueError:
            flash("Date de fin invalide", "warning")

    transactions = query.order_by(Transaction.date).all()

    periodes = {}
    for t in transactions:
        if time_scale == 'day':
            key = t.date.strftime('%Y-%m-%d')
        elif time_scale == 'year':
            key = t.date.strftime('%Y')
        else:
            key = t.date.strftime('%Y-%m')
        periodes[key] = periodes.get(key, 0) + t.montant

    labels = sorted(periodes.keys())
    values = []
    cumulatif = 0
    for k in labels:
        cumulatif += periodes[k]
        values.append(round(cumulatif if cumul else periodes[k], 2))

    return render_template(
        'graph_solde.html',
        labels=labels,
        values=values,
        time_scale=time_scale,
        cumul=cumul,
        solde_info=solde_info,
        active_page='graph_solde',
        page_title='Évolution du Solde Calendrier'
    )

@app.route('/graph_solde_paie')
def graph_solde_paie():
    if 'user' not in session:
        flash('Veuillez vous connecter.', 'warning')
        return redirect(url_for('login'))

    # On ne récupère plus date_paie depuis l'URL
    date_paie_str = None
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    time_scale = request.args.get('time_scale', 'month')
    cumul = request.args.get('cumul') == 'true'

    # Récupération utilisateur
    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()

    # Infos solde dynamiques (utilise user.jour_paie automatiquement)
    solde_info = get_solde_info(user)

    # Requête transactions avec filtres
    query = Transaction.query.filter_by(user_id=user.id)
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            query = query.filter(Transaction.date >= start_date)
        except ValueError:
            flash("Date de début invalide", "warning")
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            query = query.filter(Transaction.date <= end_date)
        except ValueError:
            flash("Date de fin invalide", "warning")

    transactions = query.order_by(Transaction.date).all()

    # Agrégation par période selon time_scale
    periodes = {}
    for t in transactions:
        if time_scale == "day":
            key = t.date.strftime('%Y-%m-%d')
        elif time_scale == "year":
            key = t.date.strftime('%Y')
        else:
            key = t.date.strftime('%Y-%m')
        periodes[key] = periodes.get(key, 0) + t.montant

    labels = sorted(periodes.keys())
    values = []
    cumulatif = 0
    for k in labels:
        cumulatif += periodes[k]
        values.append(round(cumulatif if cumul else periodes[k], 2))

    return render_template(
        'graph_solde_paie.html',
        labels=labels,
        values=values,
        solde_info=solde_info,
        start_date=start_date_str,
        end_date=end_date_str,
        time_scale=time_scale,
        cumul=cumul,
        active_page='graph_solde_paie',
        page_title='Évolution du Solde Cycle de Paie'
    )

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)