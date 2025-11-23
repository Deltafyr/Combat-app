import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import urllib.parse

# --- CONFIGURATION & DESIGN SYSTEM (CSS AVANCÉ) ---
st.set_page_config(page_title="Fight Tracker Pro", page_icon="🥊", layout="wide")

st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Oswald:wght@300;500;700&family=Roboto:wght@300;400;700&display=swap" rel="stylesheet">

    <style>
        /* --- GLOBAL THEME --- */
        html, body, [class*="css"] {
            font-family: 'Roboto', sans-serif;
            background-color: #0E1117;
            color: #FAFAFA;
        }
        
        /* TITRES EN POLICE 'OSWALD' */
        h1, h2, h3, .combat-num, .fighter-name {
            font-family: 'Oswald', sans-serif;
            letter-spacing: 1px;
            text-transform: uppercase;
        }

        /* --- STYLISATION DES BOUTONS --- */
        .stButton > button {
            border-radius: 20px;
            font-weight: 600;
            border: none;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(255, 75, 75, 0.4);
        }
        /* Bouton Primaire (Rouge Streamlit) customisé */
        div[data-testid="stMarkdownContainer"] p {
            font-size: 1.05rem;
        }

        /* --- CARTES DE COMBAT (CARD UI) --- */
        .combat-card {
            background: linear-gradient(145deg, #1A1C24, #22252E);
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            border-left: 5px solid #444;
            position: relative;
            overflow: hidden;
            transition: transform 0.2s;
        }
        .combat-card:hover {
            transform: scale(1.01);
        }
        
        /* STATUS COLORS (Bordures) */
        .status-en-cours { border-left-color: #FF4B4B !important; box-shadow: 0 0 15px rgba(255, 75, 75, 0.15); }
        .status-prochain { border-left-color: #00C853 !important; }
        .status-termine { border-left-color: #555 !important; opacity: 0.7; }

        /* CONTENU CARTE */
        .header-line { 
            display: flex; 
            justify-content: space-between; 
            align-items: flex-start;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 8px;
            margin-bottom: 8px;
        }
        
        .combat-num { 
            font-size: 1.4em; 
            font-weight: 700; 
            color: #EEE;
        }
        .tour-badge {
            font-family: 'Roboto', sans-serif;
            font-size: 0.7em;
            background: rgba(255,255,255,0.1);
            padding: 2px 6px;
            border-radius: 4px;
            margin-left: 8px;
            color: #AAA;
            vertical-align: middle;
            text-transform: none;
        }

        .combat-aire { 
            background: #FFD700; 
            color: #000;
            padding: 4px 10px; 
            border-radius: 20px; 
            font-size: 0.9em; 
            font-weight: bold; 
            font-family: 'Roboto', sans-serif;
            box-shadow: 0 2px 5px rgba(0,0,0,0.5);
        }

        .fighter-line { 
            display: flex; 
            align-items: center;
            justify-content: space-between;
        }
        
        .fighter-name { 
            font-size: 1.6em; 
            font-weight: 500; 
            color: #FFF;
            margin-bottom: 0;
        }
        
        .honor-title { 
            font-family: 'Roboto', sans-serif;
            font-size: 0.85em; 
            color: #FFD700; 
            font-style: italic; 
            opacity: 0.8;
        }

        .corner-indicator {
            font-size: 0.8em;
            text-transform: uppercase;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 4px;
            margin-right: 8px;
        }
        .corner-red { color: #FF4B4B; border: 1px solid #FF4B4B; }
        .corner-blue { color: #2196F3; border: 1px solid #2196F3; }

        .medal-pill { 
            display: inline-block; 
            padding: 4px 10px; 
            border-radius: 20px; 
            font-size: 0.9em; 
            font-weight: bold;
            margin-right: 5px; 
            margin-bottom: 5px; 
            color: #1a1a1a;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        .gold { background: linear-gradient(45deg, #FFD700, #FFC107); } 
        .silver { background: linear-gradient(45deg, #E0E0E0, #BDBDBD); } 
        .bronze { background: linear-gradient(45deg, #CD7F32, #A1887F); }
        
        /* Séparateurs plus stylés */
        hr { border-color: #333; }
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
    except: ws = sh.add_worksheet(name, 1000, len(cols)+2); ws.append_row(cols)
    return ws

def get_data(name, cols):
    ws = get_worksheet_safe(name, cols)
    return pd.DataFrame(ws.get_all_records()) if ws else pd.DataFrame()

def save_data(df, name):
    ws = get_worksheet_safe(name, [])
    if ws: ws.clear(); ws.update([df.columns.values.tolist()] + df.values.tolist())

# --- INTERFACE ---
tab_public, tab_profil, tab_historique, tab_coach = st.tabs(["📢 LIVE", "👤 PROFILS", "🏛️ CLUB", "🛠️ COACH"])

# 1. LIVE DESIGN
with tab_public:
    # Header dynamique
    titre = st.session_state.get('Config_Compet', 'Compétition en cours')
    st.markdown(f"<h1 style='text-align: center; margin-bottom: 20px;'>{titre}</h1>", unsafe_allow_html=True)
    
    if st.button("Actualiser le Live", key="ref_pub", use_container_width=True): st.rerun()
    
    try:
        df = get_data("Feuille 1", [])
        df_ath = get_data("Athletes", [])
        
        if not df.empty:
            df['Numero'] = pd.to_numeric(df['Numero'], errors='coerce').fillna(0)
            df['Aire'] = pd.to_numeric(df['Aire'], errors='coerce').fillna(0)
            df = df[df['Numero'] > 0].sort_values(by=['Numero', 'Aire'])
            
            for i, row in df.iterrows():
                if row['Statut'] != "Terminé":
                    # Calcul des classes CSS
                    status_class = "status-en-cours" if "En cours" in row['Statut'] else "status-prochain"
                    corner_html = '<span class="corner-indicator corner-red">Rouge</span>' if row['Casque'] == "Rouge" else '<span class="corner-indicator corner-blue">Bleu</span>'
                    
                    # Titre honorifique
                    titre = ""
                    if not df_ath.empty and 'Nom' in df_ath.columns:
                        info = df_ath[df_ath['Nom'] == row['Combattant']]
                        if not info.empty: titre = info.iloc[0]['Titre_Honorifique']
                    
                    # Médaille actuelle
                    med = row['Medaille_Actuelle']
                    med_html = f'<span class="medal-pill gold" style="float:right; font-size:0.6em;">{med}</span>' if med else ""

                    # Tour badge
                    tour = row['Details_Tour']
                    tour_html = f'<span class="tour-badge">{tour}</span>' if tour else ""

                    st.markdown(f"""
                    <div class="combat-card {status_class}">
                        <div class="header-line">
                            <div>
                                <span class="combat-num">CBT #{int(row['Numero'])}</span>
                                {tour_html}
                            </div>
                            <span class="combat-aire">AIRE {int(row['Aire'])}</span>
                        </div>
                        <div class="fighter-line">
                            <div>
                                {corner_html}
                                <span class="fighter-name">{row['Combattant']} {med_html}</span>
                                <span class="honor-title">{titre}</span>
                            </div>
                        </div>
                        <div style="margin-top:10px; font-size:0.8em; text-transform:uppercase; letter-spacing:1px; color:#888;">
                            {row['Statut']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            if df.empty: st.info("Aucun combat affiché pour le moment.")
        else: st.info("La liste est vide.")
    except Exception as e: st.error(f"Erreur: {e}")

# 2. PROFILS
with tab_profil:
    st.header("Fiches Athlètes")
    hist = get_data("Historique", ["Competition", "Date", "Combattant", "Medaille"])
    ath = get_data("Athletes", [])
    
    names = set(hist['Combattant']) if not hist.empty else set()
    if not ath.empty: names.update(ath['Nom'])
    
    if names:
        search = st.selectbox("Rechercher un athlète", sorted(list(names)))
        bio = ""
        if not ath.empty:
            i = ath[ath['Nom'] == search]
            if not i.empty: bio = i.iloc[0]['Titre_Honorifique']
        
        st.markdown(f"<h2 style='color:#FFD700'>{search}</h2>", unsafe_allow_html=True)
        if bio: st.markdown(f"*{bio}*")
        st.write("---")
        
        if not hist.empty:
            my = hist[hist['Combattant'] == search].sort_values('Date', ascending=False)
            for _, r in my.iterrows():
                med = r['Medaille']
                c = "gold" if "Or" in med else "silver" if "Argent" in med else "bronze"
                st.markdown(f"""
                <div style="padding:10px; background:#262730; border-radius:8px; margin-bottom:5px; display:flex; align-items:center;">
                    <span class="medal-pill {c}">{med}</span>
                    <div style="margin-left:10px;">
                        <div style="font-weight:bold; font-size:1.1em;">{r['Competition']}</div>
                        <div style="font-size:0.8em; color:#AAA;">{r['Date']}</div>
                    </div>
                </div>""", unsafe_allow_html=True)

# 3. HISTORIQUE
with tab_historique:
    st.header("Palmarès du Club")
    hist = get_data("Historique", [])
    if not hist.empty:
        st.dataframe(hist.sort_values('Date', ascending=False), use_container_width=True, hide_index=True)

# 4. COACH
with tab_coach:
    if st.text_input("Code", type="password") == "1234":
        
        # --- CALENDRIER ---
        with st.expander("📅 Calendrier", expanded=False):
            c1, c2, c3 = st.columns([3, 2, 1])
            n = c1.text_input("Nom")
            d = c2.date_input("Date")
            if c3.button("Ajouter"):
                cal = get_data("Calendrier", ["Nom_Competition", "Date_Prevue"])
                save_data(pd.concat([cal, pd.DataFrame([{"Nom_Competition": n, "Date_Prevue": str(d)}])], ignore_index=True), "Calendrier")
                st.success("OK"); st.rerun()
            
            cal = get_data("Calendrier", [])
            if not cal.empty:
                if st.button("💾 Save Calendrier"): save_data(st.data_editor(cal, num_rows="dynamic"), "Calendrier"); st.rerun()

        # --- INSCRIPTIONS ---
        with st.expander("📝 Inscriptions & Catégories", expanded=False):
            if 'inscription_df' not in st.session_state:
                st.session_state['inscription_df'] = pd.DataFrame(columns=["Compétition", "Nom Complet", "Année Naissance", "Poids (kg)", "Sexe (M/F)", "Catégorie Calculée"])
            
            cal_opts = get_data("Calendrier", [])
            opts = cal_opts['Nom_Competition'].tolist() if not cal_opts.empty else ["Entraînement"]
            
            edited = st.data_editor(
                st.session_state['inscription_df'], num_rows="dynamic", use_container_width=True,
                column_config={
                    "Compétition": st.column_config.SelectboxColumn(options=opts, required=True),
                    "Sexe (M/F)": st.column_config.SelectboxColumn(options=["M", "F"], required=True),
                    "Année Naissance": st.column_config.NumberColumn(format="%d"),
                    "Poids (kg)": st.column_config.NumberColumn(format="%.1f")
                }
            )
            
            c1, c2, c3 = st.columns(3)
            if c1.button("🔄 Calculer"):
                for i, r in edited.iterrows():
                    if r["Année Naissance"] and r["Poids (kg)"]:
                        edited.at[i, "Catégorie Calculée"] = calculer_categorie(r["Année Naissance"], r["Poids (kg)"], r.get("Sexe (M/F)", "M"))
                st.session_state['inscription_df'] = edited; st.rerun()
            
            if c2.button("📲 WhatsApp"):
                txt = "\n".join([f"🏆 {r['Compétition']} | 🥊 {r['Nom Complet']} : {r['Catégorie Calculée']}" for _, r in edited.iterrows()])
                st.link_button("Envoyer", f"https://wa.me/?text={urllib.parse.quote('📋 INSCRIPTIONS CLUB\\n\\n' + txt)}")
            
            if c3.button("💾 Sauvegarder"):
                save_data(edited.rename(columns={"Compétition": "Competition_Cible", "Nom Complet": "Nom", "Année Naissance": "Annee", "Poids (kg)": "Poids", "Sexe (M/F)": "Sexe", "Catégorie Calculée": "Categorie"}), "PreInscriptions")
                st.success("Sauvegardé")

        st.divider()

        # --- CONFIG LIVE ---
        with st.expander("⚙️ Config Live", expanded=True):
            c1, c2 = st.columns(2)
            cal_opts = get_data("Calendrier", [])
            opts = cal_opts['Nom_Competition'].tolist() if not cal_opts.empty else ["Entraînement"]
            
            nom = c1.selectbox("Événement", opts)
            dt = c2.date_input("Date", st.session_state.get('Config_Date', datetime.today()))
            st.session_state['Config_Compet'] = nom
            st.session_state['Config_Date'] = dt
            
            if st.button("📥 Importer Inscrits"):
                pre = get_data("PreInscriptions", [])
                sub = pre[pre['Competition_Cible'] == nom]
                if not sub.empty:
                    cur = get_data("Feuille 1", [])
                    rows = []
                    for _, r in sub.iterrows():
                        if r['Nom'] and (cur.empty or r['Nom'] not in cur['Combattant'].values):
                            rows.append({"Combattant": r['Nom'], "Aire":0, "Numero":0, "Casque":"Rouge", "Statut":"A venir", "Palmares":"", "Details_Tour":"", "Medaille_Actuelle":""})
                    if rows: save_data(pd.concat([cur, pd.DataFrame(rows)], ignore_index=True), "Feuille 1"); st.success("Import OK"); st.rerun()
                else: st.warning("Aucun inscrit trouvé")

        st.divider()

        # --- GESTION LIVE ---
        st.subheader("⚡ Gestion Live")
        live = get_data("Feuille 1", [])
        act = live[live['Statut'] != "Terminé"]['Combattant'].tolist()
        if act:
            sel = st.selectbox("Boxeur", act)
            idx = live[live['Combattant'] == sel].index[0]
            r = live.iloc[idx]
            with st.form("upd"):
                c1, c2 = st.columns(2)
                nn = c1.number_input("N°", value=int(r['Numero']) if r['Numero'] else 0)
                nm = c2.selectbox("Résultat", ["", "🥇 Or", "🥈 Argent", "🥉 Bronze", "🍫 4ème", "❌ Non classé"])
                if st.form_submit_button("Mettre à jour"):
                    live.at[idx, 'Numero'] = nn
                    live.at[idx, 'Medaille_Actuelle'] = nm
                    save_data(live, "Feuille 1"); st.rerun()
                if st.form_submit_button("🏁 Terminer"):
                    live.at[idx, 'Statut'] = "Terminé"
                    live.at[idx, 'Medaille_Actuelle'] = nm
                    live.at[idx, 'Palmares'] = nm
                    save_data(live, "Feuille 1"); st.rerun()

        st.write("---")
        if st.button("🏁 CLÔTURER & BILAN", type="primary"):
            hist = get_data("Historique", [])
            ath = get_data("Athletes", [])
            pre = get_data("PreInscriptions", [])
            new_a, new_q, rep = [], [], []
            
            for _, r in live.iterrows():
                res = r['Medaille_Actuelle'] if r['Medaille_Actuelle'] else r['Palmares']
                if res and r['Combattant']:
                    new_a.append({"Competition": nom, "Date": str(dt), "Combattant": r['Combattant'], "Medaille": res})
                    rep.append(f"{res} {r['Combattant']}")
                    # Qualif Auto Or/Argent (Simplifié : qualifie pour 'Championnat de France' par défaut si mot clé 'Régional')
                    if "Régional" in nom and res in ["🥇 Or", "🥈 Argent"]:
                        info = ath[ath['Nom'] == r['Combattant']]
                        if not info.empty:
                            inf = info.iloc[0]
                            cat = calculer_categorie(inf['Annee_Naissance'], inf['Poids'], inf['Sexe'])
                            new_q.append({"Competition_Cible": "Championnat de France", "Nom": r['Combattant'], "Annee": inf['Annee_Naissance'], "Poids": inf['Poids'], "Sexe": inf['Sexe'], "Categorie": cat})

            if new_a: save_data(pd.concat([hist, pd.DataFrame(new_a)], ignore_index=True), "Historique"); st.success("Archivé")
            if new_q: save_data(pd.concat([pre, pd.DataFrame(new_q)], ignore_index=True), "PreInscriptions"); st.success("Qualifiés ajoutés !")
            
            msg = urllib.parse.quote(f"🏆 *BILAN {nom}*\n\n" + "\n".join(sorted(rep)))
            st.link_button("📲 WhatsApp Bilan", f"https://wa.me/?text={msg}")

        if st.button("🗑️ Vider Live"): save_data(pd.DataFrame(columns=live.columns), "Feuille 1"); st.rerun()
