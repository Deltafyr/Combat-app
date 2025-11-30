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
st.set_page_config(page_title="Fight Tracker V55", page_icon="🥊", layout="wide")

st.markdown("""
    <style>
        html, body, [class*="css"]  { font-family: 'Roboto', sans-serif; font-size: 14px; }
        
        /* CARTE PUBLIC */
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
        
        /* STEPS DESIGN */
        .step-header {
            background-color: #262730;
            padding: 10px 15px;
            border-radius: 8px;
            border-left: 5px solid #FFD700;
            margin-top: 20px;
            margin-bottom: 10px;
            font-family: 'Oswald', sans-serif;
            font-size: 1.2em;
            color: white;
        }
        .step-number {
            background: #FFD700; color: black; 
            border-radius: 50%; width: 25px; height: 25px; 
            display: inline-block; text-align: center; margin-right: 10px;
        }
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Oswald:wght@400;600&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)

# --- CONNEXION ---
@st.cache_resource
def get_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# --- OUTILS ---
def clean_str(txt): return str(txt).strip().upper() if pd.notna(txt) else ""
def clean_prenom(txt): return str(txt).strip().title() if pd.notna(txt) else ""

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
        if n == 3: return "Poule (1-2 cbt)"
        if n == 4: return "Demi + Fin"
        if 5 <= n <= 8: return "Quart -> Fin"
        return "Tournoi 4+"
    except: return "?"

# --- PARSERS ---
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
                        "Infos_Tournoi": f"{row['Category']} ({txt_combats})",
                        "Aire_PDF": aire
                    })
            return pd.DataFrame(club_data)
    except Exception: return pd.DataFrame()

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
def get_calendar_db(): return fetch_data("Calendrier", ["Nom_Competition", "Date_Prevue", "Lieu", "Forclusion", "Source_Qualif"])
def get_preinscriptions_db(): return fetch_data("PreInscriptions", ["Competition_Cible", "Nom", "Prenom", "Annee", "Poids", "Sexe", "Categorie", "Statut_Convoc", "Aire_Prevue"])

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
        nom = clean_str(nom); prenom = clean_prenom(prenom)
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
        st.toast("Qualif auto gérée via l'onglet Config (Step 2)", icon="ℹ️")

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
                        n = clean_str(" ".join(parts[:-1])); p = clean_prenom(parts[-1])
                        info = df_ath[(df_ath['Nom'] == n) & (df_ath['Prenom'] == p)]
                        if not info.empty: titre = info.iloc[0]['Titre_Honorifique']
                med_badge = f"🏅 {row['Medaille_Actuelle']}" if row['Medaille_Actuelle'] else ""
                corner_span = "<span class='corner-red'>Rouge</span>" if row['Casque'] == "Rouge" else "<span class='corner-blue'>Bleu</span>"
                st.markdown(f"""
                <div class="{css_class}" style="border-left: 4px solid {border};">
                    <div class="header-line">
                        <div><span class="combat-num">CBT #{int(row['Numero'])}</span><span class="tour-info">{row['Details_Tour']}</span></div>
                        <span class="combat-aire">AIRE {int(row['Aire'])}</span>
                    </div>
                    <div class="fighter-line">
                        <div>{corner_span}<span class="fighter-name">{row['Combattant']} {med_badge}</span><span class="honor-title">{titre}</span></div>
                    </div>
                    <div class="status-badge">{row['Statut']}</div>
                </div>""", unsafe_allow_html=True)
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
                # DISPATCH
                waiting_list = live[(live['Statut'] != "Terminé") & (live['Numero'] == 0)]
                if not waiting_list.empty:
                    st.markdown("### ⚠️ À PROGRAMMER (Tirage)")
                    st.markdown('<div class="dispatch-box">', unsafe_allow_html=True)
                    for idx, row in waiting_list.iterrows():
                        c_nom, c_aire, c_num, c_casque, c_btn = st.columns([2, 1, 1, 2, 1])
                        with c_nom:
                            st.markdown(f"**🥊 {row['Combattant']}**")
                            if row.get('Details_Tour'): st.caption(f"{row['Details_Tour']}")
                        
                        def_aire = 1
                        if 'Aire_PDF' in st.session_state and row['Combattant'] in st.session_state['Aire_PDF']:
                             def_aire = st.session_state['Aire_PDF'][row['Combattant']]
                        
                        na = c_aire.number_input("Aire", value=int(def_aire), min_value=1, key=f"wa_{idx}", label_visibility="collapsed")
                        nn = c_num.number_input("N°", value=1, min_value=1, key=f"wn_{idx}", label_visibility="collapsed")
                        nc = c_casque.radio("Casque", ["Rouge", "Bleu"], horizontal=True, key=f"wc_{idx}", label_visibility="collapsed")
                        
                        if c_btn.button("Go", key=f"wb_{idx}", type="primary"):
                            live.at[idx, 'Aire'] = na; live.at[idx, 'Numero'] = nn; live.at[idx, 'Casque'] = nc
                            save_data(live, "Feuille 1", []); st.rerun()
                        st.markdown("---")
                    st.markdown('</div>', unsafe_allow_html=True)

                # PILOTAGE
                active_view = live[(live['Statut'] != "Terminé") & (live['Numero'] > 0)].sort_values('Numero')
                if not active_view.empty:
                    st.markdown("### 🔥 EN COURS")
                    for idx, row in active_view.iterrows():
                        with st.container(border=True):
                            color_name = "#FF4B4B" if row['Casque'] == "Rouge" else "#2196F3"
                            c_info, c_win, c_loss = st.columns([3, 1, 1])
                            with c_info:
                                st.markdown(f"### <span style='color:{color_name}'>■</span> {row['Combattant']}", unsafe_allow_html=True)
                                st.caption(f"#{int(row['Numero'])} | Aire {int(row['Aire'])} | {row['Details_Tour']}")
                            with c_win:
                                with st.popover("✅ GAGNÉ", use_container_width=True):
                                    nn = st.number_input("N°", value=int(row['Numero'])+1, key=f"n{idx}")
                                    na = st.number_input("Aire", value=int(row['Aire']), key=f"a{idx}")
                                    nt = st.text_input("Tour", key=f"t{idx}")
                                    nc = st.radio("Casque", ["Rouge", "Bleu"], key=f"nc{idx}")
                                    if st.button("Continuer", key=f"v{idx}", type="primary"):
                                        live.at[idx, 'Numero'] = nn; live.at[idx, 'Aire'] = na
                                        live.at[idx, 'Details_Tour'] = nt; live.at[idx, 'Casque'] = nc
                                        live.at[idx, 'Statut'] = "A venir"
                                        save_data(live, "Feuille 1", []); st.rerun()
                                    st.divider()
                                    if st.button("🏆 OR (FINALE)", key=f"or{idx}"):
                                        process_end_match(live, idx, "🥇 Or", st.session_state.get('Config_Compet'), datetime.today(), st.session_state.get('Target_Compet'))
                                        st.rerun()
                            with c_loss:
                                with st.popover("❌ DÉFAITE", use_container_width=True):
                                    res = st.radio("Résultat", ["🥈 Argent", "🥉 Bronze", "🍫 4ème", "❌ Non classé"], key=f"r{idx}")
                                    if st.button("Terminer", key=f"e{idx}", type="primary"):
                                        process_end_match(live, idx, res, st.session_state.get('Config_Compet'), datetime.today(), st.session_state.get('Target_Compet'))
                                        st.rerun()
            else: st.info("Vide. Importez des inscrits.")

        with subtab_admin:
            
            # --- STEP 1 : CREATION / SELECTION ---
            st.markdown("<div class='step-header'><span class='step-number'>1</span> CRÉATION & CONFIGURATION</div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            
            cal_opts = get_calendar_db()
            list_opts = cal_opts['Nom_Competition'].tolist() if not cal_opts.empty else ["Entraînement"]
            
            with c1:
                nom_c = st.selectbox("Sélectionner Compétition", list_opts)
                
                # Récup info si existe
                selected_info = cal_opts[cal_opts['Nom_Competition'] == nom_c]
                source_qualif = None
                if not selected_info.empty and 'Source_Qualif' in selected_info.columns:
                    source_qualif = selected_info.iloc[0]['Source_Qualif']

            with c2:
                with st.expander("➕ Nouvelle / Modifier"):
                    new_n = st.text_input("Nom Compétition", value=nom_c)
                    new_d = st.date_input("Date", datetime.today())
                    new_l = st.text_input("Lieu")
                    new_f = st.date_input("Forclusion (Date limite)")
                    new_s = st.selectbox("Provient de (Qualification)", ["Aucune"] + list_opts)
                    
                    if st.button("Sauvegarder Paramètres"):
                        # Update ou Insert
                        new_row = pd.DataFrame([{
                            "Nom_Competition": new_n, "Date_Prevue": str(new_d),
                            "Lieu": new_l, "Forclusion": str(new_f),
                            "Source_Qualif": new_s if new_s != "Aucune" else ""
                        }])
                        # Logique simple : on ajoute à la fin (historisation)
                        save_data(pd.concat([cal_opts, new_row], ignore_index=True), "Calendrier", ["Nom_Competition", "Date_Prevue", "Lieu", "Forclusion", "Source_Qualif"])
                        st.success("Enregistré !")
                        st.rerun()

            st.session_state['Config_Compet'] = nom_c
            
            # --- STEP 2 : POPULATION (PRÉ-INSCRIPTION) ---
            st.markdown("<div class='step-header'><span class='step-number'>2</span> PRÉ-INSCRIPTIONS</div>", unsafe_allow_html=True)
            
            # Initialisation session DF
            if 'inscr_df' not in st.session_state: 
                st.session_state['inscr_df'] = pd.DataFrame(columns=["Compétition", "Nom", "Prénom", "Année Naissance", "Poids (kg)", "Sexe (M/F)", "Catégorie Calculée", "Statut_Convoc", "Aire_Prevue"])

            c_add1, c_add2 = st.columns(2)
            with c_add1:
                # OPTION A : Charger depuis Base Athlètes
                db_ath = get_athletes_db()
                if not db_ath.empty:
                    db_ath['Full'] = db_ath['Nom'] + " " + db_ath['Prenom']
                    sel_ath = st.multiselect("Ajouter Membres du Club", db_ath['Full'].unique())
                    if st.button("Ajouter Sélection"):
                        to_add = []
                        for full in sel_ath:
                            info = db_ath[db_ath['Full'] == full].iloc[0]
                            cat = calculer_categorie(info['Annee_Naissance'], info['Poids'], info['Sexe'])
                            to_add.append({"Compétition": nom_c, "Nom": info['Nom'], "Prénom": info['Prenom'], "Année Naissance": info['Annee_Naissance'], "Poids (kg)": info['Poids'], "Sexe (M/F)": info['Sexe'], "Catégorie Calculée": cat, "Statut_Convoc": "Pré-inscrit"})
                        st.session_state['inscr_df'] = pd.concat([st.session_state['inscr_df'], pd.DataFrame(to_add)], ignore_index=True)
            
            with c_add2:
                # OPTION B : Import Qualifiés (Auto)
                if source_qualif:
                    st.info(f"Cette compétition est liée à : {source_qualif}")
                    if st.button(f"Importer les qualifiés de {source_qualif}"):
                        hist = get_history_data()
                        winners = hist[(hist['Competition'] == source_qualif) & (hist['Medaille'].isin(['🥇 Or', '🥈 Argent']))]
                        if not winners.empty:
                            to_add = []
                            for _, w in winners.iterrows():
                                # Retrouver infos
                                parts = w['Combattant'].split()
                                n, p = clean_str(" ".join(parts[:-1])), clean_prenom(parts[-1])
                                # Chercher dans base
                                match = db_ath[(db_ath['Nom'] == n) & (db_ath['Prenom'] == p)]
                                if not match.empty:
                                    info = match.iloc[0]
                                    cat = calculer_categorie(info['Annee_Naissance'], info['Poids'], info['Sexe'])
                                    to_add.append({"Compétition": nom_c, "Nom": n, "Prénom": p, "Année Naissance": info['Annee_Naissance'], "Poids (kg)": info['Poids'], "Sexe (M/F)": info['Sexe'], "Catégorie Calculée": cat, "Statut_Convoc": "Qualifié Auto"})
                            st.session_state['inscr_df'] = pd.concat([st.session_state['inscr_df'], pd.DataFrame(to_add)], ignore_index=True)
                            st.success(f"{len(to_add)} qualifiés ajoutés !")
                        else: st.warning("Pas de médaillés trouvés.")
                else:
                    st.caption("Pas de compétition source liée.")

            # Tableau éditable des inscrits
            edited = st.data_editor(
                st.session_state['inscr_df'], 
                num_rows="dynamic", 
                column_config={
                    "Compétition": st.column_config.Column(disabled=True),
                    "Statut_Convoc": st.column_config.SelectboxColumn(options=["Pré-inscrit", "Qualifié Auto", "Convoqué", "Pesée OK", "Forfait"]),
                    "Aire_Prevue": st.column_config.NumberColumn("Aire (Prev)")
                },
                use_container_width=True
            )
            st.session_state['inscr_df'] = edited
            
            if st.button("💾 Sauvegarder Pré-inscriptions"):
                pre = get_preinscriptions_db()
                # Mapping
                to_save = edited.rename(columns={"Compétition": "Competition_Cible", "Nom": "Nom", "Prénom": "Prenom", "Année Naissance": "Annee", "Poids (kg)": "Poids", "Sexe (M/F)": "Sexe", "Catégorie Calculée": "Categorie", "Statut_Convoc": "Statut_Convoc", "Aire_Prevue": "Aire_Prevue"})
                # Filter only current compet from DB to replace them or append
                # Simple strategy: Append new ones, user handles duplicates manually in editor
                # Better: Filter out current compet from DB and append new list
                other_compets = pre[pre['Competition_Cible'] != nom_c]
                final_db = pd.concat([other_compets, to_save[["Competition_Cible", "Nom", "Prenom", "Annee", "Poids", "Sexe", "Categorie", "Statut_Convoc", "Aire_Prevue"]]], ignore_index=True)
                save_data(final_db, "PreInscriptions", [])
                st.success("Liste enregistrée !")

            # --- STEP 3 : VALIDATION (CONVOCATION PDF) ---
            st.markdown("<div class='step-header'><span class='step-number'>3</span> CONVOCATIONS & VALIDATION</div>", unsafe_allow_html=True)
            
            pdf_file = st.file_uploader("Vérifier avec le PDF Convocations", type="pdf")
            if pdf_file:
                club_key = st.text_input("Mot clé Club", value="SAINT MAURICE")
                if st.button("🔍 Analyser et Mettre à jour les statuts"):
                    pdf_data = parse_pdf_ffkmda(pdf_file, club_key)
                    if not pdf_data.empty:
                        # Mise à jour du tableau Inscriptions
                        current_df = st.session_state['inscr_df']
                        count_upd = 0
                        for _, p_row in pdf_data.iterrows():
                            # Match sur Nom Prénom
                            mask = (current_df['Nom'] == p_row['Nom']) & (current_df['Prénom'] == p_row['Prénom'])
                            if mask.any():
                                # Update existant
                                idx = current_df[mask].index[0]
                                current_df.at[idx, 'Statut_Convoc'] = "Convoqué"
                                current_df.at[idx, 'Catégorie Calculée'] = p_row['Catégorie Calculée']
                                current_df.at[idx, 'Aire_Prevue'] = p_row['Aire_PDF']
                                count_upd += 1
                            else:
                                # Ajout nouveau (trouvé dans PDF mais pas dans pré-inscr)
                                new_r = {
                                    "Compétition": nom_c, "Nom": p_row['Nom'], "Prénom": p_row['Prénom'],
                                    "Catégorie Calculée": p_row['Catégorie Calculée'],
                                    "Aire_Prevue": p_row['Aire_PDF'],
                                    "Statut_Convoc": "Convoqué (PDF)"
                                }
                                current_df = pd.concat([current_df, pd.DataFrame([new_r])], ignore_index=True)
                        
                        st.session_state['inscr_df'] = current_df
                        st.success(f"{count_upd} athlètes confirmés par le PDF !")
                        st.rerun()

            # --- STEP 4 : OUTPUT (TABLEAU FINAL) ---
            st.markdown("<div class='step-header'><span class='step-number'>4</span> TABLEAU RÉCAPITULATIF</div>", unsafe_allow_html=True)
            
            # On affiche le tableau propre des "Convoqués" ou "Confirmés"
            final_view = st.session_state['inscr_df']
            if not final_view.empty:
                # Filtre optionnel
                show_all = st.checkbox("Afficher tout le monde (même non convoqués)")
                if not show_all:
                    final_view = final_view[final_view['Statut_Convoc'].str.contains("Convoqué|Pesée", na=False, case=False)]
                
                st.dataframe(final_view[["Nom", "Prénom", "Catégorie Calculée", "Aire_Prevue", "Statut_Convoc"]], use_container_width=True)
                
                # Generation texte WhatsApp
                txt = f"📋 *RÉCAPITULATIF {nom_c}*\n"
                for _, r in final_view.iterrows():
                    txt += f"🥊 {r['Nom']} {r['Prénom']} | {r['Catégorie Calculée']} | Aire {r.get('Aire_Prevue','?')}\n"
                
                st.link_button("📲 Envoyer Récap WhatsApp", f"https://wa.me/?text={urllib.parse.quote(txt)}")
                
                if st.button("🚀 ENVOYER VERS LE LIVE (JOUR J)", type="primary"):
                    cur_live = get_live_data()
                    rows = []
                    st.session_state['Aire_PDF'] = {}
                    for _, r in final_view.iterrows():
                        nom_cpl = f"{r['Nom']} {r['Prénom']}".strip()
                        if 'Aire_Prevue' in r and r['Aire_Prevue']: st.session_state['Aire_PDF'][nom_cpl] = int(r['Aire_Prevue'])
                        
                        if nom_cpl and (cur_live.empty or nom_cpl not in cur_live['Combattant'].values):
                             rows.append({"Combattant": nom_cpl, "Aire":0, "Numero":0, "Casque":"Rouge", "Statut":"A venir", "Palmares":"", "Details_Tour": r.get('Catégorie Calculée', ''), "Medaille_Actuelle":""})
                    
                    if rows: 
                        save_data(pd.concat([cur_live, pd.DataFrame(rows)], ignore_index=True), "Feuille 1", [])
                        st.balloons()
                        st.success("Prêt pour le combat !")
            else:
                st.info("Aucun athlète dans la liste.")

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
