import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import urllib.parse
import time

# --- CONFIGURATION & DESIGN ---
st.set_page_config(page_title="Fight Tracker V26", page_icon="🥊", layout="wide")

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
        .coach-info { font-size: 1.1em; font-weight: bold; }
        .coach-details { font-size: 0.9em; color: #aaa; }
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

def get_valid_competitions():
    df = get_calendar_db()
    valid = []
    if not df.empty and 'Date_Prevue' in df.columns:
        today = date.today()
        for i, row in df.iterrows():
            try:
                d = datetime.strptime(str(row['Date_Prevue']), "%Y-%m-%d").date()
                if d >= today: valid.append(row['Nom_Competition'])
            except: pass
    return valid if valid else ["Entraînement"]

def save_data(df, sheet_name, cols_def):
    ws = get_worksheet_safe(sheet_name, cols_def)
    if ws:
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.values.tolist())
        fetch_data.clear()

# --- FONCTION UNIQUE : ARCHIVAGE & QUALIF ---
def process_end_match(live_df, idx, resultat, nom_compet, date_compet, target_evt):
    # 1. Mise à jour statut Live
    live_df.at[idx, 'Statut'] = "Terminé"
    live_df.at[idx, 'Medaille_Actuelle'] = resultat
    live_df.at[idx, 'Palmares'] = resultat
    save_data(live_df, "Feuille 1", [])
    
    # 2. Archivage Historique
    nom_combattant = live_df.at[idx, 'Combattant']
    hist = get_history_data()
    new_entry = pd.DataFrame([{"Competition": nom_compet, "Date": str(date_compet), "Combattant": nom_combattant, "Medaille": resultat}])
    save_data(pd.concat([hist, new_entry], ignore_index=True), "Historique", ["Competition", "Date", "Combattant", "Medaille"])
    
    # 3. Qualification Auto
    if target_evt and resultat in ["🥇 Or", "🥈 Argent"]:
        ath = get_athletes_db()
        pre = get_preinscriptions_db()
        
        # Check doublon
        exists = False
        if not pre.empty:
            if not pre[(pre['Nom'] == nom_combattant) & (pre['Competition_Cible'] == target_evt)].empty: exists = True
        
        if not exists:
            # Récup info
            inf_row = ath[ath['Nom'] == nom_combattant]
            if not inf_row.empty:
                inf = inf_row.iloc[0]
                cat = calculer_categorie(inf['Annee_Naissance'], inf['Poids'], inf['Sexe'])
                new_q = pd.DataFrame([{"Competition_Cible": target_evt, "Nom": nom_combattant, "Annee": inf['Annee_Naissance'], "Poids": inf['Poids'], "Sexe": inf['Sexe'], "Categorie": cat}])
                save_data(pd.concat([pre, new_q], ignore_index=True), "PreInscriptions", [])
                st.toast(f"Qualifié pour {target_evt} !", icon="🚀")

# --- INTERFACE ---
tab_public, tab_coach, tab_profil, tab_historique = st.tabs(["📢 LIVE", "🛠️ COACH (PILOTAGE)", "👤 PROFILS", "🏛️ CLUB"])

# 1. LIVE
with tab_public:
    if st.button("Actualiser", key="ref_pub", use_container_width=True): st.rerun()
    df = get_live_data()
    df_ath = get_athletes_db()
    
    if not df.empty:
        df['Numero'] = pd.to_numeric(df['Numero'], errors='coerce').fillna(0)
        df['Aire'] = pd.to_numeric(df['Aire'], errors='coerce').fillna(0)
        # On trie : D'abord les "En cours", puis les "A venir", puis les "Terminé" à la fin
        df['Sort_Order'] = df['Statut'].map({"En cours": 0, "A venir": 1, "Terminé": 2}).fillna(3)
        df = df.sort_values(by=['Sort_Order', 'Numero', 'Aire'])
        
        st.markdown(f"<h2 style='text-align:center; color:#FFD700;'>{st.session_state.get('Config_Compet', 'Compétition')}</h2>", unsafe_allow_html=True)
        
        for i, row in df.iterrows():
            # Style Grisé si terminé
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
                    <div>
                        <span class="combat-num">CBT #{int(row['Numero'])}</span>
                        <span class="tour-info">{row['Details_Tour']}</span>
                    </div>
                    <span class="combat-aire">AIRE {int(row['Aire'])}</span>
                </div>
                <div class="fighter-line">
                    <div>
                        <span class="fighter-name">{row['Combattant']} {med_badge}</span>
                        <span class="honor-title">{titre}</span>
                    </div>
                </div>
                <div class="status-badge">{row['Statut']}</div>
            </div>
            """, unsafe_allow_html=True)
    else: st.info("Aucun combat.")

# 2. COACH (NOUVELLE INTERFACE)
with tab_coach:
    if st.text_input("Code", type="password") == "1234":
        
        # CONFIGURATION CACHÉE DANS UN EXPANDER POUR NE PAS GÊNER
        with st.expander("⚙️ Réglages Compétition (Nom, Qualif...)"):
            c1, c2 = st.columns(2)
            cal_opts = get_calendar_db()
            opts = cal_opts['Nom_Competition'].tolist() if not cal_opts.empty else ["Entraînement"]
            nom_c = c1.selectbox("Événement", opts)
            date_c = c2.date_input("Date", datetime.today())
            qualif = st.checkbox("Qualificatif ?")
            tgt = st.selectbox("Vers", opts) if qualif else None
            
            st.session_state['Config_Compet'] = nom_c
            
            if st.button("📥 Importer Inscrits"):
                pre = get_preinscriptions_db()
                sub = pre[pre['Competition_Cible'] == nom_c]
                if not sub.empty:
                    cur = get_live_data()
                    rows = []
                    for _, r in sub.iterrows():
                        if r['Nom'] and (cur.empty or r['Nom'] not in cur['Combattant'].values):
                            rows.append({"Combattant": r['Nom'], "Aire":0, "Numero":0, "Casque":"Rouge", "Statut":"A venir", "Palmares":"", "Details_Tour":"", "Medaille_Actuelle":""})
                    if rows: save_data(pd.concat([cur, pd.DataFrame(rows)], ignore_index=True), "Feuille 1", []); st.rerun()

        st.divider()
        st.subheader("⚡ Pilotage des Combats")
        
        live = get_live_data()
        if not live.empty:
            # On affiche seulement les non terminés pour le pilotage
            active_view = live[live['Statut'] != "Terminé"].sort_values('Numero')
            
            if active_view.empty:
                st.success("🎉 Tous les combats sont terminés ! Allez fêter ça.")
            
            for idx, row in active_view.iterrows():
                # --- LIGNE DE PILOTAGE PAR COMBATTANT ---
                with st.container(border=True):
                    c_info, c_win, c_loss = st.columns([3, 1, 1])
                    
                    with c_info:
                        st.markdown(f"### 🥊 {row['Combattant']}")
                        st.caption(f"Actuel : Combat #{row['Numero']} | Aire {row['Aire']} | {row['Details_Tour']}")
                    
                    # BOUTON VERT : VICTOIRE (POPOVER)
                    with c_win:
                        with st.popover("✅ VICTOIRE", use_container_width=True):
                            st.write("**Suite du parcours :**")
                            new_num = st.number_input("Prochain N°", value=int(row['Numero'])+1, key=f"n_{idx}")
                            new_aire = st.number_input("Nouvelle Aire", value=int(row['Aire']), key=f"a_{idx}")
                            new_tour = st.text_input("Nouveau Tour (ex: Finale)", key=f"t_{idx}")
                            
                            if st.button("Valider (Continue)", key=f"v_{idx}", type="primary"):
                                live.at[idx, 'Numero'] = new_num
                                live.at[idx, 'Aire'] = new_aire
                                live.at[idx, 'Details_Tour'] = new_tour
                                live.at[idx, 'Statut'] = "A venir"
                                save_data(live, "Feuille 1", [])
                                st.toast("Mise à jour OK")
                                st.rerun()
                            
                            st.divider()
                            st.write("**Ou C'était la Finale ?**")
                            if st.button("🏆 GAGNE LA FINALE (OR)", key=f"or_{idx}"):
                                process_end_match(live, idx, "🥇 Or", nom_c, date_c, tgt)
                                st.balloons()
                                st.rerun()

                    # BOUTON ROUGE : DÉFAITE (POPOVER)
                    with c_loss:
                        with st.popover("❌ DÉFAITE", use_container_width=True):
                            st.write("**Fin de parcours. Résultat ?**")
                            res = st.radio("Médaille / Rang", ["🥈 Argent", "🥉 Bronze", "🍫 4ème", "❌ Non classé"], key=f"r_{idx}")
                            
                            if st.button("Confirmer la fin", key=f"end_{idx}", type="primary"):
                                process_end_match(live, idx, res, nom_c, date_c, tgt)
                                st.rerun()
        else:
            st.info("Liste vide. Importez des inscrits via les réglages ci-dessus.")

        st.divider()
        if st.button("🗑️ Vider tout le Live (Reset)", type="primary"):
            save_data(pd.DataFrame(columns=live.columns), "Feuille 1", [])
            st.rerun()

# 3. PROFILS & 4. HISTORIQUE (Code inchangé, compacté)
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
