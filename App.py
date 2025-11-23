import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import urllib.parse
import time

# --- CONFIGURATION & DESIGN ---
st.set_page_config(page_title="Fight Tracker V28", page_icon="🥊", layout="wide")

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
    # Update Live
    live_df.at[idx, 'Statut'] = "Terminé"
    live_df.at[idx, 'Medaille_Actuelle'] = resultat
    live_df.at[idx, 'Palmares'] = resultat
    save_data(live_df, "Feuille 1", [])
    
    # Archive
    nom_combattant = live_df.at[idx, 'Combattant']
    hist = get_history_data()
    new_entry = pd.DataFrame([{"Competition": nom_compet, "Date": str(date_compet), "Combattant": nom_combattant, "Medaille": resultat}])
    save_data(pd.concat([hist, new_entry], ignore_index=True), "Historique", ["Competition", "Date", "Combattant", "Medaille"])
    
    # Qualif
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
                    <div><span class="fighter-name">{row['Combattant']} {med_badge}</span><span class="honor-title">{titre}</span></div>
                </div>
                <div class="status-badge">{row['Statut']}</div>
            </div>""", unsafe_allow_html=True)
    else: st.info("Aucun combat.")

# 2. COACH
with tab_coach:
    if st.text_input("Code", type="password") == "1234":
        subtab_pilotage, subtab_admin = st.tabs(["⚡ PILOTAGE LIVE", "⚙️ CONFIG & ADMIN"])
        
        # --- PILOTAGE ---
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
            else: st.info("Aucun combat en cours.")

        # --- ADMIN ---
        with subtab_admin:
            
            # 1. SELECTION COMPETITION & CREATION
            st.markdown("#### 1. Sélection de la Compétition")
            col_sel, col_new = st.columns([3, 1])
            
            cal_opts = get_calendar_db()
            opts = cal_opts['Nom_Competition'].tolist() if not cal_opts.empty else ["Entraînement"]
            
            # Selectbox principale
            with col_sel:
                nom_c = st.selectbox("Événement Actuel", opts, label_visibility="collapsed")
            
            # Bouton création rapide
            with col_new:
                with st.popover("➕ Créer", use_container_width=True):
                    new_n = st.text_input("Nom")
                    new_d = st.date_input("Date")
                    if st.button("Ajouter au calendrier"):
                        new_row = pd.DataFrame([{"Nom_Competition": new_n, "Date_Prevue": str(new_d)}])
                        save_data(pd.concat([cal_opts, new_row], ignore_index=True), "Calendrier", ["Nom_Competition", "Date_Prevue"])
                        st.success("Créé !")
                        st.rerun()

            # Stockage session
            st.session_state['Config_Compet'] = nom_c
            
            st.write("---")
            
            # 2. INSCRIPTIONS INTELLIGENTES
            st.markdown("#### 2. Inscriptions & Pesée")
            st.info("Saisissez les NOMS. Cliquez sur la baguette magique pour tout remplir automatiquement.")
            
            if 'inscr_df' not in st.session_state:
                st.session_state['inscr_df'] = pd.DataFrame(columns=["Compétition", "Nom Complet", "Année Naissance", "Poids (kg)", "Sexe (M/F)", "Catégorie Calculée"])
            
            # Editeur
            edited = st.data_editor(
                st.session_state['inscr_df'], 
                num_rows="dynamic", 
                use_container_width=True,
                column_config={
                    "Compétition": st.column_config.Column(disabled=True), # On le remplit auto
                    "Sexe (M/F)": st.column_config.SelectboxColumn(options=["M", "F"]),
                    "Année Naissance": st.column_config.NumberColumn(format="%d"),
                    "Poids (kg)": st.column_config.NumberColumn(format="%.1f")
                }
            )
            
            c_magic, c_wa, c_save = st.columns(3)
            
            # LE BOUTON MAGIQUE
            if c_magic.button("✨ Remplir Infos & Calculer", type="primary"):
                df_ath = get_athletes_db()
                
                for i, row in edited.iterrows():
                    # 1. Force le nom de la compétition
                    edited.at[i, "Compétition"] = nom_c
                    
                    nom = row["Nom Complet"]
                    if nom:
                        # 2. Cherche dans la base Athlètes
                        if not df_ath.empty:
                            found = df_ath[df_ath['Nom'] == nom]
                            if not found.empty:
                                info = found.iloc[0]
                                # On remplit seulement si vide dans le tableau (pour laisser la modif possible)
                                if pd.isna(row["Année Naissance"]) or row["Année Naissance"] == "":
                                    edited.at[i, "Année Naissance"] = info['Annee_Naissance']
                                if pd.isna(row["Poids (kg)"]) or row["Poids (kg)"] == "":
                                    edited.at[i, "Poids (kg)"] = info['Poids']
                                if pd.isna(row["Sexe (M/F)"]) or row["Sexe (M/F)"] == "":
                                    edited.at[i, "Sexe (M/F)"] = info['Sexe']
                        
                        # 3. Calcul Catégorie (avec les nouvelles valeurs)
                        # On doit relire les valeurs potentiellement mises à jour
                        an = edited.at[i, "Année Naissance"]
                        pd_val = edited.at[i, "Poids (kg)"]
                        sx = edited.at[i, "Sexe (M/F)"]
                        
                        if an and pd_val:
                            edited.at[i, "Catégorie Calculée"] = calculer_categorie(an, pd_val, sx)
                
                st.session_state['inscr_df'] = edited
                st.rerun()

            if c_wa.button("📲 Générer Message"):
                txt = "\n".join([f"🏆 {r['Compétition']} | 🥊 {r['Nom Complet']} : {r['Catégorie Calculée']}" for _, r in edited.iterrows() if r['Nom Complet']])
                st.link_button("Envoyer WhatsApp", f"https://wa.me/?text={urllib.parse.quote('📋 INSCRIPTIONS\\n\\n' + txt)}")
            
            if c_save.button("💾 Sauvegarder Liste"):
                pre = get_preinscriptions_db()
                to_save = edited.rename(columns={"Compétition": "Competition_Cible", "Nom Complet": "Nom", "Année Naissance": "Annee", "Poids (kg)": "Poids", "Sexe (M/F)": "Sexe", "Catégorie Calculée": "Categorie"})
                # On sauvegarde aussi les nouvelles infos athlètes dans la base principale !
                for _, r in edited.iterrows():
                    if r["Nom Complet"] and r["Année Naissance"]:
                        # On met à jour la fiche athlète discrètement
                        save_athlete(r["Nom Complet"], "") # Titre vide par défaut, mais update poids/age
                        # Note: save_athlete est simple, on pourrait faire une update plus fine mais ça suffit pour créer l'entrée
                
                save_data(pd.concat([pre, to_save], ignore_index=True), "PreInscriptions", [])
                st.success("Sauvegardé !")

            st.write("---")
            
            # 3. IMPORT LIVE
            st.markdown("#### 3. Lancement")
            qualif = st.checkbox("Compétition Qualificative ?")
            tgt = st.selectbox("Vers...", opts) if qualif else None
            st.session_state['Target_Compet'] = tgt
            
            if st.button(f"📥 Importer les inscrits de '{nom_c}' vers le Live"):
                pre = get_preinscriptions_db()
                sub = pre[pre['Competition_Cible'] == nom_c]
                if not sub.empty:
                    cur = get_live_data()
                    rows = []
                    for _, r in sub.iterrows():
                        if r['Nom'] and (cur.empty or r['Nom'] not in cur['Combattant'].values):
                            rows.append({"Combattant": r['Nom'], "Aire":0, "Numero":0, "Casque":"Rouge", "Statut":"A venir", "Palmares":"", "Details_Tour":"", "Medaille_Actuelle":""})
                    if rows: save_data(pd.concat([cur, pd.DataFrame(rows)], ignore_index=True), "Feuille 1", []); st.success("Importé !"); st.rerun()
                else: st.warning("Aucun inscrit trouvé.")
            
            if st.button("🗑️ Vider le Live (Reset)", type="primary"):
                save_data(pd.DataFrame(columns=get_live_data().columns), "Feuille 1", [])
                st.rerun()

# 3. PROFILS & 4. HISTORIQUE (Inchangé)
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
