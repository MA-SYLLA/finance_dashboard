# utils.py

from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from models import Transaction
from models import DatePaieConfirmee
import pandas as pd

def get_solde_info(user, date_paie=None):
    today = date.today()

    if not date_paie:
        date_paie = 1  # Valeur statique (fallback simple)

    # Récupère les dates de paie confirmées de l’utilisateur
    confirmées = DatePaieConfirmee.query.filter_by(user_id=user.id).order_by(DatePaieConfirmee.date_paie).all()
    start_date, end_date = None, None

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

    # Requête filtrée
    transactions = Transaction.query.filter(
        Transaction.user_id == user.id,
        Transaction.type_compte == "Compte Courant",
        Transaction.date >= start_date,
        Transaction.date <= end_date
    ).all()

    total_revenus = sum(t.montant for t in transactions if t.montant > 0)
    total_depenses = abs(sum(t.montant for t in transactions if t.montant < 0))
    solde = total_revenus - total_depenses
    
    jours_restant = (end_date - today).days
    prochaine_paie = end_date + timedelta(days=1)
    decouvert = user.decouvert or 0
    disponible_avec_decouvert = solde + decouvert

    return {
        "solde_actuel": round(solde, 2),
        "disponible_avec_decouvert": round(disponible_avec_decouvert, 2),
        "jours_restant": jours_restant,
        "prochaine_paie": prochaine_paie.strftime("%d/%m/%Y")
    }
    
def detecter_dates_paie(transactions_df, montant_min=1000):
    """
    Détecte la date de paie réelle pour chaque mois à partir des transactions créditeuses.

    transactions_df : DataFrame contenant au moins les colonnes :
        - 'Date opération' (datetime)
        - 'Montant' (float, positif = crédit)
        - 'Libellé' (str)

    Retourne un dictionnaire { 'YYYY-MM': date_paie_detectée }
    """

    # On garde les crédits > seuil et libellés typiques
    df = transactions_df.copy()
    df = df[df['Montant'] > montant_min]

    # Mots-clés indicatifs d'un virement de paie
    keywords = ['salaire', 'paie', 'versement', 'rémunération', 'virement', 'sylla', 'orange']
    df = df[df['Libellé'].str.lower().str.contains('|'.join(keywords), na=False)]

    # Extraire l'année-mois de chaque transaction
    df['mois'] = df['Date opération'].dt.to_period('M')

    # Garder la dernière paie par mois
    paies = df.sort_values('Date opération').groupby('mois').last()

    # Créer un dict { '2025-04': date(...) }
    resultat = {
        str(row['Date opération'].date()): row['Date opération'].date()
        for _, row in paies.iterrows()
    }

    return resultat


def get_periode_budgetaire(jour_paie: int, ref_date: date = None):
    """
    Calcule le début et la fin du cycle budgétaire à partir d’un jour de paie.
    Le cycle va de jour_paie à (jour_paie - 1) du mois suivant.
    Exemple : jour_paie = 20 => du 20 avril au 19 mai.
    """
    if not ref_date:
        ref_date = date.today()

    # Calcul du début de période
    try:
        start = ref_date.replace(day=jour_paie)
        if ref_date < start:
            start = (start - relativedelta(months=1)).replace(day=jour_paie)
    except ValueError:
        start = ref_date.replace(day=1)

    end = start + relativedelta(months=1) - timedelta(days=1)

    return start, end

from models import DatePaieConfirmee

def detecter_dates_a_valider(user_id):
    """
    Retourne les dates de paie détectées pour un utilisateur qui ne sont pas encore confirmées.
    Format : [{mois: '2025-04', date: date(...), message: "..."}]
    """
    # Transactions du compte courant uniquement
    transactions = Transaction.query.filter_by(user_id=user_id, type_compte="Compte Courant").all()
    data = [{
        "Date opération": t.date,
        "Montant": t.montant,
        "Libellé": t.libelle
    } for t in transactions]

    df = pd.DataFrame(data)
    if df.empty:
        return []

    df["Date opération"] = pd.to_datetime(df["Date opération"])

    # Détection brève
    paies_detectees = detecter_dates_paie(df)

    # Mois déjà confirmés
    mois_confirmes = {p.mois for p in DatePaieConfirmee.query.filter_by(user_id=user_id).all()}

    # Tri des mois pour calculs de fin de période
    mois_ordonne = sorted(paies_detectees.items(), key=lambda x: x[0])

    suggestions = []
    for i, (date_str, date_paie) in enumerate(mois_ordonne):
        mois = date_paie.strftime('%Y-%m')
        if mois in mois_confirmes:
            continue

        if i + 1 < len(mois_ordonne):
            date_fin = mois_ordonne[i + 1][1] - timedelta(days=1)
        else:
            date_fin = date_paie + timedelta(days=30)

        message = f"Période de paie du {date_paie.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}."
        suggestions.append({
            "mois": mois,
            "date": date_paie,
            "fin": date_fin,
            "message": message
        })

    return suggestions
