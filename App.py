import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import urllib.parse
import time

# --- CONFIGURATION & DESIGN ---
st.set_page_config(page_title="Fight Tracker V27", page_icon="🥊", layout="wide")

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
        .tour-info { font-size: 0.85em; color: #aaa; margin-left: 5px; }
        .combat-aire { background: #FFD700; color:black; padding: 2px 8px; border-radius: 10px; font-size: 0.85em; font-weight: bold; }
        
        .fighter-name { font-size: 1.3em; font-weight: 700; color: #fff; }
        .honor-title { font-size: 0.8em; color: #FFD700; font-style: italic; display:block; opacity:0.8;}
        
        /* DESIGN COACH */
        .coach-row {
            background-color: #262730;
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 8px;
            border: 1px solid #444;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
    </style>
""", unsafe_allow_html=True)

# --- CONNEXION ---
@st.cache_resource
def get_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# --- LOGIQUE MÉTIER ---
def calculer_categorie(annee, poids, sexe):
    try:
        if not annee or not poids: return "Incomplet"
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
    try: ws = sh.worksheet(name)
    except: ws = sh.add_worksheet(name, 1000, len(cols)+2); ws.append_row(cols); time.sleep(1)
    return ws

@st.cache_data(ttl=5)
def fetch_data(sheet_name, cols):
    ws = get_worksheet_safe(sheet_name, cols)
    if ws:
        try: return pd.DataFrame(ws.get_all_records())
        except: return pd.DataFrame(columns=cols)
    return pd.DataFrame(columns=cols)

def get_live_data(): return fetch_data("Feuille 1", ["Combattant", "Aire", "Numero", "Casque", "Statut", "Palmares", "Details_Tour", "Medaille_Actuelle"])
def get_history_data(): return fetch_data("Historique", ["Competition", "Date", "Combattant", "Medaille"])
def get_athletes_db(): return fetch_data("Athletes", ["Nom", "Titre_Honorifique", "Annee_Naissance", "Poids", "Sexe"])
def get_calendar_db(): return fetch_data("Calendrier", ["Nom_Competition", "Date_Prevue"])
def get_preinscriptions_db(): return fetch_data("PreInscriptions", ["Competition_Cible", "Nom", "Annee", "Poids", "Sexe", "Categorie"])

def save_data(df, sheet_name, cols_def):
    ws = get_worksheet_safe(sheet_name, cols_def)
    if ws:
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.values.tolist())
        fetch_data.clear()

def process_end_match(live_df, idx, resultat, nom_compet, date_compet, target_evt):
    # 1. Update Live
    live_df.at[idx, 'Statut'] = "Terminé"
    live_df.at[idx, 'Medaille_Actuelle'] = resultat
    live_df.at[idx, 'Palmares'] = resultat
    save_data(live_df, "Feuille 1", [])
    
    # 2. Archive History
    nom_combattant = live_df.at[idx, 'Combattant']
    hist = get_history_data()
    new_entry = pd.DataFrame([{"Competition": nom_compet, "Date": str(date_compet), "Combattant": nom_combattant, "Medaille": resultat}])
    save_data(pd.concat([hist, new_entry], ignore_index=True), "Historique", ["Competition", "Date", "Combattant", "Medaille"])
    
    # 3. Auto Qualif
    if target_evt and resultat in ["🥇 Or", "🥈 Argent"]:
        ath = get_athletes_db()
        pre = get_preinscriptions_db()
        exists = False
        if not pre.empty:
            if not pre[(pre['Nom'] == nom_combattant) & (pre['Competition_Cible'] == target_evt)].empty: exists = True
        
        if not exists:
            inf_row = ath[ath['Nom'] == nom_combattant]
            if not inf_row.empty:
                inf = inf_row.iloc[0]
                cat = calculer_categorie(inf['Annee_Naissance'], inf['Poids'], inf['Sexe'])
                new_q = pd.DataFrame([{"Competition_Cible": target_evt, "Nom": nom_combattant, "Annee": inf['Annee_Naissance'], "Poids": inf['Poids'], "Sexe": inf['Sexe'], "Categorie": cat}])
                save_data(pd.concat([pre, new_q], ignore_index=True), "PreInscriptions", [])
                st.toast(f"Qualifié pour {target_evt} !", icon="🚀")

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
        df['Sort_Order'] = df['Statut'].map({"En cours": 0, "A venir": 1, "Terminé": 2}).fillna(3)
        df = df.sort_values(by=['Sort_Order', 'Numero', 'Aire'])
        
        st.markdown(f"<h2 style='text-align:center; color:#FFD700;'>{st.session_state.get('Config_Compet', 'Compétition en cours')}</h2>", unsafe_allow_html=True)
        
        for i, row in df.iterrows():
            css_class = "combat-card"
            if row['Statut'] == "Terminé": css_class += " card-termine"
            border = "#FF4B4B" if "En cours" in row['Statut'] else "#444"
            if row['Statut'] == "Terminé": border = "#222"
            
            titre = ""
            if not df_ath.empty and 'Nom' in df_ath.columns:
                info = df_ath[df_ath['Nom'] == row['Combattant']]
                if not info.empty: titre = info.iloc[0]['Titre_Honorifique']
            
            med_badge = f"🏅 {row['Medaille_Actuelle']}" if row['Medaille_Actuelle'] else ""

            st.markdown(f"""
            <div class="{css_class}" style="border-left: 4px solid {border};">
                <div class="header-line">
                    <div><span class="combat-num">CBT #{int(row['Numero'])}</span><span class="tour-info">{row['Details_Tour']}</span></div>
                    <span class="combat-aire">AIRE {int(row['Aire'])}</span>
                </div>
                <div class="fighter-line">
                    <div style="width:100%;">
                        <span class="fighter-name" style="color:{'#FF4B4B' if row['Casque'] == 'Rouge' else '#2196F3'}">{row['Combattant']} {med_badge}</span>
                        <span class="honor-title">{titre}</span>
                    </div>
                </div>
                <div class="status-badge">{row['Statut']}</div>
            </div>
            """, unsafe_allow_html=True)
    else: st.info("Aucun combat.")

# 2. COACH (DIVISÉ EN 2 SOUS-ONGLETS)
with tab_coach:
    if st.text_input("Code", type="password") == "1234":
        
        # SOUS-ONGLETS POUR ORGANISATION
        subtab_pilotage, subtab_admin = st.tabs(["⚡ PILOTAGE LIVE", "⚙️ CONFIG & ADMIN"])
        
        # --- A. PILOTAGE (ACTION) ---
        with subtab_pilotage:
            st.caption(f"Événement : **{st.session_state.get('Config_Compet', 'Non Défini')}**")
            
            live = get_live_data()
            active_view = live[live['Statut'] != "Terminé"].sort_values('Numero') if not live.empty else pd.DataFrame()
            
            if not active_view.empty:
                for idx, row in active_view.iterrows():
                    with st.container(border=True):
                        c_info, c_win, c_loss = st.columns([3, 1, 1])
                        with c_info:
                            st.markdown(f"### 🥊 {row['Combattant']}")
                            st.caption(f"#{row['Numero']} | Aire {row['Aire']} | {row['Details_Tour']}")
                        
                        with c_win:
                            with st.popover("✅ VICTOIRE", use_container_width=True):
                                st.write("Suite du parcours :")
                                nn = st.number_input("N°", value=int(row['Numero'])+1, key=f"n{idx}")
                                na = st.number_input("Aire", value=int(row['Aire']), key=f"a{idx}")
                                nt = st.text_input("Tour", key=f"t{idx}")
                                if st.button("Valider", key=f"v{idx}", type="primary"):
                                    live.at[idx, 'Numero'] = nn; live.at[idx, 'Aire'] = na; live.at[idx, 'Details_Tour'] = nt
                                    live.at[idx, 'Statut'] = "A venir"
                                    save_data(live, "Feuille 1", []); st.rerun()
                                st.divider()
                                if st.button("🏆 FINALE (OR)", key=f"or{idx}"):
                                    process_end_match(live, idx, "🥇 Or", st.session_state.get('Config_Compet'), datetime.today(), st.session_state.get('Target_Compet'))
                                    st.rerun()
                        
                        with c_loss:
                            with st.popover("❌ DÉFAITE", use_container_width=True):
                                res = st.radio("Résultat", ["🥈 Argent", "🥉 Bronze", "🍫 4ème", "❌ Non classé"], key=f"r{idx}")
                                if st.button("Terminer", key=f"e{idx}", type="primary"):
                                    process_end_match(live, idx, res, st.session_state.get('Config_Compet'), datetime.today(), st.session_state.get('Target_Compet'))
                                    st.rerun()
            else:
                st.info("Aucun combat en cours. Allez dans 'Config & Admin' pour importer des inscrits.")

        # --- B. CONFIG & ADMIN (PRÉPARATION) ---
        with subtab_admin:
            
            # 1. CONFIGURATION LIVE
            st.markdown("#### 1. Configuration du Jour")
            c1, c2 = st.columns(2)
            cal_opts = get_calendar_db()
            opts = cal_opts['Nom_Competition'].tolist() if not cal_opts.empty else ["Entraînement"]
            nom_c = c1.selectbox("Événement du Jour", opts)
            qualif = st.checkbox("Qualificatif ?")
            tgt = st.selectbox("Vers", opts) if qualif else None
            
            st.session_state['Config_Compet'] = nom_c
            st.session_state['Target_Compet'] = tgt
            
            if st.button("📥 Importer la liste des Inscrits vers le Live"):
                pre = get_preinscriptions_db()
                sub = pre[pre['Competition_Cible'] == nom_c]
                if not sub.empty:
                    cur = get_live_data()
                    rows = []
                    for _, r in sub.iterrows():
                        if r['Nom'] and (cur.empty or r['Nom'] not in cur['Combattant'].values):
                            rows.append({"Combattant": r['Nom'], "Aire":0, "Numero":0, "Casque":"Rouge", "Statut":"A venir", "Palmares":"", "Details_Tour":"", "Medaille_Actuelle":""})
                    if rows: save_data(pd.concat([cur, pd.DataFrame(rows)], ignore_index=True), "Feuille 1", []); st.success("Importé !"); st.rerun()
                else: st.warning("Aucun inscrit trouvé pour cet événement.")
            
            st.write("---")
            
            # 2. CALENDRIER & INSCRIPTIONS
            with st.expander("📅 Gestion Calendrier & Inscriptions Futures"):
                st.markdown("**Ajouter une date au calendrier :**")
                cc1, cc2, cc3 = st.columns([3, 2, 1])
                n_cal = cc1.text_input("Nom Compétition")
                d_cal = cc2.date_input("Date Prévue")
                if cc3.button("Ajouter Date"):
                    cal = get_calendar_db()
                    save_data(pd.concat([cal, pd.DataFrame([{"Nom_Competition": n_cal, "Date_Prevue": str(d_cal)}])], ignore_index=True), "Calendrier", [])
                    st.rerun()
                
                st.markdown("**Préparer les inscriptions :**")
                if 'inscr_df' not in st.session_state: st.session_state['inscr_df'] = pd.DataFrame(columns=["Compétition", "Nom Complet", "Année Naissance", "Poids (kg)", "Sexe (M/F)", "Catégorie Calculée"])
                
                ed_i = st.data_editor(st.session_state['inscr_df'], num_rows="dynamic", column_config={
                    "Compétition": st.column_config.SelectboxColumn(options=opts, required=True),
                    "Sexe (M/F)": st.column_config.SelectboxColumn(options=["M", "F"])
                }, use_container_width=True)
                
                ci1, ci2 = st.columns(2)
                if ci1.button("Calculer Catégories"):
                    for i, r in ed_i.iterrows():
                        ed_i.at[i, "Catégorie Calculée"] = calculer_categorie(r["Année Naissance"], r["Poids (kg)"], r.get("Sexe (M/F)", "M"))
                    st.session_state['inscr_df'] = ed_i; st.rerun()
                
                if ci2.button("💾 Sauvegarder Inscriptions"):
                    pre = get_preinscriptions_db()
                    to_save = ed_i.rename(columns={"Compétition": "Competition_Cible", "Nom Complet": "Nom", "Année Naissance": "Annee", "Poids (kg)": "Poids", "Sexe (M/F)": "Sexe", "Catégorie Calculée": "Categorie"})
                    save_data(pd.concat([pre, to_save], ignore_index=True), "PreInscriptions", [])
                    st.success("Sauvegardé")

            st.write("---")
            if st.button("🗑️ Vider entièrement le Live (Reset)", type="primary"):
                save_data(pd.DataFrame(columns=live.columns), "Feuille 1", [])
                st.rerun()

# 3. PROFILS & 4. HISTORIQUE (Code inchangé)
with tab_profil:
    st.header("Fiches"); hist = get_history_data(); ath = get_athletes_db()
    names = set(hist['Combattant']) if not hist.empty else set()
    if not ath.empty: names.update(ath['Nom'])
    if names:
        s = st.selectbox("Rechercher", sorted(list(names)))
        if not ath.empty: 
            i = ath[ath['Nom'] == s]
            if not i.empty: st.markdown(f"**{i.iloc[0]['Titre_Honorifique']}**")
        if not hist.empty:
            m = hist[hist['Combattant'] == s]
            for _, r in m.iterrows(): st.write(f"{r['Medaille']} - {r['Competition']}")

with tab_historique:
    st.header("Palmarès"); h = get_history_data()
    if not h.empty: st.dataframe(h, use_container_width=True)
