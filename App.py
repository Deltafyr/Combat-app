import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import urllib.parse

# --- CONFIGURATION & CSS ---
st.set_page_config(page_title="Fight Tracker V21", page_icon="🥊", layout="wide")

st.markdown("""
    <style>
        html, body, [class*="css"]  { font-family: 'Roboto', sans-serif; font-size: 14px; }
        .combat-card { background-color: #1E1E1E; border-radius: 8px; padding: 10px; margin-bottom: 8px; border-left: 4px solid #555; }
        .header-line { display: flex; justify-content: space-between; align-items: baseline; }
        .combat-num { font-style: italic; font-size: 1.1em; color: #ddd; }
        .combat-aire { background: #333; padding: 2px 8px; border-radius: 10px; font-size: 0.85em; font-weight: bold; color: #FFD700; }
        .fighter-name { font-size: 1.4em; font-weight: 700; color: #fff; display:block;}
        .honor-title { font-size: 0.85em; color: #FFD700; font-style: italic; display:block;}
        .medal-badge { float:right; font-size: 1.2em; }
        .gold { background: #FFD700; color:black; padding:2px 6px; border-radius:4px;} 
        .silver { background: #C0C0C0; color:black; padding:2px 6px; border-radius:4px;}
    </style>
""", unsafe_allow_html=True)

# --- CONNEXION ---
def get_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

# --- LOGIQUE MÉTIER ---
def calculer_categorie(annee, poids, sexe):
    try:
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

# --- GESTION BDD ---
def get_live_data():
    client = get_client()
    sh = client.open("suivi_combats").sheet1
    df = pd.DataFrame(sh.get_all_records())
    cols = ["Combattant", "Aire", "Numero", "Casque", "Statut", "Palmares", "Details_Tour", "Medaille_Actuelle"]
    for c in cols: 
        if c not in df.columns: df[c] = ""
    return df

def get_history_data():
    client = get_client()
    try: sh = client.open("suivi_combats").worksheet("Historique")
    except: sh = client.open("suivi_combats").add_worksheet("Historique", 1000, 4)
    return pd.DataFrame(sh.get_all_records())

def get_athletes_db():
    client = get_client()
    try: sh = client.open("suivi_combats").worksheet("Athletes")
    except: sh = client.open("suivi_combats").add_worksheet("Athletes", 100, 5)
    return pd.DataFrame(sh.get_all_records())

def get_calendar_db():
    client = get_client()
    try: sh = client.open("suivi_combats").worksheet("Calendrier")
    except: sh = client.open("suivi_combats").add_worksheet("Calendrier", 100, 2)
    return pd.DataFrame(sh.get_all_records())

def get_preinscriptions_db():
    client = get_client()
    try: sh = client.open("suivi_combats").worksheet("PreInscriptions")
    except: sh = client.open("suivi_combats").add_worksheet("PreInscriptions", 100, 6)
    return pd.DataFrame(sh.get_all_records())

def get_valid_competitions():
    df = get_calendar_db()
    today = date.today()
    valid = []
    if not df.empty:
        for i, row in df.iterrows():
            try:
                d = datetime.strptime(str(row['Date_Prevue']), "%Y-%m-%d").date()
                if d >= today: valid.append(row['Nom_Competition'])
            except: pass
    return valid

# --- SAUVEGARDES ---
def save_live(df):
    client = get_client()
    sh = client.open("suivi_combats").sheet1
    sh.clear()
    sh.update([df.columns.values.tolist()] + df.values.tolist())

def save_history(df):
    client = get_client()
    sh = client.open("suivi_combats").worksheet("Historique")
    sh.clear()
    sh.update([df.columns.values.tolist()] + df.values.tolist())

def save_calendar(df):
    client = get_client()
    sh = client.open("suivi_combats").worksheet("Calendrier")
    sh.clear()
    sh.update([df.columns.values.tolist()] + df.values.tolist())

def save_preinscriptions(df):
    client = get_client()
    sh = client.open("suivi_combats").worksheet("PreInscriptions")
    sh.clear()
    sh.update([df.columns.values.tolist()] + df.values.tolist())

def update_athlete_full(nom, titre, annee, poids, sexe):
    client = get_client()
    sh = client.open("suivi_combats").worksheet("Athletes")
    df = pd.DataFrame(sh.get_all_records())
    
    # Structure correcte
    expected_cols = ["Nom", "Titre_Honorifique", "Annee_Naissance", "Poids", "Sexe"]
    for c in expected_cols: 
        if c not in df.columns: df[c] = ""
        
    if nom in df['Nom'].values:
        # Update
        idx = df[df['Nom'] == nom].index[0]
        df.at[idx, "Titre_Honorifique"] = titre
        df.at[idx, "Annee_Naissance"] = annee
        df.at[idx, "Poids"] = poids
        df.at[idx, "Sexe"] = sexe
    else:
        # Insert
        new_row = pd.DataFrame([{
            "Nom": nom, "Titre_Honorifique": titre, 
            "Annee_Naissance": annee, "Poids": poids, "Sexe": sexe
        }])
        df = pd.concat([df, new_row], ignore_index=True)
    
    sh.clear()
    sh.update([df.columns.values.tolist()] + df.values.tolist())

# --- INTERFACE ---
tab_public, tab_profil, tab_historique, tab_coach = st.tabs(["📢 LIVE", "👤 PROFILS", "🏛️ CLUB", "🛠️ COACH"])

# 1. LIVE
with tab_public:
    if st.button("🔄 Actualiser", key="ref_pub"): st.rerun()
    try:
        df = get_live_data()
        df_ath = get_athletes_db()
        if not df.empty:
            df['Numero'] = pd.to_numeric(df['Numero'], errors='coerce').fillna(0)
            df['Aire'] = pd.to_numeric(df['Aire'], errors='coerce').fillna(0)
            df_active = df[df['Numero'] > 0].sort_values(by=['Numero', 'Aire'])
            
            st.markdown(f"### 📍 {st.session_state.get('Config_Compet', 'Compétition')}")
            
            for i, row in df_active.iterrows():
                if row['Statut'] != "Terminé":
                    icon = "🔴" if row['Casque'] == "Rouge" else "🔵"
                    border = "#FF4B4B" if "En cours" in row['Statut'] else "#444"
                    titre = ""
                    if not df_ath.empty and "Nom" in df_ath.columns:
                        infos = df_ath[df_ath['Nom'] == row['Combattant']]
                        if not infos.empty: titre = infos.iloc[0]['Titre_Honorifique']
                    
                    st.markdown(f"""
                    <div class="combat-card" style="border-left: 4px solid {border};">
                        <div class="header-line">
                            <span class="combat-num">Combat n°{int(row['Numero'])} <span class="tour-info">({row['Details_Tour']})</span></span>
                            <span class="combat-aire">Aire {int(row['Aire'])}</span>
                        </div>
                        <div class="fighter-line">
                            <span class="fighter-name">{icon} {row['Combattant']} <span class="medal-badge">{row['Medaille_Actuelle']}</span></span>
                            <span class="honor-title">{titre}</span>
                        </div>
                        <div class="status-badge">{row['Statut']}</div>
                    </div>
                    """, unsafe_allow_html=True)
            if df_active.empty: st.info("Aucun combat.")
    except Exception as e: st.error(f"Erreur: {e}")

# 2. PROFILS
with tab_profil:
    st.header("Fiches Athlètes")
    df_hist = get_history_data()
    df_ath = get_athletes_db()
    all_names = set(df_hist['Combattant'].unique()) if not df_hist.empty else set()
    if not df_ath.empty: all_names.update(df_ath['Nom'].unique())
    
    if all_names:
        search = st.selectbox("Rechercher", sorted(list(all_names)))
        bio = ""
        if not df_ath.empty:
            infos = df_ath[df_ath['Nom'] == search]
            if not infos.empty: 
                bio = infos.iloc[0]['Titre_Honorifique']
                poids = infos.iloc[0]['Poids']
                st.caption(f"Infos : {poids}kg | Catégorie habituelle")
        
        st.markdown(f"## {search}")
        if bio: st.markdown(f"**⭐ {bio}**")
        st.divider()
        if not df_hist.empty:
            my_hist = df_hist[df_hist['Combattant'] == search]
            for i, row in my_hist.iterrows():
                med = row['Medaille']
                css = "gold" if "Or" in med else "silver" if "Argent" in med else "bronze" if "Bronze" in med else ""
                st.markdown(f"<div><span class='medal-pill {css}'>{med}</span> <strong>{row['Competition']}</strong> ({row['Date']})</div>", unsafe_allow_html=True)

# 3. HISTORIQUE
with tab_historique:
    st.header("🏛️ Palmarès")
    df_hist = get_history_data()
    if not df_hist.empty: st.dataframe(df_hist.sort_values('Date', ascending=False), use_container_width=True, hide_index=True)

# 4. COACH
with tab_coach:
    password = st.text_input("🔑 Code", type="password")
    if password == "1234":
        
        # --- CALENDRIER ---
        with st.expander("📅 Calendrier Saison", expanded=False):
            c1, c2, c3 = st.columns([3, 2, 1])
            n_cal = c1.text_input("Nom Compétition")
            d_cal = c2.date_input("Date Prévue")
            if c3.button("Ajouter"):
                df_cal = get_calendar_db()
                new = pd.DataFrame([{"Nom_Competition": n_cal, "Date_Prevue": str(d_cal)}])
                save_calendar(pd.concat([df_cal, new], ignore_index=True) if not df_cal.empty else new)
                st.success("Date ajoutée !")
                st.rerun()
            
            df_cal = get_calendar_db()
            if not df_cal.empty:
                edited = st.data_editor(df_cal, num_rows="dynamic", key="cal_ed")
                if st.button("💾 Save Calendrier"): save_calendar(edited); st.rerun()

        valid_competitions = get_valid_competitions()
        if not valid_competitions: valid_competitions = ["Entraînement"]

        # --- INSCRIPTIONS ---
        with st.expander("📝 Inscriptions & Qualifications Auto", expanded=False):
            st.info("Gérez les inscriptions futures ou récupérez les qualifiés.")
            
            # Chargement des pré-inscrits (Qualifiés)
            df_pre = get_preinscriptions_db()
            
            # Fusion avec session state si besoin, ici on travaille direct sur session
            if 'inscription_df' not in st.session_state:
                # On charge les préinscriptions existantes s'il y en a
                if not df_pre.empty:
                    # Renommage pour matcher l'éditeur
                    df_pre = df_pre.rename(columns={"Competition_Cible": "Compétition", "Nom": "Nom Complet", "Annee": "Année Naissance", "Poids": "Poids (kg)", "Sexe": "Sexe (M/F)", "Categorie": "Catégorie Calculée"})
                    st.session_state['inscription_df'] = df_pre
                else:
                    st.session_state['inscription_df'] = pd.DataFrame(columns=["Compétition", "Nom Complet", "Année Naissance", "Poids (kg)", "Sexe (M/F)", "Catégorie Calculée"])

            edited_inscr = st.data_editor(
                st.session_state['inscription_df'],
                num_rows="dynamic",
                column_config={
                    "Compétition": st.column_config.SelectboxColumn("Compétition", options=valid_competitions, required=True),
                    "Sexe (M/F)": st.column_config.SelectboxColumn("Sexe", options=["M", "F"], required=True),
                    "Année Naissance": st.column_config.NumberColumn("Année", format="%d"),
                    "Poids (kg)": st.column_config.NumberColumn("Poids", format="%.1f")
                },
                use_container_width=True,
                key="inscr_ed"
            )
            
            c_calc, c_wa, c_load = st.columns(3)
            if c_calc.button("🔄 Calculer Catégories"):
                for idx, row in edited_inscr.iterrows():
                    if row["Année Naissance"] and row["Poids (kg)"]:
                        cat = calculer_categorie(row["Année Naissance"], row["Poids (kg)"], row.get("Sexe (M/F)", "M"))
                        edited_inscr.at[idx, "Catégorie Calculée"] = cat
                st.session_state['inscription_df'] = edited_inscr
                st.rerun()
                
            if c_wa.button("📲 WhatsApp"):
                lines = [f"🏆 {r['Compétition']} | 🥊 {r['Nom Complet']} : {r['Catégorie Calculée']}" for i, r in edited_inscr.iterrows()]
                msg = urllib.parse.quote("📋 *INSCRIPTIONS*\n\n" + "\n".join(lines))
                st.link_button("Envoyer", f"https://wa.me/?text={msg}")
            
            if c_load.button("💾 Sauvegarder Liste"):
                # On sauvegarde dans l'onglet PreInscriptions pour ne pas perdre
                # Renommage inverse
                to_save = edited_inscr.rename(columns={"Compétition": "Competition_Cible", "Nom Complet": "Nom", "Année Naissance": "Annee", "Poids (kg)": "Poids", "Sexe (M/F)": "Sexe", "Catégorie Calculée": "Categorie"})
                save_preinscriptions(to_save)
                st.success("Liste sauvegardée dans le Cloud !")

        st.divider()

        # --- CONFIGURATION JOUR J ---
        with st.expander("⚙️ Config Live (Jour J)", expanded=True):
            c1, c2 = st.columns(2)
            nom_compet = c1.selectbox("Sélectionner Événement", valid_competitions)
            date_compet = c2.date_input("Date", st.session_state.get('Config_Date', datetime.today()))
            st.session_state['Config_Compet'] = nom_compet
            st.session_state['Config_Date'] = date_compet
            
            # OPTION QUALIFICATION
            st.write("---")
            is_qualif = st.checkbox("⚠️ Cette compétition est qualificative ?")
            target_compet = None
            if is_qualif:
                target_compet = st.selectbox("Les qualifiés (Or/Argent) iront à :", valid_competitions, index=0)
                st.info(f"Les 1er et 2ème seront automatiquement ajoutés à la liste pour '{target_compet}'.")
                st.session_state['Target_Compet'] = target_compet
            else:
                if 'Target_Compet' in st.session_state: del st.session_state['Target_Compet']

            st.write("---")
            if st.button("📥 Importer Inscrits pour ce Live"):
                df_pre = get_preinscriptions_db()
                # On filtre sur le nom de la compet
                subset = df_pre[df_pre['Competition_Cible'] == nom_compet]
                if not subset.empty:
                    cur = get_live_data()
                    rows = []
                    for i, r in subset.iterrows():
                        if r['Nom'] and (cur.empty or r['Nom'] not in cur['Combattant'].values):
                            rows.append({"Combattant": r['Nom'], "Aire":0, "Numero":0, "Casque":"Rouge", "Statut":"A venir", "Palmares":"", "Details_Tour":"", "Medaille_Actuelle":""})
                    if rows:
                        save_live(pd.concat([cur, pd.DataFrame(rows)], ignore_index=True))
                        st.success("Import réussi !")
                        st.rerun()
                else: st.warning("Personne inscrit pour cet événement.")

        st.divider()

        # --- GESTION LIVE ---
        st.subheader("⚡ Gestion Live")
        live = get_live_data()
        actives = live[live['Statut'] != "Terminé"]['Combattant'].tolist()
        if actives:
            sel = st.selectbox("Boxeur", actives)
            idx = live[live['Combattant'] == sel].index[0]
            row = live.iloc[idx]
            with st.form("upd"):
                c1, c2 = st.columns(2)
                n_num = c1.number_input("N°", value=int(row['Numero']) if row['Numero'] else 0)
                n_med = c2.selectbox("Résultat", ["", "🥇 Or", "🥈 Argent", "🥉 Bronze", "🍫 4ème", "❌ Non classé"])
                if st.form_submit_button("Mettre à jour"):
                    live.at[idx, 'Numero'] = n_num
                    live.at[idx, 'Medaille_Actuelle'] = n_med
                    save_live(live)
                    st.rerun()
                if st.form_submit_button("🏁 Terminer"):
                    live.at[idx, 'Statut'] = "Terminé"
                    live.at[idx, 'Medaille_Actuelle'] = n_med
                    live.at[idx, 'Palmares'] = n_med
                    save_live(live)
                    st.toast("Terminé !")
                    st.rerun()

        st.write("---")
        
        # --- CLÔTURE INTELLIGENTE ---
        if st.button("🏁 CLÔTURER & TRAITER QUALIFICATIONS", type="primary"):
            hist = get_history_data()
            df_ath = get_athletes_db() # Pour récupérer poids/âge des gagnants
            df_pre = get_preinscriptions_db() # Pour ajouter les qualifiés
            
            new_arch = []
            new_qualif = []
            report = []
            
            target_evt = st.session_state.get('Target_Compet')
            
            for i, row in live.iterrows():
                res = row['Medaille_Actuelle'] if row['Medaille_Actuelle'] else row['Palmares']
                nom = row['Combattant']
                
                if res and nom:
                    # 1. ARCHIVAGE
                    new_arch.append({"Competition": nom_compet, "Date": str(date_compet), "Combattant": nom, "Medaille": res})
                    report.append(f"{res} {nom}")
                    
                    # 2. QUALIFICATION AUTOMATIQUE (Si Or/Argent et Target défini)
                    if target_evt and res in ["🥇 Or", "🥈 Argent"]:
                        # On cherche les infos de l'athlète dans la base
                        infos = df_ath[df_ath['Nom'] == nom]
                        if not infos.empty:
                            info = infos.iloc[0]
                            # On calcule la catégorie pour gagner du temps
                            cat_auto = calculer_categorie(info['Annee_Naissance'], info['Poids'], info['Sexe'])
                            new_qualif.append({
                                "Competition_Cible": target_evt,
                                "Nom": nom,
                                "Annee": info['Annee_Naissance'],
                                "Poids": info['Poids'],
                                "Sexe": info['Sexe'],
                                "Categorie": cat_auto
                            })
                        else:
                            # Pas d'info ? On inscrit quand même mais vide
                            new_qualif.append({"Competition_Cible": target_evt, "Nom": nom, "Annee": "", "Poids": "", "Sexe": "", "Categorie": "A compléter"})

            # SAUVEGARDE ARCHIVES
            if new_arch:
                save_history(pd.concat([hist, pd.DataFrame(new_arch)], ignore_index=True))
                st.success("✅ Résultats archivés.")
            
            # SAUVEGARDE QUALIFIÉS
            if new_qualif:
                save_preinscriptions(pd.concat([df_pre, pd.DataFrame(new_qualif)], ignore_index=True))
                st.balloons()
                st.success(f"🚀 {len(new_qualif)} boxeurs qualifiés automatiquement pour '{target_evt}' !")
            
            # WHATSAPP
            msg = urllib.parse.quote(f"🏆 *BILAN {nom_compet}*\n\n" + "\n".join(sorted(report)))
            st.link_button("📲 Envoyer Bilan", f"https://wa.me/?text={msg}")

        if st.button("🗑️ Vider Live"):
            save_live(pd.DataFrame(columns=live.columns))
            st.warning("Live vidé.")
            st.rerun()

        # --- GESTION ATHLÈTES (Base de données complète) ---
        with st.expander("👤 Base Athlètes (Pour Qualifications Auto)"):
            st.info("Remplissez ceci pour que l'inscription automatique fonctionne.")
            df_ath = get_athletes_db()
            
            # Vérification colonnes
            cols_req = ["Nom", "Titre_Honorifique", "Annee_Naissance", "Poids", "Sexe"]
            for c in cols_req: 
                if c not in df_ath.columns: df_ath[c] = ""
            
            edited_ath = st.data_editor(
                df_ath, 
                num_rows="dynamic",
                column_config={
                    "Sexe": st.column_config.SelectboxColumn("Sexe", options=["M", "F"]),
                    "Annee_Naissance": st.column_config.NumberColumn("Année", format="%d"),
                    "Poids": st.column_config.NumberColumn("Poids", format="%.1f")
                },
                key="ath_editor"
            )
            if st.button("Sauvegarder Base Athlètes"):
                # Save raw
                client = get_client()
                sh = client.open("suivi_combats").worksheet("Athletes")
                sh.clear()
                sh.update([edited_ath.columns.values.tolist()] + edited_ath.values.tolist())
                st.success("Base mise à jour")
