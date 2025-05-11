# utils.py

from datetime import datetime
from models import Transaction

def get_solde_info(user, date_paie=None):
    """Calcule les informations de solde pour un utilisateur."""
    transactions = Transaction.query.filter_by(user_id=user.id).all()
    solde_actuel = sum(t.montant for t in transactions)
    disponible_avant_decouvert = max(0, solde_actuel)
    disponible_avec_decouvert = solde_actuel + (user.decouvert or 0)

    today = datetime.today().date()

    if not date_paie:
        date_paie = user.jour_paie or 1

    try:
        paie_jour = int(date_paie)
        prochaine_paie = today.replace(day=paie_jour)
    except ValueError:
        prochaine_paie = today.replace(day=28)

    if today >= prochaine_paie:
        if prochaine_paie.month == 12:
            prochaine_paie = prochaine_paie.replace(year=prochaine_paie.year + 1, month=1)
        else:
            prochaine_paie = prochaine_paie.replace(month=prochaine_paie.month + 1)

    jours_restant = (prochaine_paie - today).days

    return {
        'solde_actuel': round(solde_actuel, 2),
        'disponible_avant_decouvert': int(round(disponible_avant_decouvert)),
        'disponible_avec_decouvert': int(round(disponible_avec_decouvert)),
        'prochaine_paie': prochaine_paie.strftime('%d/%m/%Y') if prochaine_paie else 'N/A',
        'jours_restant': jours_restant if jours_restant is not None else 'N/A'
    }
