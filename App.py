import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import urllib.parse
import time
import re

# Gestion pdfplumber
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

# --- CONFIGURATION & DESIGN ---
st.set_page_config(page_title="Fight Tracker V53", page_icon="🥊", layout="wide")

st.markdown("""
    <style>
        html, body, [class*="css"]  { font-family: 'Roboto', sans-serif; font-size: 14px; }
        .combat-card {
            background: linear-gradient(145deg, #1E1E1E, #252525);
            border-radius: 8px; padding: 12px; margin-bottom: 8px; 
            border-left: 4px solid #555; box-shadow: 0 2px 5px rgba(0,0,0,0.3);
        }
        .card-termine { opacity: 0.6; filter: grayscale(0.8); border-left: 4px solid #333 !important; }
        .header-line { display: flex; justify-content: space-between; align-items: baseline; }
        .combat-num { font-style: italic; font-size: 1.1em; color: #ddd; font-weight:bold;}
        .combat-aire { background: #FFD700; color:black; padding: 2px 8px; border-radius: 10px; font-size: 0.85em; font-weight: bold; }
        .fighter-name { font-size: 1.3em; font-weight: 700; color: #fff; }
        .honor-title { font-size: 0.8em; color: #FFD700; font-style: italic; display:block; opacity:0.8;}
        .corner-red { color: #FF4B4B; border: 1px solid #FF4B4B; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; margin-right: 5px;}
        .corner-blue { color: #2196F3; border: 1px solid #2196F3; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; margin-right: 5px;}
        .stToast { background-color: #00C853 !important; color: white !important; }
        .dispatch-box { border: 2px dashed #FFD700; padding: 15px; border-radius: 10px; background-color: #2b2d35; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- CONNEXION ---
@st.cache_resource
def get_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# --- OUTILS ---
def clean_str(txt):
    return str(txt).strip().upper() if pd.notna(txt) else ""

def clean_prenom(txt):
    return str(txt).strip().title() if pd.notna(txt) else ""

def deduplicate_dataframe(df, subset_cols):
    """Supprime les doublons en gardant la dernière version (la plus récente)"""
    if df.empty: return df
    # On normalise temporairement pour la comparaison
    df['temp_key'] = df.apply(lambda x: "".join([str(x[c]).strip().upper() for c in subset_cols]), axis=1)
    df = df.drop_duplicates(subset=['temp_key'], keep='last')
    return df.drop(columns=['temp_key'])

# --- LOGIQUE METIER ---
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

def calculer_nombre_combats(nb_participants):
    try:
        n = int(nb_participants)
        if n <= 1: return "Seul ?"
        if n == 2: return "Finale"
        if n == 3: return "Poule"
        if n == 4: return "Demi + Fin"
        if 5 <= n <= 8: return "Quart -> Fin"
        return "Tournoi"
    except: return "?"

# --- IMPORT PDF ---
def parse_pdf_ffkmda(pdf_file, club_filter_keyword):
    if pdfplumber is None: return pd.DataFrame()
    all_entries = []
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    for row in table:
                        clean_row = [str(cell).replace('\n', ' ') if cell else "" for cell in row]
                        if len(clean_row) < 2: continue
                        if "Catégorie" in clean_row[0] or "Athlète" in clean_row[1]: continue
                        entry = {"Category": clean_row[0].strip(), "Athlete": clean_row[1].strip(), "Raw_Info": " ".join(clean_row)}
                        if not entry["Category"] and all_entries: entry["Category"] = all_entries[-1]["Category"]
                        if entry["Athlete"]: all_entries.append(entry)
            
            df_all = pd.DataFrame(all_entries)
            if df_all.empty: return pd.DataFrame()
            counts = df_all['Category'].value_counts()
            club_data = []
            for _, row in df_all.iterrows():
                if club_filter_keyword.upper() in row['Raw_Info'].upper():
                    aire = 0
                    match_aire = re.search(r'(?:AIRE|Aire)\s*(\d+)', row['Raw_Info'], re.IGNORECASE)
                    if match_aire: aire = int(match_aire.group(1))
                    
                    nb_in_cat = counts.get(row['Category'], 0)
                    txt_combats = calculer_nombre_combats(nb_in_cat)
                    
                    parts = row['Athlete'].split()
                    nom = " ".join(parts[:-1]) if len(parts)>1 else row['Athlete']
                    prenom = parts[-1] if len(parts)>1 else ""
                    
                    club_data.append({
                        "Nom": clean_str(nom),
                        "Prénom": clean_prenom(prenom),
                        "Catégorie Calculée": f"{row['Category']} ({txt_combats})",
                        "Aire_PDF": aire
                    })
            return pd.DataFrame(club_data)
    except Exception as e:
        st.error(f"Erreur PDF: {e}")
        return pd.DataFrame()

# --- BDD ---
def get_worksheet_safe(name, cols):
    client = get_client()
    try: sh = client.open("suivi_combats")
    except: return None
    try: 
        ws_list = [s.title for s in sh.worksheets()]
        if name in ws_list: return sh.worksheet(name)
        else: ws = sh.add_worksheet(name, 1000, len(cols)+2); ws.append_row(cols); time.sleep(1); return ws
    except: return None

@st.cache_data(ttl=5)
def fetch_data(sheet_name, expected_cols):
    ws = get_worksheet_safe(sheet_name, expected_cols)
    if ws:
        try: 
            df = pd.DataFrame(ws.get_all_records())
            for col in expected_cols:
                if col not in df.columns: df[col] = ""
            return df
        except: return pd.DataFrame(columns=expected_cols)
    return pd.DataFrame(columns=expected_cols)

def get_live_data(): return fetch_data("Feuille 1", ["Combattant", "Aire", "Numero", "Casque", "Statut", "Palmares", "Details_Tour", "Medaille_Actuelle"])
def get_history_data(): return fetch_data("Historique", ["Competition", "Date", "Combattant", "Medaille"])
def get_athletes_db(): return fetch_data("Athletes", ["Nom", "Prenom", "Annee_Naissance", "Poids", "Sexe", "Titre_Honorifique"])
def get_calendar_db(): return fetch_data("Calendrier", ["Nom_Competition", "Date_Prevue"])
def get_preinscriptions_db(): return fetch_data("PreInscriptions", ["Competition_Cible", "Nom", "Prenom", "Annee", "Poids", "Sexe", "Categorie"])

def save_data(df, sheet_name, cols_def):
    ws = get_worksheet_safe(sheet_name, cols_def)
    if ws:
        ws.clear()
        df = df.fillna("")
        ws.update([df.columns.values.tolist()] + df.values.tolist())
        fetch_data.clear()

def save_athlete(nom, prenom, titre, annee, poids, sexe):
    cols_order = ["Nom", "Prenom", "Annee_Naissance", "Poids", "Sexe", "Titre_Honorifique"]
    ws = get_worksheet_safe("Athletes", cols_order)
    if ws:
        df = pd.DataFrame(ws.get_all_records())
        if "Nom" not in df.columns: df = pd.DataFrame(columns=cols_order)
        nom = clean_str(nom)
        prenom = clean_prenom(prenom)
        
        # Anti-Doublon Base
        df['Key'] = df['Nom'].apply(clean_str) + "|" + df['Prenom'].apply(clean_prenom)
        key = nom + "|" + prenom
        
        if key in df['Key'].values:
            idx = df[df['Key'] == key].index[0]
            if titre: df.at[idx, "Titre_Honorifique"] = titre
            if annee: df.at[idx, "Annee_Naissance"] = annee
            if poids: df.at[idx, "Poids"] = poids
            if sexe: df.at[idx, "Sexe"] = sexe
        else:
            new_row = pd.DataFrame([{"Nom": nom, "Prenom": prenom, "Titre_Honorifique": titre, "Annee_Naissance": annee, "Poids": poids, "Sexe": sexe}])
            df = pd.concat([df, new_row], ignore_index=True)
        
        if 'Key' in df.columns: df = df.drop(columns=['Key'])
        df = df[cols_order].fillna("")
        ws.clear(); ws.update([df.columns.values.tolist()] + df.values.tolist()); fetch_data.clear()

def process_end_match(live_df, idx, resultat, nom_compet, date_compet, target_evt):
    live_df.at[idx, 'Statut'] = "Terminé"
    live_df.at[idx, 'Medaille_Actuelle'] = resultat
    live_df.at[idx, 'Palmares'] = resultat
    save_data(live_df, "Feuille 1", [])
    
    nom_full = live_df.at[idx, 'Combattant']
    hist = get_history_data()
    if nom_full and resultat:
        new_entry = pd.DataFrame([{"Competition": nom_compet, "Date": str(date_compet), "Combattant": nom_full, "Medaille": resultat}])
        save_data(pd.concat([hist, new_entry], ignore_index=True), "Historique", ["Competition", "Date", "Combattant", "Medaille"])
    
    if target_evt and resultat in ["🥇 Or", "🥈 Argent"]:
        ath = get_athletes_db()
        pre = get_preinscriptions_db()
        parts = str(nom_full).split()
        nom_s = " ".join(parts[:-1]); prenom_s = parts[-1] if len(parts)>1 else ""
        
        # Anti-doublon Inscription
        exists = False
        if not pre.empty:
            match = pre[(pre['Nom'] == nom_s) & (pre['Prenom'] == prenom_s) & (pre['Competition_Cible'] == target_evt)]
            if not match.empty: exists = True
        
        if not exists:
            inf_row = pd.DataFrame()
            if not ath.empty:
                inf_row = ath[(ath['Nom'] == nom_s) & (ath['Prenom'] == prenom_s)]
            cat = "?"
            if not inf_row.empty:
                inf = inf_row.iloc[0]
                cat = calculer_categorie(inf['Annee_Naissance'], inf['Poids'], inf['Sexe'])
                new_q = pd.DataFrame([{"Competition_Cible": target_evt, "Nom": nom_s, "Prenom": prenom_s, "Annee": inf['Annee_Naissance'], "Poids": inf['Poids'], "Sexe": inf['Sexe'], "Categorie": cat}])
            else:
                new_q = pd.DataFrame([{"Competition_Cible": target_evt, "Nom": nom_s, "Prenom": prenom_s, "Categorie": "A compléter"}])
            save_data(pd.concat([pre, new_q], ignore_index=True), "PreInscriptions", [])
            st.toast(f"Qualifié !", icon="🚀")

# --- INTERFACE ---
tab_public, tab_coach, tab_profil, tab_historique = st.tabs(["📢 LIVE", "🛠️ COACH", "👤 PROFILS", "🏛️ CLUB"])

# 1. LIVE
with tab_public:
    if st.button("Actualiser", key="ref_pub", use_container_width=True): st.rerun()
    df = get_live_data()
    df_ath = get_athletes_db()
    if not df.empty:
        df['Numero'] = pd.to_numeric(df['Numero'], errors='coerce').fillna(0)
        df['Aire'] = pd.to_numeric(df['Aire'], errors='coerce').fillna(0)
        df = df[(df['Numero'] > 0)].sort_values(by=['Numero', 'Aire'])
        st.markdown(f"<h2 style='text-align:center; color:#FFD700;'>{st.session_state.get('Config_Compet', 'Compétition en cours')}</h2>", unsafe_allow_html=True)
        if df.empty: st.info("Les combats n'ont pas encore commencé.")
        for i, row in df.iterrows():
            if row['Statut'] != "Terminé":
                css_class = "combat-card"
                border = "#FF4B4B" if "En cours" in row['Statut'] else "#444"
                titre = ""
                nom_complet = row['Combattant']
                if not df_ath.empty:
                    parts = str(nom_complet).split()
                    if len(parts) > 1:
                        n = " ".join(parts[:-1]); p = parts[-1]
                        info = df_ath[(df_ath['Nom'] == n) & (df_ath['Prenom'] == p)]
                        if not info.empty: titre = info.iloc[0]['Titre_Honorifique']
                med_badge = f"🏅 {row['Medaille_Actuelle']}" if row['Medaille_Actuelle'] else ""
                corner_span = "<span class='corner-red'>Rouge</span>" if row['Casque'] == "Rouge" else "<span class='corner-blue'>Bleu</span>"
                st.markdown(f"""
                <div class="{css_class}" style="border-left: 4px solid {border};">
                    <div class="
