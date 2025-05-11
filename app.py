from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

from models import db, User, Transaction
from process_csv import process_csv
from utils import get_solde_info


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
        flash('Veuillez vous connecter.', 'warning')
        return redirect(url_for('login'))

    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()
    transactions = Transaction.query.filter_by(user_id=user.id).all()

    total_transactions = len(transactions)
    total_revenus = sum(t.montant for t in transactions if t.montant > 0)
    total_depenses = sum(t.montant for t in transactions if t.montant < 0)
    solde = total_revenus + total_depenses
    decouvert = user.decouvert if user else 0
    solde_disponible = solde + decouvert

    solde_info = get_solde_info(user)

    return render_template('home.html',
                           total_transactions=total_transactions,
                           total_revenus=round(total_revenus, 2),
                           total_depenses=round(total_depenses, 2),
                           solde=round(solde, 2),
                           decouvert=round(decouvert, 2),
                           solde_disponible=round(solde_disponible, 2),
                           solde_info=solde_info,
                           user=user,
                           active_page='home')

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

    flash('Fichier CSV importé avec succès.', 'success')
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

@app.route('/set_jour_paie', methods=['POST'])
def set_jour_paie():
    if 'user' not in session:
        flash("Veuillez vous connecter", "warning")
        return redirect(url_for('login'))

    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()

    jour_paie = request.form.get('jour_paie', '').strip()
    if jour_paie.isdigit():
        jour = int(jour_paie)
        if 1 <= jour <= 31:
            user.jour_paie = jour
            db.session.commit()
            flash("Jour de paie mis à jour.", "success")
        else:
            flash("Le jour de paie doit être compris entre 1 et 31.", "danger")
    else:
        flash("Valeur invalide pour le jour de paie.", "danger")

    return redirect(url_for('home'))

@app.route('/graph_par_compte')
def graph_par_compte():
    if 'user' not in session:
        flash('Veuillez vous connecter.', 'warning')
        return redirect(url_for('login'))

    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()
    solde_info = get_solde_info(user)

    # Récupérer les données pour le graphique par type de compte
    transactions = Transaction.query.filter_by(user_id=user.id).all()
    comptes = set(t.type_compte for t in transactions)
    labels = list(comptes)  # Les types de comptes seront nos labels
    values = [sum(t.montant for t in transactions if t.type_compte == compte) for compte in comptes]

    # Préparer les données pour le template
    data = list(zip(labels, values))

    return render_template('graph.html', labels=labels, values=values, data=data, solde_info=solde_info, active_page='graph_par_compte')

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