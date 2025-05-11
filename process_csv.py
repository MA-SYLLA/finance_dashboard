from flask import flash  # ← ← ← AJOUT OBLIGATOIRE !
import csv
from io import StringIO
from models import db, Transaction
from datetime import datetime
import re

def process_csv(file_stream, type_compte, user_id):
    try:
        def is_date_line(line):
            return bool(re.match(r"\d{2}/\d{2}/\d{4};", line))

        stream = StringIO(file_stream.read().decode('latin1'))
        lines = [line.strip() for line in stream.readlines() if line.strip()]

        start_idx = 0
        for i, line in enumerate(lines):
            if 'Date;Libellé;Débit euros;Crédit euros;' in line:
                start_idx = i + 1
                break

        data_lines = lines[start_idx:]
        transactions = []
        current = ""
        for line in data_lines:
            if is_date_line(line):
                if current:
                    transactions.append(current)
                current = line
            else:
                current += " " + line.strip()
        if current:
            transactions.append(current)

        rows = []
        for t in transactions:
            parts = t.split(";")
            if len(parts) >= 4:
                try:
                    date = datetime.strptime(parts[0], "%d/%m/%Y").date()
                    libelle = parts[1].strip()
                    debit = float(parts[2].replace(",", ".").replace("\xa0", "")) if parts[2] else 0
                    credit = float(parts[3].replace(",", ".").replace("\xa0", "")) if parts[3] else 0
                    montant = credit - debit
                    rows.append({"date": date, "libelle": libelle, "montant": montant})
                except Exception as e:
                    print(f"Erreur parsing ligne: {t} -> {e}")

        existants = {(t.date, t.libelle, t.montant) for t in Transaction.query.filter_by(user_id=user_id).all()}

        doublons = 0
        inserts = 0
        for row in rows:
            if (row['date'], row['libelle'], row['montant']) not in existants:
                transaction = Transaction(
                    date=row['date'],
                    libelle=row['libelle'],
                    montant=row['montant'],
                    type_compte=type_compte,
                    categorie=None,
                    user_id=user_id
                )
                db.session.add(transaction)
                inserts += 1
            else:
                doublons += 1

        db.session.commit()
        flash(f"{inserts} transactions importées avec succès.", 'success')
        if doublons > 0:
            flash(f"{doublons} doublons détectés et ignorés.", 'warning')

    except Exception as e:
        flash(f"Erreur lors de l'import : {e}", 'danger')
