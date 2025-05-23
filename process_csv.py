from flask import flash
import csv
from io import StringIO
from models import db, Transaction, SoldeHistorique
from datetime import datetime
import re


def process_csv(file_stream, type_compte, user_id):
    try:
        def is_date_line(line):
            return bool(re.match(r"\d{2}/\d{2}/\d{4};", line))

        # Lecture brute des lignes
        stream = StringIO(file_stream.read().decode('latin1'))
        lines = [line.strip() for line in stream.readlines() if line.strip()]

        # 🔍 Étape 1 : détecter et isoler le solde final
        solde_final = None
        date_solde = None

        for line in lines:
            if "Solde au" in line:
                ligne_solde = line.strip()
                print(f">>> 🔍 Ligne détectée : {ligne_solde}")

                match_date = re.search(r"Solde au (\d{2}/\d{2}/\d{4})", ligne_solde)
                if match_date:
                    date_str = match_date.group(1)
                    date_solde = datetime.strptime(date_str, "%d/%m/%Y").date()

                    montant_part = ligne_solde.replace(f"Solde au {date_str}", "").strip()
                    montant_str = (
                        montant_part.replace("€", "")
                                    .replace("\xa0", "")
                                    .replace(" ", "")
                                    .replace(",", ".")
                    )
                    montant_str = re.sub(r"[^\d\.-]", "", montant_str)
                    try:
                        solde_final = float(montant_str)
                        print(f">>> ✅ Solde final : {solde_final} € à la date {date_solde}")
                        break
                    except Exception as e:
                        print(f">>> ⚠️ Erreur conversion : '{montant_str}' → {e}")

        # 🔍 Étape 2 : parsing des transactions
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

        # 🔄 Import en base
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

        # ✅ Injection de l'ajustement si delta détecté
        if solde_final is not None and date_solde is not None:
            somme_transactions = sum(row['montant'] for row in rows)
            delta = round(solde_final - somme_transactions, 2)

            if abs(delta) >= 0.01:
                ajustement = Transaction(
                    date=date_solde,
                    libelle="Ajustement auto pour solde réel",
                    montant=delta,
                    type_compte=type_compte,
                    categorie="Ajustement",
                    user_id=user_id
                )
                db.session.add(ajustement)
                db.session.commit()
                flash(f"⚖️ Ajustement automatique ajouté : {delta:+.2f} € le {date_solde.strftime('%d/%m/%Y')}", "info")

            # 💾 Enregistrement du solde
            deja = SoldeHistorique.query.filter_by(user_id=user_id, date=date_solde).first()
            if not deja:
                sh = SoldeHistorique(user_id=user_id, date=date_solde, solde=solde_final)
                db.session.add(sh)
                db.session.commit()
                flash(f"💾 Solde enregistré pour le {date_solde.strftime('%d/%m/%Y')} : {solde_final:.2f} €", "info")

    except Exception as e:
        flash(f"Erreur lors de l'import : {e}", 'danger')
