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
    # Assurez-vous que le nom ici est bien celui de votre Google Sheet
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
st.title("🥊 Suivi Combats Mobile")

# 1. FORMULAIRE (MODIFIÉ : AIRE MANUELLE)
with st.expander("➕ Ajouter un combattant", expanded=True):
    with st.form("add_form"):
        nom = st.text_input("Nom du combattant")
        
        col_a, col_b = st.columns(2)
        
        # --- CHANGEMENT ICI : Saisie libre du numéro d'aire ---
        aire = col_a.number_input("N° Aire", min_value=1, step=1)
        
        num = col_b.number_input("N° Combat", min_value=1, step=1)
        casque = st.radio("Casque", ["Rouge", "Bleu"], horizontal=True)
        
        if st.form_submit_button("Valider et Enregistrer"):
            if nom:
                add_data(nom, aire, num, casque)
                st.success("C'est enregistré !")
                st.rerun()
            else:
                st.error("Il faut mettre un nom !")

# 2. LISTE TRIÉE
st.divider()
st.subheader("Chronologie des passages")

try:
    df = get_data()
    if not df.empty:
        # Sécurisation des données pour le tri
        df['Numero'] = pd.to_numeric(df['Numero'], errors='coerce')
        df['Aire'] = pd.to_numeric(df['Aire'], errors='coerce')
        
        # Tri : D'abord par Numéro de combat, ensuite par Aire
        df_sorted = df.sort_values(by=['Numero', 'Aire'])
        
        for i, row in df_sorted.iterrows():
            icon = "🔴" if row['Casque'] == "Rouge" else "🔵"
            
            # Gestion des erreurs d'affichage si une ligne est vide
            num_combat = int(row['Numero']) if pd.notnull(row['Numero']) else "?"
            num_aire = int(row['Aire']) if pd.notnull(row['Aire']) else "?"
            
            with st.container():
                st.info(f"**Combat #{num_combat}** (Aire {num_aire})\n\n{icon} **{row['Combattant']}**")
    else:
        st.info("La liste est vide pour l'instant.")

except Exception as e:
    st.error(f"Une petite erreur est survenue : {e}")
    st.warning("Vérifiez que la colonne C de votre Google Sheet s'appelle bien 'Numero' (sans accent).")
