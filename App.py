import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="SETUP BDD", page_icon="⚠️")

st.title("⚠️ Initialisation de la Base de Données")
st.warning("Ce script va reformater entièrement votre Google Sheet et injecter l'historique.")

# --- DONNÉES À INJECTER (HISTORIQUE 22/11/2025) ---
COMPETITION = "Championnat Régional AURA 2025"
DATE = "2025-11-22"

HISTO_DATA = [
    # OR
    [COMPETITION, DATE, "Pauline", "🥇 Or"],
    [COMPETITION, DATE, "Meline", "🥇 Or"],
    [COMPETITION, DATE, "Maevan", "🥇 Or"],
    [COMPETITION, DATE, "Armand", "🥇 Or"],
    # ARGENT
    [COMPETITION, DATE, "Benjamin", "🥈 Argent"],
    # BRONZE
    [COMPETITION, DATE, "Lucas", "🥉 Bronze"],
    [COMPETITION, DATE, "Elise", "🥉 Bronze"],
    [COMPETITION, DATE, "Nicolas", "🥉 Bronze"],
    # 4EME
    [COMPETITION, DATE, "Axel", "🍫 4ème"],
    [COMPETITION, DATE, "Julien", "🍫 4ème"]
]

# --- DONNÉES ATHLÈTES (BIO) ---
ATHLETES_DATA = [
    ["Pauline", "Double Championne de France"]
]

# --- CONNEXION ---
try:
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    # Ouverture du fichier principal
    sh = client.open("suivi_combats")
except Exception as e:
    st.error(f"Erreur de connexion : {e}")
    st.stop()

if st.button("🚀 LANCER L'INITIALISATION (Irréversible)", type="primary"):
    with st.status("Travail en cours...", expanded=True) as status:
        
        # 1. FEUILLE LIVE (Feuille 1)
        st.write("Formatage de 'Feuille 1' (Live)...")
        ws_live = sh.sheet1
        ws_live.clear()
        # Titres exacts requis par V13
        live_headers = ["Combattant", "Aire", "Numero", "Casque", "Statut", "Palmares", "Details_Tour", "Medaille_Actuelle"]
        ws_live.append_row(live_headers)
        
        # 2. FEUILLE HISTORIQUE
        st.write("Création/Formatage de 'Historique'...")
        try:
            ws_hist = sh.worksheet("Historique")
        except:
            ws_hist = sh.add_worksheet(title="Historique", rows=1000, cols=10)
        
        ws_hist.clear()
        hist_headers = ["Competition", "Date", "Combattant", "Medaille"]
        # On prépare tout le bloc (Titres + Données)
        hist_payload = [hist_headers] + HISTO_DATA
        ws_hist.update(hist_payload)
        
        # 3. FEUILLE ATHLETES
        st.write("Création/Formatage de 'Athletes'...")
        try:
            ws_ath = sh.worksheet("Athletes")
        except:
            ws_ath = sh.add_worksheet(title="Athletes", rows=100, cols=5)
            
        ws_ath.clear()
        ath_headers = ["Nom", "Titre_Honorifique"]
        ath_payload = [ath_headers] + ATHLETES_DATA
        ws_ath.update(ath_payload)
        
        status.update(label="✅ Initialisation Terminée !", state="complete", expanded=False)
    
    st.success("La base de données est parfaite.")
    st.balloons()
    st.markdown("### 👉 Maintenant, remettez le code de l'application V13 dans GitHub.")
