import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURATION ---
st.set_page_config(page_title="Fight Tracker", page_icon="🥊", layout="centered")

# --- CONNEXION SECURISEE ---
def get_connection():
    # On définit le périmètre d'accès (Scope)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # On récupère les infos secrètes depuis le fichier secrets.toml de Streamlit
    # Assurez-vous d'avoir bien rempli .streamlit/secrets.toml
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # OUVERTURE DU FICHIER - Remplacer par le nom EXACT de votre fichier
    sheet = client.open("suivi_combats").sheet1 
    return sheet

# --- FONCTIONS ---
def get_data():
    sh = get_connection()
    data = sh.get_all_records()
    # Si vide, on retourne un dataframe vide avec les bonnes colonnes
    if not data:
        return pd.DataFrame(columns=["Combattant", "Aire", "Numero", "Casque", "Statut"])
    return pd.DataFrame(data)

def add_data(combattant, aire, numero, casque):
    sh = get_connection()
    # On ajoute la ligne
    sh.append_row([combattant, aire, numero, casque, "A venir"])

# --- INTERFACE ---
st.title("🥊 Suivi Combats Mobile")

# 1. FORMULAIRE
with st.expander("➕ Ajouter un combattant", expanded=False):
    with st.form("add_form"):
        nom = st.text_input("Nom")
        col_a, col_b = st.columns(2)
        aire = col_a.selectbox("Aire", ["Aire 1", "Aire 2", "Aire 3"])
        num = col_b.number_input("N° Combat", min_value=1, step=1)
        casque = st.radio("Casque", ["Rouge", "Bleu"], horizontal=True)
        
        if st.form_submit_button("Valider"):
            add_data(nom, aire, num, casque)
            st.success("Ajouté !")
            st.rerun()

# 2. LISTE TRIÉE
st.subheader("Chronologie des passages")

try:
    df = get_data()
    if not df.empty:
        # Conversion Numéro en entier pour bien trier (éviter que 10 soit avant 2)
        df['Numero'] = pd.to_numeric(df['Numero'])
        
        # TRI MAGIQUE : Par Numéro croissant, puis par Aire
        df_sorted = df.sort_values(by=['Numero', 'Aire'])
        
        # AFFICHAGE
        for i, row in df_sorted.iterrows():
            icon = "🔴" if row['Casque'] == "Rouge" else "🔵"
            with st.container():
                # Design type "Billet d'avion"
                st.info(f"**Combat #{row['Numero']}** | {row['Aire']}\n\n{icon} **{row['Combattant']}**")
    else:
        st.info("Aucun combat enregistré.")

except Exception as e:
    st.error(f"Erreur de connexion : {e}")
    st.warning("Avez-vous bien créé le fichier secrets.toml et partagé le Sheet ?")
