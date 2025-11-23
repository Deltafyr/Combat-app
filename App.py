import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import urllib.parse

# --- CONFIGURATION & CSS ---
st.set_page_config(page_title="Fight Tracker V16", page_icon="🥊", layout="wide")

st.markdown("""
    <style>
        html, body, [class*="css"]  { font-family: 'Roboto', sans-serif; font-size: 14px; }
        .combat-card {
            background-color: #1E1E1E; border-radius: 8px; padding: 10px 14px;
            margin-bottom: 8px; border-left: 4px solid #555;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        .header-line { display: flex; justify-content: space-between; align-items: baseline; }
        .combat-num { font-style: italic; font-size: 1.1em; color: #ddd; }
        .tour-info { font-size: 0.85em; color: #aaa; margin-left: 5px; }
        .combat-aire { background: #333; padding: 2px 8px; border-radius: 10px; font-size: 0.85em; font-weight: bold; color: #FFD700; }
        .fighter-line { margin-top: 5px; }
        .fighter-name { font-size: 1.4em; font-weight: 700; color: #fff; display:block;}
        .honor-title { font-size: 0.85em; color: #FFD700; font-style: italic; margin-bottom: 4px; display:block;}
        .medal-badge { float:right; font-size: 1.2em; }
        .status-badge { font-size: 0.75em; color: #888; margin-top: 4px; text-transform: uppercase; letter-spacing: 1px;}
        .medal-pill { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; margin-right: 5px; margin-bottom: 5px; color:black;}
        .gold { background: #FFD700; } .silver { background: #C0C0C0; } .bronze { background: #CD7F32; }
    </style>
""", unsafe_allow_html=True)

# --- CONNEXION ---
def get_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# --- LOGIQUE FFKMDA (INTELLIGENCE CATÉGORIES) ---
def calculer_categorie(annee_naissance, poids, sexe):
    """Détermine la catégorie d'âge et de poids selon règles standard FFKMDA"""
    try:
        annee_actuelle = datetime.now().year
        # Pour la saison 2024/2025, on base souvent l'âge sur l'année civile
        age = annee_actuelle - int(annee_naissance)
        poids = float(poids)
        
        # 1. DÉTERMINATION AGE
        cat_age = "Inconnu"
        if 7 <= age <= 9: cat_age = "Poussin"
        elif 10 <= age <= 11: cat_age = "Benjamin"
        elif 12 <= age <= 13: cat_age = "Minime"
        elif 14 <= age <= 15: cat_age = "Cadet"
        elif 16 <= age <= 17: cat_age = "Junior"
        elif 18 <= age <= 40: cat_age = "Senior"
        elif age >= 41: cat_age = "Vétéran"
        
        # 2. DÉTERMINATION POIDS (Approximation Light Contact / Kick Light standard)
        limites = []
        
        if cat_age == "Poussin": limites = [23, 28, 32, 37, 42, 47]
        elif cat_age == "Benjamin": limites = [28, 32, 37, 42, 47, 52]
        elif cat_age == "Minime": limites = [32, 37, 42, 47, 52, 57, 63, 69]
        elif cat_age == "Cadet": limites = [32, 37, 42, 47, 52, 57, 63, 69, 74]
        
        elif cat_age in ["Junior", "Senior", "Vétéran"]:
            if sexe == "F": # Femmes
                limites = [48, 52, 56, 60, 65, 70] # +70
            else: # Hommes
                limites = [57, 63, 69, 74, 79, 84, 89, 94] # +94
        
        # Trouve la limite sup
        cat_poids = "Hors cat."
        found = False
        
        # Gestion des poids lourds (au dessus du max)
        if limites and poids > limites[-1]:
            cat_poids = f"+{limites[-1]}kg"
            found = True
        else:
            for lim in limites:
                if poids <= lim:
                    cat_poids = f"-{lim}kg"
                    found = True
                    break
        
        if not found and not limites: cat_poids = f"{poids}kg (Cat?)"
            
        return f"{cat_age} {sexe} {cat_poids}"
        
    except:
        return "Erreur Données"

# --- LECTURE/ECRITURE DONNÉES ---
def get_live_data():
    client = get_client()
    sh = client.open("suivi_combats").sheet1
    df = pd.DataFrame(sh.get_all_records())
    cols = ["Combattant", "Aire", "Numero", "Casque", "Statut", "Palmares", "Details_Tour", "Medaille_Actuelle"]
    for c in cols: 
        if c not in df.columns: df[c] = ""
    return df

def get_history_data():
    try:
        client = get_client()
        sh = client.open("suivi_combats").worksheet("Historique")
        return pd.DataFrame(sh.get_all_records())
    except: return pd.DataFrame(columns=["Competition", "Date", "Combattant", "Medaille"])

def get_athletes_db():
    try:
        client = get_client()
        sh = client.open("suivi_combats").worksheet("Athletes")
        return pd.DataFrame(sh.get_all_records())
    except: return pd.DataFrame(columns=["Nom", "Titre_Honorifique"])

def save_live_dataframe(df):
    client = get_client()
    sh = client.open("suivi_combats").sheet1
    sh.clear()
    sh.update([df.columns.values.tolist()] + df.values.tolist())

def save_history_dataframe(df):
    client = get_client()
    try: sh = client.open("suivi_combats").worksheet("Historique")
    except: sh = client.open("suivi_combats").add_worksheet(title="Historique", rows=1000, cols=4)
    sh.clear()
    sh.update([df.columns.values.tolist()] + df.values.tolist())

def save_athlete(nom, titre):
    client = get_client()
    try: sh = client.open("suivi_combats").worksheet("Athletes")
    except: sh = client.open("suivi_combats").add_worksheet(title="Athletes", rows=100, cols=5)
    df = pd.DataFrame(sh.get_all_records())
    if "Nom" not in df.columns: df = pd.DataFrame(columns=["Nom", "Titre_Honorifique"])
    if nom in df['Nom'].values: df.loc[df['Nom'] == nom, 'Titre_Honorifique'] = titre
    else: df = pd.concat([df, pd.DataFrame([{"Nom": nom, "Titre_Honorifique": titre}])], ignore_index=True)
    sh.clear()
    sh.update([df.columns.values.tolist()] + df.values.tolist())

# --- INTERFACE ---
tab_public, tab_profil, tab_historique, tab_coach = st.tabs(["📢 LIVE", "👤 PROFILS", "🏛️ CLUB", "🛠️ COACH"])

# 1. LIVE
with tab_public:
    if st.button("🔄 Actualiser", key="ref_pub"): st.rerun()
    try:
        df = get_live_data()
        df_athletes = get_athletes_db()
        if not df.empty:
            df['Numero'] = pd.to_numeric(df['Numero'], errors='coerce').fillna(0)
            df['Aire'] = pd.to_numeric(df['Aire'], errors='coerce').fillna(0)
            df_active = df[df['Numero'] > 0].sort_values(by=['Numero', 'Aire'])
            
            titre_compet = st.session_state.get('Config_Compet', "Compétition en cours")
            st.markdown(f"### 📍 {titre_compet}")

            for i, row in df_active.iterrows():
                if row['Statut'] != "Terminé":
                    icon_casque = "🔴" if row['Casque'] == "Rouge" else "🔵"
                    border = "#FF4B4B" if "En cours" in row['Statut'] else "#444"
                    
                    titre_honorifique = ""
                    if not df_athletes.empty:
                        infos = df_athletes[df_athletes['Nom'] == row['Combattant']]
                        if not infos.empty: titre_honorifique = infos.iloc[0]['Titre_Honorifique']

                    st.markdown(f"""
                    <div class="combat-card" style="border-left: 4px solid {border};">
                        <div class="header-line">
                            <span class="combat-num">Combat n°{int(row['Numero'])} <span class="tour-info">({row['Details_Tour']})</span></span>
                            <span class="combat-aire">Aire {int(row['Aire'])}</span>
                        </div>
                        <div class="fighter-line">
                            <span class="fighter-name">{icon_casque} {row['Combattant']} <span class="medal-badge">{row['Medaille_Actuelle']}</span></span>
                            <span class="honor-title">{titre_honorifique}</span>
                        </div>
                        <div class="status-badge">{row['Statut']}</div>
                    </div>
                    """, unsafe_allow_html=True)
            if df_active.empty: st.info("Aucun combat affiché.")
    except Exception as e: st.error(f"Erreur: {e}")

# 2. PROFILS
with tab_profil:
    st.header("Fiches Athlètes")
    df_hist = get_history_data()
    df_athletes = get_athletes_db()
    all_names = set(df_hist['Combattant'].unique()) if not df_hist.empty else set()
    if not df_athletes.empty: all_names.update(df_athletes['Nom'].unique())
    if all_names:
        search = st.selectbox("Rechercher", sorted(list(all_names)))
        bio = ""
        if not df_athletes.empty:
            infos = df_athletes[df_athletes['Nom'] == search]
            if not infos.empty: bio = infos.iloc[0]['Titre_Honorifique']
        st.markdown(f"## {search}")
        if
