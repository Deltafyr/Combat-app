import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import urllib.parse
import time

# --- CONFIGURATION & DESIGN ---
st.set_page_config(page_title="Fight Tracker V43", page_icon="🥊", layout="wide")

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

# --- BDD ROBUSTE ---
def get_worksheet_safe(name, cols):
    client = get_client()
    try: sh = client.open("suivi_combats")
    except: return None
    try: ws = sh.worksheet(name)
    except: 
        ws = sh.add_worksheet(name, 1000, len(cols)+2)
        ws.append_row(cols)
        time.sleep(1)
    return ws

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
        ws.update([df.columns.values.tolist()] + df.values.tolist())
        fetch_data.clear()

def save_athlete(nom, prenom, titre, annee, poids, sexe):
    cols_order = ["Nom", "Prenom", "Annee_Naissance", "Poids", "Sexe", "Titre_Honorifique"]
    ws = get_worksheet_safe("Athletes", cols_order)
    if ws:
        df = pd.DataFrame(ws.get_all_records())
        if "Nom" not in df.columns: df = pd.DataFrame(columns=cols_order)
        nom = str(nom).strip().upper()
        prenom = str(prenom).strip().capitalize()
        mask = (df['Nom'] == nom) & (df['Prenom'] == prenom)
        if mask.any():
            idx = df[mask].index[0]
            if titre: df.at[idx, "Titre_Honorifique"] = titre
            if annee: df.at[idx, "Annee_Naissance"] = annee
            if poids: df.at[idx, "Poids"] = poids
            if sexe: df.at[idx, "Sexe"] = sexe
        else:
            new_row = pd.DataFrame([{
                "Nom": nom, "Prenom": prenom, "Titre_Honorifique": titre,
                "Annee_Naissance": annee, "Poids": poids, "Sexe": sexe
            }])
            df = pd.concat([df, new_row], ignore_index=True)
        df = df[cols_order]
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
                    <div class="header-line">
                        <div><span class="combat-num">CBT #{int(row['Numero'])}</span><span class="tour-info">{row['Details_Tour']}</span></div>
                        <span class="combat-aire">AIRE {int(row['Aire'])}</span>
                    </div>
                    <div class="fighter-line">
                        <div>{corner_span}<span class="fighter-name">{row['Combattant']} {med_badge}</span><span class="honor-title">{titre}</span></div>
                    </div>
                    <div class="status-badge">{row['Statut']}</div>
                </div>""", unsafe_allow_html=True)
        if df.empty: st.info("Les combats n'ont pas encore commencé.")
    else: st.info("Aucun combat.")

# 2. COACH
with tab_coach:
    if st.text_input("Code", type="password") == "1234":
        subtab_pilotage, subtab_admin = st.tabs(["⚡ PILOTAGE LIVE", "⚙️ CONFIG & ADMIN"])
        
        with subtab_pilotage:
            st.caption(f"Événement : **{st.session_state.get('Config_Compet', 'Non Défini')}**")
            live = get_live_data()
            if not live.empty:
                # ZONE DISPATCH
                live['Numero'] = pd.to_numeric(live['Numero'], errors='coerce').fillna(0)
                waiting_list = live[(live['Statut'] != "Terminé") & (live['Numero'] == 0)]
                
                if not waiting_list.empty:
                    st.markdown("### ⚠️ À PROGRAMMER (Tirage)")
                    st.markdown('<div class="dispatch-box">', unsafe_allow_html=True)
                    for idx, row in waiting_list.iterrows():
                        c_nom, c_aire, c_num, c_casque, c_btn = st.columns([2, 1, 1, 2, 1])
                        with c_nom:
                            st.markdown(f"**🥊 {row['Combattant']}**")
                            cat_info = row.get('Details_Tour', '')
                            if cat_info: st.caption(f"{cat_info}")
                        na = c_aire.number_input("Aire", value=1, min_value=1, key=f"wa_{idx}", label_visibility="collapsed")
                        nn = c_num.number_input("N°", value=1, min_value=1, key=f"wn_{idx}", label_visibility="collapsed")
                        nc = c_casque.radio("Casque", ["Rouge", "Bleu"], horizontal=True, key=f"wc_{idx}", label_visibility="collapsed")
                        if c_btn.button("Go", key=f"wb_{idx}", type="primary"):
                            live.at[idx, 'Aire'] = na; live.at[idx, 'Numero'] = nn; live.at[idx, 'Casque'] = nc
                            save_data(live, "Feuille 1", []); st.rerun()
                        st.markdown("---")
                    st.markdown('</div>', unsafe_allow_html=True)

                # ZONE PILOTAGE
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
            st.markdown("#### 1. Configuration")
            c1, c2 = st.columns(2)
            cal_opts = get_calendar_db()
            opts = cal_opts['Nom_Competition'].tolist() if not cal_opts.empty else ["Entraînement"]
            with c1: nom_c = st.selectbox("Événement", opts)
            with c2:
                with st.popover("➕ Créer"):
                    new_n = st.text_input("Nom"); new_d = st.date_input("Date")
                    if st.button("OK"):
                        save_data(pd.concat([cal_opts, pd.DataFrame([{"Nom_Competition": new_n, "Date_Prevue": str(new_d)}])], ignore_index=True), "Calendrier", ["Nom_Competition", "Date_Prevue"]); st.rerun()
            
            st.session_state['Config_Compet'] = nom_c
            qualif = st.checkbox("Qualificatif ?")
            st.session_state['Target_Compet'] = st.selectbox("Vers", opts) if qualif else None
            
            if st.button("📥 Importer les Inscrits"):
                if 'inscr_df' in st.session_state and not st.session_state['inscr_df'].empty:
                    to_save = st.session_state['inscr_df'].copy()
                    to_save = to_save[to_save["Nom"] != ""]
                    if not to_save.empty:
                        for _, r in to_save.iterrows():
                            if r["Nom"] and r["Année Naissance"]: save_athlete(r["Nom"], r["Prénom"], "", r["Année Naissance"], r["Poids (kg)"], r["Sexe (M/F)"])
                        final_save = to_save.rename(columns={"Compétition": "Competition_Cible", "Nom": "Nom", "Prénom": "Prenom", "Année Naissance": "Annee", "Poids (kg)": "Poids", "Sexe (M/F)": "Sexe", "Catégorie Calculée": "Categorie"})
                        current_pre = get_preinscriptions_db()
                        save_data(pd.concat([current_pre, final_save[["Competition_Cible", "Nom", "Prenom", "Annee", "Poids", "Sexe", "Categorie"]]], ignore_index=True), "PreInscriptions", [])
                        st.toast("Sauvegardé auto", icon="💾")
                
                pre = get_preinscriptions_db()
                sub = pre[pre['Competition_Cible'] == nom_c]
                if not sub.empty:
                    cur = get_live_data()
                    rows = []
                    for _, r in sub.iterrows():
                        nom_complet = f"{r['Nom']} {r['Prenom']}".strip()
                        if nom_complet and (cur.empty or nom_complet not in cur['Combattant'].values):
                            rows.append({"Combattant": nom_complet, "Aire":0, "Numero":0, "Casque":"Rouge", "Statut":"A venir", "Palmares":"", "Details_Tour": r.get('Categorie', ''), "Medaille_Actuelle":""})
                    if rows: save_data(pd.concat([cur, pd.DataFrame(rows)], ignore_index=True), "Feuille 1", []); st.success(f"✅ {len(rows)} importés !"); st.rerun()
                    else: st.warning("Déjà dans le Live.")
                else: st.warning("Aucun inscrit.")
            
            st.write("---")
            st.markdown("#### 2. Inscriptions")
            if 'inscr_df' not in st.session_state: st.session_state['inscr_df'] = pd.DataFrame(columns=["Compétition", "Nom", "Prénom", "Année Naissance", "Poids (kg)", "Sexe (M/F)", "Catégorie Calculée"])
            
            with st.expander("📂 Charger depuis la Base Athlètes"):
                db_ath = get_athletes_db()
                if not db_ath.empty:
                    db_ath['Full_Name'] = db_ath.apply(lambda x: f"{x['Nom']} {x['Prenom']}", axis=1)
                    selected_athletes = st.multiselect("Sélectionnez :", db_ath['Full_Name'].unique())
                    if st.button("📥 Ajouter"):
                        to_add = []
                        for full in selected_athletes:
                            info = db_ath[db_ath['Full_Name'] == full].iloc[0]
                            to_add.append({"Compétition": nom_c, "Nom": info['Nom'], "Prénom": info['Prenom'], "Année Naissance": info['Annee_Naissance'], "Poids (kg)": info['Poids'], "Sexe (M/F)": info['Sexe'], "Catégorie Calculée": calculer_categorie(info['Annee_Naissance'], info['Poids'], info['Sexe'])})
                        if to_add: st.session_state['inscr_df'] = pd.concat([st.session_state['inscr_df'], pd.DataFrame(to_add)], ignore_index=True); st.rerun()
                else: st.warning("Base vide.")

            edited = st.data_editor(st.session_state['inscr_df'], num_rows="dynamic", use_container_width=True, column_config={"Compétition": st.column_config.Column(disabled=True), "Sexe (M/F)": st.column_config.SelectboxColumn(options=["M", "F"]), "Année Naissance": st.column_config.NumberColumn(format="%d"), "Poids (kg)": st.column_config.NumberColumn(format="%.1f")})
            
            cm, cw, cs = st.columns(3)
            if cm.button("✨ Recalculer"):
                for i, row in edited.iterrows():
                    edited.at[i, "Compétition"] = nom_c
                    if edited.at[i, "Année Naissance"] and edited.at[i, "Poids (kg)"]: edited.at[i, "Catégorie Calculée"] = calculer_categorie(edited.at[i, "Année Naissance"], edited.at[i, "Poids (kg)"], edited.at[i, "Sexe (M/F)"])
                st.session_state['inscr_df'] = edited; st.rerun()
            
            if cw.button("📲 WhatsApp"):
                txt = "\n".join([f"🏆 {r['Compétition']} | 🥊 {str(r['Nom']).upper()} {r['Prénom']} : {r['Catégorie Calculée']}" for _, r in edited.iterrows() if r['Nom']])
                st.link_button("Envoyer", f"https://wa.me/?text={urllib.parse.quote('📋 INSCRIPTIONS\\n\\n' + txt)}")
            
            if cs.button("💾 Sauvegarder"):
                pre = get_preinscriptions_db()
                to_save = edited.copy()
                for _, r in to_save.iterrows():
                    if r["Nom"] and r["Année Naissance"]: save_athlete(r["Nom"], r["Prénom"], "", r["Année Naissance"], r["Poids (kg)"], r["Sexe (M/F)"])
                final_save = to_save.rename(columns={"Compétition": "Competition_Cible", "Nom": "Nom", "Prénom": "Prenom", "Année Naissance": "Annee", "Poids (kg)": "Poids", "Sexe (M/F)": "Sexe", "Catégorie Calculée": "Categorie"})
                save_data(pd.concat([pre, final_save[["Competition_Cible", "Nom", "Prenom", "Annee", "Poids", "Sexe", "Categorie"]]], ignore_index=True), "PreInscriptions", [])
                st.success("Sauvegardé"); st.session_state['inscr_df'] = pd.DataFrame(columns=edited.columns)

            st.write("---")
            if st.button("🗑️ Reset Live"): save_data(pd.DataFrame(columns=live.columns), "Feuille 1", []); st.rerun()

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
