import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import re
from bs4 import BeautifulSoup

# --- MODULE SELENIUM (LE ROBOT) ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# --- CONFIGURATION & DESIGN ---
st.set_page_config(page_title="Fight Tracker V50", page_icon="🥊", layout="wide")

st.markdown("""
    <style>
        html, body, [class*="css"]  { font-family: 'Roboto', sans-serif; font-size: 14px; }
        .combat-card {
            background: linear-gradient(145deg, #1E1E1E, #252525);
            border-radius: 12px; padding: 15px; margin-bottom: 12px; 
            border-left: 5px solid #555; box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }
        .header-line { display: flex; justify-content: space-between; align-items: baseline; }
        .combat-num { font-family: 'Oswald', sans-serif; font-size: 1.4em; color: #fff; font-weight:bold;}
        .combat-aire { background: #FFD700; color:black; padding: 4px 10px; border-radius: 20px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.5);}
        .fighter-name { font-family: 'Oswald', sans-serif; font-size: 1.6em; font-weight: 500; color: #fff; text-transform: uppercase; }
        .honor-title { font-size: 0.9em; color: #FFD700; font-style: italic; opacity:0.8;}
        .corner-red { border-left: 3px solid #FF4B4B; padding-left: 10px; }
        .corner-blue { border-left: 3px solid #2196F3; padding-left: 10px; }
        .opponent-box { background-color: #2b2d35; padding: 10px; border-radius: 8px; margin-top: 8px; border-left: 3px solid #FF4B4B; }
        .stToast { background-color: #00C853 !important; color: white !important; }
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Oswald:wght@400;600&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)

# --- CONNEXION BDD ---
@st.cache_resource
def get_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# --- LOGIQUE MÉTIER ---
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

def estimer_tours_detail(nb_competiteurs):
    try:
        n = int(nb_competiteurs)
        if n <= 1: return "Seul (Gagnant)", 0
        if n == 2: return "Finale Directe", 1
        if n == 3: return "Poule (1 ou 2 combats)", 2
        if n == 4: return "Demi + Finale", 2
        if 5 <= n <= 8: return "Quart -> Finale", 3
        if 9 <= n <= 16: return "8ème -> Finale", 4
        return "Tableau > 16", 5
    except: return "Inconnu", 0

# --- ROBOT SCRAPER (SELENIUM) ---
def run_robot_scraper(login_url, target_url, username, password, id_field_selector, pass_field_selector, submit_selector):
    """Lance un navigateur Chrome invisible, se connecte, et récupère le HTML de la liste"""
    driver = None
    try:
        # Options pour rendre le navigateur invisible (Headless) mais robuste
        chrome_options = Options()
        chrome_options.add_argument("--headless") 
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        with st.spinner("🤖 Le robot démarre Chrome..."):
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        
        # 1. LOGIN
        with st.spinner("🔐 Connexion au site..."):
            driver.get(login_url)
            time.sleep(2) # Pause sécurité
            
            # Remplissage Formulaire
            # On cherche par ID, Name ou Class selon ce que l'utilisateur a donné
            try:
                user_box = driver.find_element(By.CSS_SELECTOR, id_field_selector)
                pass_box = driver.find_element(By.CSS_SELECTOR, pass_field_selector)
                submit_btn = driver.find_element(By.CSS_SELECTOR, submit_selector)
                
                user_box.send_keys(username)
                pass_box.send_keys(password)
                submit_btn.click()
            except Exception as e:
                return None, f"❌ Impossible de trouver les champs de connexion. Vérifiez les sélecteurs CSS. ({str(e)})"
            
            time.sleep(3) # Attente validation connexion

        # 2. ACCÈS LISTE
        with st.spinner("📄 Récupération de la liste des inscrits..."):
            driver.get(target_url)
            # Attente intelligente que le tableau se charge (max 10 sec)
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "table"))
                )
            except:
                st.warning("⚠️ Le tableau met du temps à charger ou n'est pas standard...")
            
            time.sleep(2) # Sécurité pour le Javascript
            html_content = driver.page_source
            
        return html_content, "OK"

    except Exception as e:
        return None, f"Erreur critique du Robot : {e}"
    finally:
        if driver: driver.quit()

# --- ANALYSEUR HTML (V49 Réutilisé) ---
def parse_html_content(html_content, athletes_db):
    soup = BeautifulSoup(html_content, 'html.parser')
    tables = pd.read_html(str(soup))
    
    if not tables: return "ERROR", "Aucun tableau trouvé."
    
    # On prend le plus grand tableau trouvé (souvent c'est celui des données)
    full_df = pd.DataFrame()
    for t in tables:
        if len(t) > len(full_df): full_df = t
            
    full_df = full_df.astype(str)
    full_df.columns = [str(c).lower() for c in full_df.columns]
    
    # Détection dynamique des colonnes
    col_nom = next((c for c in full_df.columns if 'nom' in c), None)
    col_cat = next((c for c in full_df.columns if 'cat' in c or 'poids' in c or 'weight' in c), None)
    
    if not col_cat: return "ERROR", "Pas de colonne 'Catégorie' détectée."

    matches = []
    grouped = full_df.groupby(col_cat)
    
    for cat_name, group in grouped:
        competitors = []
        for _, row in group.iterrows():
            txt = " ".join([str(val) for val in row.values])
            competitors.append(txt.upper())
            
        for _, ath in athletes_db.iterrows():
            mon_nom = str(ath['Nom']).upper()
            mon_prenom = str(ath['Prenom']).upper()
            
            # Recherche stricte
            found = False
            found_str = ""
            for c in competitors:
                if mon_nom in c and mon_prenom in c:
                    found = True; found_str = c; break
            
            if found:
                opponents = [c[:30]+"..." for c in competitors if c != found_str] # Clean names
                matches.append({
                    "Nom": ath['Nom'], "Prenom": ath['Prenom'],
                    "Categorie_Web": cat_name,
                    "Nb_Poule": len(competitors),
                    "Adversaires": opponents
                })
    return "SUCCESS", matches

# --- FONCTIONS BDD (inchangées) ---
def get_worksheet_safe(name, cols):
    client = get_client()
    try: 
        sh = client.open("suivi_combats")
        ws_list = [s.title for s in sh.worksheets()]
        if name in ws_list: return sh.worksheet(name)
        else: ws = sh.add_worksheet(name, 1000, len(cols)+2); ws.append_row(cols); return ws
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
        ws.clear(); ws.update([df.columns.values.tolist()] + df.values.tolist()); fetch_data.clear()

def save_athlete(nom, prenom, titre, annee, poids, sexe):
    cols_order = ["Nom", "Prenom", "Annee_Naissance", "Poids", "Sexe", "Titre_Honorifique"]
    ws = get_worksheet_safe("Athletes", cols_order)
    if ws:
        df = pd.DataFrame(ws.get_all_records())
        if "Nom" not in df.columns: df = pd.DataFrame(columns=cols_order)
        nom = str(nom).strip().upper(); prenom = str(prenom).strip().capitalize()
        mask = (df['Nom'] == nom) & (df['Prenom'] == prenom)
        if mask.any():
            idx = df[mask].index[0]
            if titre: df.at[idx, "Titre_Honorifique"] = titre
            if annee: df.at[idx, "Annee_Naissance"] = annee
            if poids: df.at[idx, "Poids"] = poids
            if sexe: df.at[idx, "Sexe"] = sexe
        else:
            new_row = pd.DataFrame([{"Nom": nom, "Prenom": prenom, "Titre_Honorifique": titre, "Annee_Naissance": annee, "Poids": poids, "Sexe": sexe}])
            df = pd.concat([df, new_row], ignore_index=True)
        df = df[cols_order]
        ws.clear(); ws.update([df.columns.values.tolist()] + df.values.tolist()); fetch_data.clear()

def process_end_match(live_df, idx, resultat, nom_compet, date_compet, target_evt):
    live_df.at[idx, 'Statut'] = "Terminé"; live_df.at[idx, 'Medaille_Actuelle'] = resultat; live_df.at[idx, 'Palmares'] = resultat
    save_data(live_df, "Feuille 1", [])
    nom_full = live_df.at[idx, 'Combattant']
    hist = get_history_data()
    if nom_full and resultat:
        new_entry = pd.DataFrame([{"Competition": nom_compet, "Date": str(date_compet), "Combattant": nom_full, "Medaille": resultat}])
        save_data(pd.concat([hist, new_entry], ignore_index=True), "Historique", ["Competition", "Date", "Combattant", "Medaille"])
    if target_evt and resultat in ["🥇 Or", "🥈 Argent"]:
        ath = get_athletes_db(); pre = get_preinscriptions_db()
        parts = str(nom_full).split(); nom_s = " ".join(parts[:-1]); prenom_s = parts[-1] if len(parts)>1 else ""
        if pre[(pre['Nom'] == nom_s) & (pre['Prenom'] == prenom_s) & (pre['Competition_Cible'] == target_evt)].empty:
            inf_row = pd.DataFrame()
            if not ath.empty: inf_row = ath[(ath['Nom'] == nom_s) & (ath['Prenom'] == prenom_s)]
            cat = "?"
            if not inf_row.empty:
                inf = inf_row.iloc[0]; cat = calculer_categorie(inf['Annee_Naissance'], inf['Poids'], inf['Sexe'])
                new_q = pd.DataFrame([{"Competition_Cible": target_evt, "Nom": nom_s, "Prenom": prenom_s, "Annee": inf['Annee_Naissance'], "Poids": inf['Poids'], "Sexe": inf['Sexe'], "Categorie": cat}])
            else: new_q = pd.DataFrame([{"Competition_Cible": target_evt, "Nom": nom_s, "Prenom": prenom_s, "Categorie": "A compléter"}])
            save_data(pd.concat([pre, new_q], ignore_index=True), "PreInscriptions", []); st.toast(f"Qualifié !", icon="🚀")

# --- INTERFACE ---
tab_public, tab_coach, tab_profil, tab_historique = st.tabs(["📢 LIVE", "🛠️ COACH", "👤 PROFILS", "🏛️ CLUB"])

# 1. LIVE
with tab_public:
    if st.button("Actualiser", key="ref_pub", use_container_width=True): st.rerun()
    df = get_live_data(); df_ath = get_athletes_db()
    if not df.empty:
        df['Numero'] = pd.to_numeric(df['Numero'], errors='coerce').fillna(0); df['Aire'] = pd.to_numeric(df['Aire'], errors='coerce').fillna(0)
        df = df[(df['Numero'] > 0)].sort_values(by=['Numero', 'Aire'])
        st.markdown(f"<h2 style='text-align:center; color:#FFD700;'>{st.session_state.get('Config_Compet', 'Compétition en cours')}</h2>", unsafe_allow_html=True)
        for i, row in df.iterrows():
            if row['Statut'] != "Terminé":
                titre = ""
                if not df_ath.empty:
                    parts = str(row['Combattant']).split()
                    if len(parts) > 1:
                        n = " ".join(parts[:-1]); p = parts[-1]
                        info = df_ath[(df_ath['Nom'] == n) & (df_ath['Prenom'] == p)]
                        if not info.empty: titre = info.iloc[0]['Titre_Honorifique']
                med_badge = f"🏅 {row['Medaille_Actuelle']}" if row['Medaille_Actuelle'] else ""
                corner_span = "<span class='corner-red'>Rouge</span>" if row['Casque'] == "Rouge" else "<span class='corner-blue'>Bleu</span>"
                st.markdown(f"""<div class="combat-card"><div class="header-line"><div><span class="combat-num">CBT #{int(row['Numero'])}</span><span class="tour-info">{row['Details_Tour']}</span></div><span class="combat-aire">AIRE {int(row['Aire'])}</span></div><div class="fighter-line"><div>{corner_span}<span class="fighter-name">{row['Combattant']} {med_badge}</span><span class="honor-title">{titre}</span></div></div><div class="status-badge">{row['Statut']}</div></div>""", unsafe_allow_html=True)
    else: st.info("Aucun combat.")

# 2. COACH
with tab_coach:
    if st.text_input("Code", type="password") == "1234":
        subtab_pilotage, subtab_admin = st.tabs(["⚡ PILOTAGE LIVE", "⚙️ CONFIG & ADMIN"])
        
        with subtab_pilotage:
            st.caption(f"Événement : **{st.session_state.get('Config_Compet', 'Non Défini')}**")
            live = get_live_data()
            if not live.empty:
                live['Numero'] = pd.to_numeric(live['Numero'], errors='coerce').fillna(0)
                waiting_list = live[(live['Statut'] != "Terminé") & (live['Numero'] == 0)]
                if not waiting_list.empty:
                    st.markdown("### ⚠️ À PROGRAMMER")
                    for idx, row in waiting_list.iterrows():
                        with st.container(border=True):
                            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                            c1.markdown(f"**{row['Combattant']}**<br><span style='color:grey'>{row.get('Details_Tour','')}</span>", unsafe_allow_html=True)
                            na = c2.number_input("Aire", value=1, key=f"wa_{idx}"); nn = c3.number_input("N°", value=1, key=f"wn_{idx}")
                            if c4.button("GO", key=f"go_{idx}"):
                                live.at[idx, 'Aire'] = na; live.at[idx, 'Numero'] = nn; save_data(live, "Feuille 1", []); st.rerun()
                
                active_view = live[(live['Statut'] != "Terminé") & (live['Numero'] > 0)].sort_values('Numero')
                if not active_view.empty:
                    st.markdown("### 🔥 EN COURS")
                    for idx, row in active_view.iterrows():
                        with st.container(border=True):
                            c_info, c_act = st.columns([3, 2])
                            c_info.markdown(f"### {row['Combattant']}")
                            with c_act:
                                if st.button("✅ GAGNÉ", key=f"win_{idx}"):
                                    live.at[idx, 'Statut'] = "Terminé"; live.at[idx, 'Palmares'] = "Victoire"; save_data(live, "Feuille 1", []); st.rerun()

        with subtab_admin:
            st.markdown("#### 1. Configuration")
            c1, c2 = st.columns(2)
            cal_opts = get_calendar_db()
            opts = cal_opts['Nom_Competition'].tolist() if not cal_opts.empty else ["Entraînement"]
            nom_c = c1.selectbox("Événement", opts)
            st.session_state['Config_Compet'] = nom_c
            
            # --- ROBOT AUTOMATIQUE ---
            st.write("---")
            st.markdown("#### 🤖 AUTOMATISATION (Robot Web)")
            
            with st.expander("Configurer le Robot"):
                st.info("Remplissez ceci UNE SEULE FOIS pour le site de la fédération.")
                col_url, col_log = st.columns(2)
                site_login_url = col_url.text_input("URL Page Connexion", "https://www.exemple-fede.fr/login")
                target_list_url = col_url.text_input("URL Page Liste Inscrits", "https://www.exemple-fede.fr/competitions/view/123")
                
                site_user = col_log.text_input("Identifiant", "votre_email")
                site_pass = col_log.text_input("Mot de passe", type="password")
                
                st.markdown("**Sélecteurs CSS (Avancé - Clic Droit 'Inspecter' sur le site)**")
                sel_id = st.text_input("Sélecteur Champ Identifiant (ex: #username)", "#username")
                sel_pass = st.text_input("Sélecteur Champ Mot de Passe (ex: #password)", "#password")
                sel_btn = st.text_input("Sélecteur Bouton Connexion (ex: button[type='submit'])", "button[type='submit']")
                
                if st.button("🚀 LANCER LE ROBOT RÉCUPÉRATEUR"):
                    ath_db = get_athletes_db()
                    if not ath_db.empty:
                        html_res, msg = run_robot_scraper(site_login_url, target_list_url, site_user, site_pass, sel_id, sel_pass, sel_btn)
                        
                        if html_res:
                            st.success("Connexion réussie ! Analyse du tableau...")
                            status, matches = parse_html_content(html_res, ath_db)
                            
                            if status == "SUCCESS" and matches:
                                st.success(f"✅ {len(matches)} athlètes trouvés !")
                                to_add_web = []
                                for m in matches:
                                    desc, nb = estimer_tours_detail(m['Nb_Poule'])
                                    to_add_web.append({
                                        "Compétition": nom_c, "Nom": m['Nom'], "Prénom": m['Prenom'],
                                        "Année Naissance": "", "Poids (kg)": "", "Sexe (M/F)": "",
                                        "Catégorie Calculée": f"{m['Categorie_Web']} ({desc})"
                                    })
                                st.session_state['inscr_df'] = pd.DataFrame(to_add_web)
                                st.success("Données chargées dans le tableau ci-dessous !")
                            else: st.error(f"Aucun match trouvé. {matches}")
                        else: st.error(msg)
                    else: st.error("Base Athlètes vide.")

            # (Reste du code Inscription/Tableau/Import identique aux versions précédentes...)
            # Je ne le remets pas pour ne pas saturer la réponse, mais le bloc '2. Inscriptions' 
            # avec st.data_editor et le bouton 'Importer' reste le même que la V43/44.
            
            st.write("---")
            # --- TABLEAU ET BOUTONS CLASSIQUES (COPIE V43/44) ---
            if 'inscr_df' not in st.session_state: st.session_state['inscr_df'] = pd.DataFrame(columns=["Compétition", "Nom", "Prénom", "Année Naissance", "Poids (kg)", "Sexe (M/F)", "Catégorie Calculée"])
            
            if st.button("📥 Importer vers le Live"):
                # (Logique import V43)
                if not st.session_state['inscr_df'].empty:
                    live_cur = get_live_data()
                    rows = []
                    for _, r in st.session_state['inscr_df'].iterrows():
                        rows.append({"Combattant": f"{r['Nom']} {r['Prénom']}", "Aire": 0, "Numero": 0, "Casque": "Rouge", "Statut": "A venir", "Palmares": "", "Details_Tour": r.get('Catégorie Calculée',''), "Medaille_Actuelle": ""})
                    save_data(pd.concat([live_cur, pd.DataFrame(rows)], ignore_index=True), "Feuille 1", []); st.success("Importé !"); st.rerun()

            st.data_editor(st.session_state['inscr_df'], num_rows="dynamic", use_container_width=True)

# 3 & 4
with tab_profil:
    st.header("Fiches"); h=get_history_data(); a=get_athletes_db(); n=set(h['Combattant']) if not h.empty else set(); 
    if not a.empty: 
        a['Full'] = a['Nom'] + " " + a['Prenom']
        n.update(a['Full'])
    if n: 
        s=st.selectbox("Nom", sorted(list(n))); 
        if not a.empty: 
            parts = s.split(); nm = " ".join(parts[:-1]); pm = parts[-1]
            i=a[(a['Nom']==nm) & (a['Prenom']==pm)]
            if not i.empty: st.markdown(f"**{i.iloc[0]['Titre_Honorifique']}**")
        if not h.empty:
            m=h[h['Combattant']==s].sort_values('Date', ascending=False)
            for _,r in m.iterrows(): st.write(f"{r['Medaille']} - {r['Competition']}")
with tab_historique: st.header("Palmarès"); h=get_history_data(); st.dataframe(h, use_container_width=True)
