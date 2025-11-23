import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import urllib.parse

# --- CONFIGURATION & CSS ---
st.set_page_config(page_title="Fight Tracker V20", page_icon="🥊", layout="wide")

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

# --- LOGIQUE METIER ---
def calculer_categorie(annee_naissance, poids, sexe):
    try:
        annee_actuelle = datetime.now().year
        age = annee_actuelle - int(annee_naissance)
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
        found = False
        if limites and poids > limites[-1]: cat_poids = f"+{limites[-1]}kg"; found = True
        else:
            for lim in limites:
                if poids <= lim: cat_poids = f"-{lim}kg"; found = True; break
        if not found and not limites: cat_poids = f"{poids}kg (Cat?)"
        return f"{cat_age} {sexe} {cat_poids}"
    except: return "Erreur Données"

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

def get_calendar_db():
    try:
        client = get_client()
        sh = client.open("suivi_combats").worksheet("Calendrier")
        return pd.DataFrame(sh.get_all_records())
    except: return pd.DataFrame(columns=["Nom_Competition", "Date_Prevue"])

def get_valid_competitions():
    """Renvoie la liste des compétitions futures ou du jour"""
    df = get_calendar_db()
    valid_list = []
    today = date.today()
    
    if not df.empty:
        for i, row in df.iterrows():
            try:
                date_obj = datetime.strptime(str(row['Date_Prevue']), "%Y-%m-%d").date()
                # On garde si la date est aujourd'hui ou dans le futur
                if date_obj >= today:
                    valid_list.append(row['Nom_Competition'])
            except:
                continue # Erreur de date, on ignore
    return valid_list

# --- SAUVEGARDES ---
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

def save_calendar_dataframe(df):
    client = get_client()
    try: sh = client.open("suivi_combats").worksheet("Calendrier")
    except: sh = client.open("suivi_combats").add_worksheet(title="Calendrier", rows=100, cols=2)
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
                    titre = ""
                    if not df_athletes.empty:
                        infos = df_athletes[df_athletes['Nom'] == row['Combattant']]
                        if not infos.empty: titre = infos.iloc[0]['Titre_Honorifique']

                    st.markdown(f"""
                    <div class="combat-card" style="border-left: 4px solid {border};">
                        <div class="header-line">
                            <span class="combat-num">Combat n°{int(row['Numero'])} <span class="tour-info">({row['Details_Tour']})</span></span>
                            <span class="combat-aire">Aire {int(row['Aire'])}</span>
                        </div>
                        <div class="fighter-line">
                            <span class="fighter-name">{icon_casque} {row['Combattant']} <span class="medal-badge">{row['Medaille_Actuelle']}</span></span>
                            <span class="honor-title">{titre}</span>
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
        if bio: st.markdown(f"**⭐ {bio}**")
        st.divider()
        if not df_hist.empty:
            my_hist = df_hist[df_hist['Combattant'] == search]
            if not my_hist.empty:
                for i, row in my_hist.iterrows():
                    med = row['Medaille']
                    css = "gold" if "Or" in med else "silver" if "Argent" in med else "bronze" if "Bronze" in med else ""
                    st.markdown(f"""
                    <div style="border-bottom:1px solid #333; padding:5px;">
                        <span class="medal-pill {css}">{med}</span>
                        <strong>{row['Competition']}</strong> <span style="color:#888;">({row['Date']})</span>
                    </div>""", unsafe_allow_html=True)
            else: st.info("Pas d'historique.")
    else: st.info("Base vide.")

# 3. HISTORIQUE
with tab_historique:
    st.header("🏛️ Palmarès Global")
    df_hist = get_history_data()
    if not df_hist.empty:
        st.dataframe(df_hist.sort_values(by='Date', ascending=False), use_container_width=True, hide_index=True)
    else: st.info("Vide.")

# 4. COACH
with tab_coach:
    password = st.text_input("🔑 Code", type="password")
    if password == "1234":
        
        # --- SECTION 0 : CALENDRIER SAISON (NOUVEAU) ---
        with st.expander("📅 Programmation Saison (Calendrier)", expanded=True):
            st.info("Ajoutez ici les compétitions futures. Elles apparaîtront dans les listes déroulantes.")
            
            # Formulaire ajout
            c_cal1, c_cal2, c_cal3 = st.columns([3, 2, 1])
            new_cal_name = c_cal1.text_input("Nom Compétition")
            new_cal_date = c_cal2.date_input("Date Prévue")
            
            if c_cal3.button("Ajouter Date"):
                if new_cal_name:
                    cal_df = get_calendar_db()
                    new_event = pd.DataFrame([{"Nom_Competition": new_cal_name, "Date_Prevue": str(new_cal_date)}])
                    if cal_df.empty: final_cal = new_event
                    else: final_cal = pd.concat([cal_df, new_event], ignore_index=True)
                    save_calendar_dataframe(final_cal)
                    st.success("Date ajoutée !")
                    st.rerun()
            
            # Affichage tableau calendrier (pour supprimer si besoin)
            st.write("---")
            cal_df_view = get_calendar_db()
            if not cal_df_view.empty:
                edited_cal = st.data_editor(cal_df_view, num_rows="dynamic", key="cal_editor")
                if st.button("💾 Sauvegarder Calendrier"):
                    save_calendar_dataframe(edited_cal)
                    st.rerun()

        st.divider()
        
        # Récupération liste active pour les menus déroulants
        valid_competitions = get_valid_competitions()
        if not valid_competitions: valid_competitions = ["Entraînement / Autre"]

        # --- SECTION 1 : PRÉPARATION INSCRIPTIONS ---
        with st.expander("📝 Préparer Inscriptions & Catégories", expanded=False):
            st.info("Saisissez les infos pour générer la liste à envoyer.")
            
            if 'inscription_df' not in st.session_state:
                st.session_state['inscription_df'] = pd.DataFrame(columns=["Compétition", "Nom Complet", "Année Naissance", "Poids (kg)", "Sexe (M/F)", "Catégorie Calculée"])
            
            # On s'assure que la colonne Compétition existe
            if "Compétition" not in st.session_state['inscription_df'].columns:
                 st.session_state['inscription_df'].insert(0, "Compétition", "")

            edited_inscr = st.data_editor(
                st.session_state['inscription_df'],
                num_rows="dynamic",
                column_config={
                    # LISTE DEROULANTE ISSUE DU CALENDRIER
                    "Compétition": st.column_config.SelectboxColumn("Compétition", options=valid_competitions, required=True, width="medium"),
                    "Nom Complet": st.column_config.TextColumn("Nom Prénom", width="medium"),
                    "Année Naissance": st.column_config.NumberColumn("Année", min_value=1950, max_value=2025, step=1, format="%d"),
                    "Poids (kg)": st.column_config.NumberColumn("Poids", min_value=10, max_value=150, step=0.1, format="%.1f"),
                    "Sexe (M/F)": st.column_config.SelectboxColumn("Sexe", options=["M", "F"], required=True),
                    "Catégorie Calculée": st.column_config.TextColumn("Catégorie (Auto)", disabled=True)
                },
                use_container_width=True,
                key="editor_inscr"
            )
            
            col_calc, col_wa = st.columns(2)
            if col_calc.button("🔄 Calculer les Catégories"):
                for idx, row in edited_inscr.iterrows():
                    if row["Année Naissance"] and row["Poids (kg)"]:
                        cat = calculer_categorie(row["Année Naissance"], row["Poids (kg)"], row.get("Sexe (M/F)", "M"))
                        edited_inscr.at[idx, "Catégorie Calculée"] = cat
                st.session_state['inscription_df'] = edited_inscr
                st.rerun()

            if col_wa.button("📲 Générer Message Inscription"):
                if not edited_inscr.empty:
                    lines = []
                    for idx, row in edited_inscr.iterrows():
                        compet_name = row["Compétition"] if row["Compétition"] else "?"
                        nom = row["Nom Complet"]
                        cat = row["Catégorie Calculée"] if row["Catégorie Calculée"] else "En attente"
                        poids = row["Poids (kg)"]
                        lines.append(f"🏆 {compet_name} | 🥊 {nom} : {poids}kg -> *{cat}*")
                    msg_text = "📋 *LISTE INSCRIPTIONS CLUB*\n\n" + "\n".join(lines)
                    msg_encoded = urllib.parse.quote(msg_text)
                    st.link_button("Envoyer sur WhatsApp", f"https://wa.me/?text={msg_encoded}", type="primary")
                else: st.warning("Tableau vide.")

        st.divider()

        # --- SECTION 2 : CONFIG LIVE ---
        with st.expander("⚙️ Configuration Compétition du Jour", expanded=False):
            c1, c2 = st.columns(2)
            
            # SELECTBOX DYNAMIQUE CALENDRIER
            nom_compet_select = c1.selectbox("Sélectionner Événement du Jour", valid_competitions, index=0)
            date_compet = c2.date_input("Date", st.session_state.get('Config_Date', datetime.today()))
            
            # Mise à jour Session
            st.session_state['Config_Compet'] = nom_compet_select
            st.session_state['Config_Date'] = date_compet
            
            st.write("---")
            st.write("#### 📥 Importer depuis la liste d'inscription")
            
            if 'inscription_df' in st.session_state and not st.session_state['inscription_df'].empty:
                # On cherche les gens inscrits à CETTE compétition sélectionnée
                subset = st.session_state['inscription_df'][st.session_state['inscription_df']['Compétition'] == nom_compet_select]
                
                if not subset.empty:
                    st.info(f"{len(subset)} combattants trouvés pour '{nom_compet_select}'")
                    if st.button(f"Importer ces {len(subset)} combattants dans le Live"):
                        cur_live = get_live_data()
                        rows = []
                        for idx, row in subset.iterrows():
                            name = row["Nom Complet"]
                            if name and (cur_live.empty or name not in cur_live['Combattant'].values):
                                rows.append({"Combattant": name, "Aire":0, "Numero":0, "Casque":"Rouge", "Statut":"A venir", "Palmares":"", "Details_Tour":"", "Medaille_Actuelle":""})
                        if rows:
                            final = pd.concat([cur_live, pd.DataFrame(rows)], ignore_index=True)
                            save_live_dataframe(final)
                            st.success("Import réussi !")
                            st.rerun()
                else:
                    st.warning(f"Aucun inscrit trouvé pour '{nom_compet_select}' dans votre tableau d'inscription.")
            else:
                st.caption("Remplissez le tableau d'inscription d'abord.")

        st.divider()

        # --- SECTION 3 : GESTION LIVE ---
        st.subheader("⚡ Gestion Live")
        live_df = get_live_data()
        active_mask = live_df['Statut'] != "Terminé"
        actives = live_df[active_mask]['Combattant'].tolist()
        if actives:
            sel_boxer = st.selectbox("Boxeur en cours", actives)
            idx = live_df[live_df['Combattant'] == sel_boxer].index[0]
            row = live_df.iloc[idx]
            with st.form("upd"):
                col_a, col_b = st.columns(2)
                n_num = col_a.number_input("N°", value=int(row['Numero']) if row['Numero'] else 0)
                n_med = col_b.selectbox("Résultat/Médaille", ["", "🥇 Or", "🥈 Argent", "🥉 Bronze", "🍫 4ème", "❌ Non classé"], index=0)
                b_up = st.form_submit_button("✅ Mettre à jour")
                b_fin = st.form_submit_button("🏁 Terminer & Archiver")
                if b_up:
                    live_df.at[idx, 'Numero'] = n_num
                    live_df.at[idx, 'Medaille_Actuelle'] = n_med
                    save_live_dataframe(live_df)
                    st.rerun()
                if b_fin:
                    live_df.at[idx, 'Statut'] = "Terminé"
                    live_df.at[idx, 'Medaille_Actuelle'] = n_med
                    live_df.at[idx, 'Palmares'] = n_med
                    save_live_dataframe(live_df)
                    st.toast("Terminé !")
                    st.rerun()
        
        st.write("---")
        
        # --- CLÔTURE ---
        st.subheader("📤 Fin de Journée")
        col_archive, col_clear = st.columns([2, 1])
        
        with col_archive:
            if st.button("🏁 CLÔTURER & GÉNÉRER LE BILAN", type="primary"):
                hist_df = get_history_data()
                new_archives = []
                report_lines = []
                # On utilise la compétition configurée en haut
                final_compet_name = st.session_state.get('Config_Compet', "Compétition")
                final_date = st.session_state.get('Config_Date', datetime.today())
                
                for i, row in live_df.iterrows():
                    res = row['Medaille_Actuelle'] if row['Medaille_Actuelle'] else row['Palmares']
                    if res and row['Combattant']:
                        new_archives.append({"Competition": final_compet_name, "Date": str(final_date), "Combattant": row['Combattant'], "Medaille": res})
                        report_lines.append(f"{res} {row['Combattant']}")
                
                if new_archives:
                    new_hist_df = pd.concat([hist_df, pd.DataFrame(new_archives)], ignore_index=True)
                    save_history_dataframe(new_hist_df)
                    st.success("✅ Résultats archivés !")
                    report_lines.sort()
                    msg_text = f"🏆 *RÉSULTATS DU CLUB*\n📍 {final_compet_name}\n🗓️ {final_date}\n\n" + "\n".join(report_lines) + "\n\n🔥 *Bravo à toute l'équipe !*"
                    msg_encoded = urllib.parse.quote(msg_text)
                    st.session_state['wa_link'] = f"https://wa.me/?text={msg_encoded}"
                else: st.warning("Rien à archiver.")

            if 'wa_link' in st.session_state:
                st.link_button("📲 Envoyer le Bilan sur WhatsApp", st.session_state['wa_link'], type="primary")

        with col_clear:
            if st.button("🗑️ Vider le Live"):
                empty = pd.DataFrame(columns=live_df.columns)
                save_live_dataframe(empty)
                if 'wa_link' in st.session_state: del st.session_state['wa_link']
                st.warning("Liste Live effacée.")
                st.rerun()
        
        st.divider()

        # --- ADMIN ---
        with st.expander("🛠️ Outils Admin (Historique/Bio)"):
            full_hist = get_history_data()
            edited_hist = st.data_editor(full_hist, num_rows="dynamic", use_container_width=True, key="hist_editor")
            if st.button("💾 Sauvegarder Historique"):
                save_history_dataframe(edited_hist)
                st.rerun()
            st.write("---")
            df_ath = get_athletes_db()
            edited_ath = st.data_editor(df_ath, num_rows="dynamic", key="ath_editor")
            if st.button("Sauvegarder Athlètes"):
                client = get_client()
                try: sh = client.open("suivi_combats").worksheet("Athletes")
                except: sh = client.open("suivi_combats").add_worksheet(title="Athletes", rows=100, cols=5)
                sh.clear()
                sh.update([edited_ath.columns.values.tolist()] + edited_ath.values.tolist())
                st.success("OK")
