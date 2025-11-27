import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="AUDIT & REPAIR", page_icon="🔧")
st.title("🔧 Audit et Réparation de la Structure")

try:
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sh = client.open("suivi_combats")
except Exception as e:
    st.error(f"Erreur connexion : {e}")
    st.stop()

if st.button("LANCER LA RESTRUCTURATION DES COLONNES", type="primary"):
    with st.status("Réparation en cours...") as status:
        
        # 1. FEUILLE 1 (LIVE)
        st.write("Configuring 'Feuille 1' (Live)...")
        ws = sh.sheet1
        ws.clear()
        ws.append_row(["Combattant", "Aire", "Numero", "Casque", "Statut", "Palmares", "Details_Tour", "Medaille_Actuelle"])
        
        # 2. CALENDRIER
        st.write("Configuring 'Calendrier'...")
        try: ws = sh.worksheet("Calendrier")
        except: ws = sh.add_worksheet("Calendrier", 100, 2)
        # On garde les données si possible, sinon reset headers
        if not ws.get_all_records():
            ws.clear()
            ws.append_row(["Nom_Competition", "Date_Prevue"])
            
        # 3. ATHLETES (On garde les données mais on force l'ordre)
        st.write("Configuring 'Athletes'...")
        try: 
            ws = sh.worksheet("Athletes")
            data = ws.get_all_records()
            ws.clear()
            ws.append_row(["Nom", "Prenom", "Annee_Naissance", "Poids", "Sexe", "Titre_Honorifique"])
            # Réinjection des données si existantes
            if data:
                new_rows = []
                for d in data:
                    # Gestion de la séparation nom/prenom si ancienne version
                    nom = d.get('Nom', '')
                    prenom = d.get('Prenom', '')
                    if not prenom and " " in nom: # Tentative de réparation
                        parts = nom.split()
                        nom = " ".join(parts[:-1])
                        prenom = parts[-1]
                    
                    new_rows.append([
                        str(nom).upper(), 
                        str(prenom).capitalize(), 
                        d.get('Annee_Naissance', ''), 
                        d.get('Poids', ''), 
                        d.get('Sexe', ''), 
                        d.get('Titre_Honorifique', '')
                    ])
                ws.append_rows(new_rows)
        except: 
            ws = sh.add_worksheet("Athletes", 1000, 6)
            ws.append_row(["Nom", "Prenom", "Annee_Naissance", "Poids", "Sexe", "Titre_Honorifique"])

        # 4. PRE-INSCRIPTIONS (Zone tampon - On reset pour éviter les bugs)
        st.write("Resetting 'PreInscriptions'...")
        try: ws = sh.worksheet("PreInscriptions")
        except: ws = sh.add_worksheet("PreInscriptions", 1000, 7)
        ws.clear()
        ws.append_row(["Competition_Cible", "Nom", "Prenom", "Annee", "Poids", "Sexe", "Categorie"])
        
        # 5. HISTORIQUE (On touche pas aux données, juste vérif headers)
        st.write("Checking 'Historique'...")
        try: ws = sh.worksheet("Historique")
        except: ws = sh.add_worksheet("Historique", 1000, 4)
        if not ws.row_values(1):
            ws.append_row(["Competition", "Date", "Combattant", "Medaille"])

        status.update(label="✅ Base de données réparée et cohérente !", state="complete")
        st.success("Structure validée. Vous pouvez charger le Code V37.")
