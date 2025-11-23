import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURATION ---
st.set_page_config(page_title="Fight Tracker", page_icon="🥊", layout="centered")

# --- CONNEXION SECURISEE ---
def get_connection():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("suivi_combats").sheet1 
    return sheet

# --- FONCTIONS ---
def get_data():
    sh = get_connection()
    data = sh.get_all_records()
    if not data:
        return pd.DataFrame(columns=["Combattant", "Aire", "Numero", "Casque", "Statut"])
    return pd.DataFrame(data)

def add_data(combattant, aire, numero, casque):
    sh = get_connection()
    sh.append_row([combattant, aire, numero, casque, "A venir"])

# --- INTERFACE ---
st.title("🥊 Chronologie des Combats")
st.caption("Suivez l'ordre de passage en temps réel")

# 1. LA LISTE (VISIBLE PAR TOUS EN PREMIER)
try:
    df = get_data()
    if not df.empty:
        # Sécurisation et Tri
        df['Numero'] = pd.to_numeric(df['Numero'], errors='coerce')
        df['Aire'] = pd.to_numeric(df['Aire'], errors='coerce')
        df_sorted = df.sort_values(by=['Numero', 'Aire'])
        
        # Affichage optimisé lecture
        for i, row in df_sorted.iterrows():
            icon = "🔴" if row['Casque'] == "Rouge" else "🔵"
            num_combat = int(row['Numero']) if pd.notnull(row['Numero']) else "?"
            num_aire = int(row['Aire']) if pd.notnull(row['Aire']) else "?"
            
            # Design carte épuré
            with st.container():
                st.markdown(f"""
                <div style="padding: 10px; border-radius: 5px; border: 1px solid #333; margin-bottom: 10px;">
                    <h3 style="margin:0;">Combat #{num_combat} <span style="font-size:0.7em; color:gray;">(Aire {num_aire})</span></h3>
                    <div style="font-size:1.2em;">{icon} <strong>{row['Combattant']}</strong></div>
                </div>
                """, unsafe_allow_html=True)

    else:
        st.info("Aucun combat prévu pour le moment.")
        
    if st.button("🔄 Actualiser la liste"):
        st.rerun()

except Exception as e:
    st.error("Erreur de chargement. Le coach est sur le coup !")

# 2. ZONE COACH (PROTÉGÉE)
st.divider()
with st.expander("🔒 Accès Coach (Ajouter un combat)"):
    password = st.text_input("Mot de passe Coach", type="password")
    
    # CHANGEZ LE MOT DE PASSE ICI SI VOUS VOULEZ (Par défaut: 1234)
    if password == "1234": 
        st.success("Mode Édition Activé")
        with st.form("add_form"):
            nom = st.text_input("Nom du combattant")
            col_a, col_b = st.columns(2)
            aire = col_a.number_input("N° Aire", min_value=1, step=1)
            num = col_b.number_input("N° Combat", min_value=1, step=1)
            casque = st.radio("Casque", ["Rouge", "Bleu"], horizontal=True)
            
            if st.form_submit_button("Enregistrer"):
                add_data(nom, aire, num, casque)
                st.success("Ajouté !")
                st.rerun()
    elif password:
        st.error("Mot de passe incorrect")
