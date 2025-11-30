import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import urllib.parse
import time

# --- CONFIGURATION & DESIGN ---
st.set_page_config(page_title="Fight Tracker V45", page_icon="🥊", layout="wide")

# --- CSS MODERNE (NEON SPORT THEME) ---
st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Oswald:wght@400;600&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    
    <style>
        /* --- GLOBAL --- */
        .stApp {
            background-color: #0e1117;
            font-family: 'Inter', sans-serif;
        }
        h1, h2, h3 { font-family: 'Oswald', sans-serif !important; text-transform: uppercase; letter-spacing: 1px; }
        
        /* --- BOUTONS MODERNES --- */
        .stButton > button {
            width: 100%;
            border-radius: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 0.6rem 1rem;
            transition: all 0.2s ease-in-out;
            border: none;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.5);
        }
        
        /* Couleur spécifique boutons primaires (Rouge par défaut -> Bleu/Vert selon contexte) */
        div[data-testid="stButton"] button { background-color: #262730; color: white; border: 1px solid #444; }
        div[data-testid="stButton"] button:hover { border-color: #FFD700; color: #FFD700; }

        /* --- TABS (NAVIGATION) --- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: #1A1C24;
            padding: 10px;
            border-radius: 16px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: transparent;
            border-radius: 8px;
            color: #aaa;
            font-family: 'Oswald', sans-serif;
            font-size: 1.1rem;
        }
        .stTabs [aria-selected="true"] {
            background-color: #FFD700 !important;
            color: #000 !important;
            box-shadow: 0 2px 10px rgba(255, 215, 0, 0.3);
        }

        /* --- CARTE COMBAT (PUBLIC) --- */
        .combat-card {
            background: linear-gradient(135deg, #1E2028 0%, #16181D 100%);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 12px;
            border: 1px solid #333;
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
            position: relative;
            overflow: hidden;
        }
        /* Indicateur visuel status */
        .status-bar { height: 100%; width: 6px; position: absolute; left: 0; top: 0; }
        .bar-red { background: #FF4B4B; box-shadow: 0 0 10px #FF4B4B; }
        .bar-green { background: #00C853; }
        .bar-grey { background: #555; }

        .card-content { margin-left: 12px; }
        
        .header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .combat-badge { 
            background: #333; color: #eee; padding: 4px 10px; 
            border-radius: 8px; font-weight: bold; font-size: 0.9rem; font-family: 'Oswald';
        }
        .aire-badge { background: #FFD700; color: black; }
        
        .fighter-name { font-family: 'Oswald'; font-size: 1.8rem; font-weight: 600; color: white; line-height: 1.2; }
        .fighter-meta { color: #888; font-size: 0.9rem; font-style: italic; }
        
        /* --- ZONE DISPATCH (COACH) --- */
        .dispatch-card {
            background-color: #22252E;
            border: 1px solid #444;
            border-radius: 12px;
            padding: 12px;
            margin-bottom: 8px;
        }
        .dispatch-name { color: #FFD700; font-weight: bold; font-size: 1.1rem; }
        
        /* --- ALERTE TOAST --- */
        .stToast { background-color: #333 !important; border-left: 5px solid #00C853; }
    </style>
""", unsafe_allow_html=True)

# --- CONNEXION ---
@st.cache_resource
def get_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# --- LOGIQUE ---
def calculer_categorie(annee, poids, sexe):
    try:
        if not annee or not poids: return ""
        age = datetime.now().year - int(annee)
        poids = float(poids)
        cat_age = "Inconnu"
        if 7 <= age <= 9: cat_age = "Poussin"
        elif 10 <= age <= 11: cat_age = "Benjamin"
        elif 12 <= age <= 13: cat_age = "Minime"
        elif 14 <= age <= 15: cat_age = "Cadet"
        elif 16 <= age <= 17: cat_age = "Junior"
        elif 18 <= age <= 40: cat_age = "Senior"
        elif age >= 41: cat_age = "Vétéran"
        limites = []
        if cat_age == "Poussin": limites = [23, 28, 32, 37, 42, 47]
        elif cat_age == "Benjamin": limites = [28, 32, 37, 42, 47, 52]
        elif cat_age == "Minime": limites = [32, 37, 42, 47, 52, 57, 63, 69]
        elif cat_age == "Cadet": limites = [32, 37, 42, 47, 52, 57, 63, 69, 74]
        elif cat_age in ["Junior", "Senior", "Vétéran"]:
            if sexe == "F": limites = [48, 52, 56, 60, 65, 70]
            else: limites = [57, 63, 69, 74, 79, 84, 89, 94]
        cat_poids = "Hors cat."
        if limites and poids > limites[-1]: cat_poids = f"+{limites[-1]}kg"
        else:
            for lim in limites:
                if poids <= lim: cat_poids = f"-{lim}kg"; break
        return f"{cat_age} {sexe} {cat_poids}"
    except: return "?"

# --- BDD ---
def get_worksheet_safe(name, cols):
    client = get_client()
    try: sh = client.open("suivi_combats")
    except: return None
    try: 
        ws_list = [s.title for s in sh.worksheets()]
        if name in ws_list: return sh.worksheet(name)
        else: ws = sh.add_worksheet(name, 1000, len(cols)+2); ws.append_row(cols); return ws
    except: return None

@st.cache_data(ttl=5)
def fetch_data(sheet_name, cols):
    ws = get_worksheet_safe(sheet_name, cols)
    if ws:
        try: 
            df = pd.DataFrame(ws.get_all_records())
            for col in cols:
                if col not in df.columns: df[col] = ""
            return df
        except: return pd.DataFrame(columns=cols)
    return pd.DataFrame(columns=cols)

def get_live_data(): return fetch_data("Feuille 1", ["Combattant", "Aire", "Numero", "Casque", "Statut", "Palmares", "Details_Tour", "Medaille_Actuelle"])
def get_history_data(): return fetch_data("Historique", ["Competition", "Date", "Combattant", "Medaille"])
def get_athletes_db(): return fetch_data("Athletes", ["Nom", "Prenom", "Annee_Naissance", "Poids", "Sexe", "Titre_Honorifique"])
def get_calendar_db(): return fetch_data("Calendrier", ["Nom_Competition", "Date_Prevue"])
def get_preinscriptions_db(): return fetch_data("PreInscriptions", ["Competition_Cible", "Nom", "Prenom", "Annee", "Poids", "Sexe", "Categorie"])

def save_data(df, sheet_name, cols_def):
    ws = get_worksheet_safe(sheet_name, cols_def)
    if ws:
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.values.tolist())
        fetch_data.clear()

def save_athlete(nom
