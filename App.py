import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import urllib.parse
import time

# --- CONFIGURATION & DESIGN ---
st.set_page_config(page_title="Fight Tracker V25", page_icon="🥊", layout="wide")

st.markdown("""
    <style>
        html, body, [class*="css"]  { font-family: 'Roboto', sans-serif; font-size: 14px; }
        .combat-card {
            background: linear-gradient(145deg, #1E1E1E, #252525);
            border-radius: 8px; padding: 12px; margin-bottom: 8px; 
            border-left: 4px solid #555; box-shadow: 0 2px 5px rgba(0,0,0,0.3);
        }
        .header-line { display: flex; justify-content: space-between; align-items: baseline; }
        .combat-num { font-style: italic; font-size: 1.1em; color: #ddd; font-weight:bold;}
        .tour-info { font-size: 0.85em; color: #aaa; margin-left: 5px; }
        .combat-aire { background: #FFD700; color:black; padding: 2px 8px; border-radius: 10px; font-size: 0.85em; font-weight: bold; }
        
        .fighter-line { margin-top: 8px; display:flex; align-items:center; justify-content:space-between;}
        .fighter-name { font-size: 1.3em; font-weight: 700; color: #fff; }
        .honor-title { font-size: 0.8em; color: #FFD700; font-style: italic; display:block; opacity:0.8;}
        
        .medal-badge { font-size: 1.2em; margin-left:5px;}
        .status-badge { font-size: 0.75em; color: #888; margin-top: 6px; text-transform: uppercase; letter-spacing: 1px;}
        .medal-pill { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; margin-right: 5px; margin-bottom: 5px; color:black;}
        .gold { background: #FFD700; } .silver { background: #C0C0C0; } .bronze { background: #CD7F32; }
        
        /* Indicateurs coins */
        .corner-red { border-left: 3px solid #FF4B4B; padding-left:5px; }
        .corner-blue { border-left: 3px solid #2196F3; padding-left:5px; }
    </style>
""", unsafe_allow_html=True)

# --- CONNEXION ROBUSTE (CACHE RESOURCE) ---
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

# --- GESTION BDD SECURISEE ---
def get_worksheet_safe(name, expected_cols):
    """Ouvre un onglet et le crée s'il n'existe pas, avec les bons titres"""
    client = get_client()
    try: sh = client.open("suivi_combats")
    except: return None
    
    try: ws = sh.worksheet(name)
    except: 
        # Création si inexistant
        ws = sh.add_worksheet(name, 1000, len(expected_cols)+2)
        if expected_cols: ws.append_row(expected_cols)
        time.sleep(1) # Pause pour laisser Google respirer
    return ws

# --- LECTURE AVEC CACHE (TTL 5s) ---
# Cela empêche l'erreur "APIError" en réduisant les appels
@st.cache_data(ttl=5)
def fetch_data(sheet_name, cols):
    ws = get_worksheet_safe(sheet_name, cols)
    if ws:
        try: return pd.DataFrame(ws.get_all_records())
        except: return pd.DataFrame(columns=cols) # Retourne vide si erreur lecture
    return pd.DataFrame(columns=cols)

def get_live_data():
    df = fetch_data("Feuille 1", ["Combattant", "Aire", "Numero", "Casque", "Statut", "Palmares", "Details_Tour", "Medaille_Actuelle"])
    # Sécurité colonnes
    cols = ["Combattant", "Aire", "Numero", "Casque", "Statut", "Palmares", "Details_Tour", "Medaille_Actuelle"]
    for c in cols: 
        if c not in df.columns: df[c] = ""
    return df

def get_history_data():
    return fetch_data("Historique", ["Competition", "Date", "Combattant", "Medaille"])

def get_athletes_db():
    return fetch_data("Athletes", ["Nom", "Titre_Honorifique", "Annee_Naissance", "Poids", "Sexe"])

def get_calendar_db():
    # CORRECTION BUG : On définit bien les colonnes ici
    return fetch_data("Calendrier", ["Nom_Competition", "Date_Prevue"])

def get_preinscriptions_db():
    return fetch_data("PreInscriptions", ["Competition_Cible", "Nom", "Annee", "Poids", "Sexe", "Categorie"])

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

# --- ECRITURE (Pas de cache ici) ---
def save_data(df, sheet_name, cols_def):
    ws = get_worksheet_safe(sheet_name, cols_def)
    if ws:
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.values.tolist())
        # Invalider le cache pour forcer le rechargement au prochain clic
        fetch_data.clear()

# --- INTERFACE ---
tab_public, tab_profil, tab_historique, tab_coach = st.tabs(["📢 LIVE", "👤 PROFILS", "🏛️ CLUB", "🛠️ COACH"])

# 1. LIVE
with tab_public:
    st.caption("Appuyez sur R pour rafraîchir")
    if st.button("🔄 Rafraîchir", key="ref_pub", use_container_width=True): st.rerun()
    
    df = get_live_data()
    df_ath = get_athletes_db()
    
    if not df.empty:
        df['Numero'] = pd.to_numeric(df['Numero'], errors='coerce').fillna(0)
        df['Aire'] = pd.to_numeric(df['Aire'], errors='coerce').fillna(0)
        df = df[df['Numero'] > 0].sort_values(by=['Numero', 'Aire'])
        
        titre_compet = st.session_state.get('Config_Compet', "Compétition en cours")
        st.markdown(f"<h2 style='text-align:center; color:#FFD700;'>{titre_compet}</h2>", unsafe_allow_html=True)
        
        if df.empty: st.info("Aucun combat actif.")
        
        for i, row in df.iterrows():
            if row['Statut'] != "Terminé":
                # Couleurs et Style
                is_red = (row['Casque'] == "Rouge")
                corner_class = "corner-red" if is_red else "corner-blue"
                border = "#FF4B4B" if "En cours" in row['Statut'] else "#444"
                bg_style = "box-shadow: 0 0 10px rgba(255, 75, 75, 0.3);" if "En cours" in row['Statut'] else ""
                
                # Titre Bio
                titre = ""
                if not df_ath.empty and 'Nom' in df_ath.columns:
                    infos = df_ath[df_ath['Nom'] == row['Combattant']]
                    if not infos.empty: titre = infos.iloc[0]['Titre_Honorifique']
                
                # Badge Médaille
                med_html = f"<span class='medal-badge'>{row['Medaille_Actuelle']}</span>" if row['Medaille_Actuelle'] else ""

                st.markdown(f"""
                <div class="combat-card" style="border-left: 4px solid {border}; {bg_style}">
                    <div class="header-line">
                        <div>
                            <span class="combat-num">Combat #{int(row['Numero'])}</span>
                            <span class="tour-info">{row['Details_Tour']}</span>
                        </div>
                        <span class="combat-aire">AIRE {int(row['Aire'])}</span>
                    </div>
                    <div class="fighter-line">
                        <div class="{corner_class}" style="padding-left:10px; width:100%;">
                            <span class="fighter-name">{row['Combattant']} {med_html}</span>
                            <span class="honor-title">{titre}</span>
                        </div>
                    </div>
                    <div class="status-badge">{row['Statut']}</div>
                </div>
                """, unsafe_allow_html=True)
    else: st.info("Chargement...")

# 2. PROFILS
with tab_profil:
    st.header("Fiches Athlètes")
    hist = get_history_data()
    ath = get_athletes_db()
    
    names = set(hist['Combattant']) if not hist.empty and 'Combattant' in hist.columns else set()
    if not ath.empty and 'Nom' in ath.columns: names.update(ath['Nom'])
    
    if names:
        search = st.selectbox("Rechercher un athlète", sorted(list(names)))
        bio, poids, cat = "", "", ""
        if not ath.empty and 'Nom' in ath.columns:
            i = ath[ath['Nom'] == search]
            if not i.empty: 
                bio = i.iloc[0]['Titre_Honorifique']
                poids = i.iloc[0]['Poids']
        
        st.markdown(f"<h2 style='color:#FFD700'>{search}</h2>", unsafe_allow_html=True)
        if bio: st.markdown(f"**{bio}**")
        if poids: st.caption(f"Poids enregistré : {poids}kg")
        st.divider()
        
        if not hist.empty and 'Combattant' in hist.columns:
            my = hist[hist['Combattant'] == search].sort_values('Date', ascending=False)
            for _, r in my.iterrows():
                med = r['Medaille']
                c = "gold" if "Or" in med else "silver" if "Argent" in med else "bronze"
                st.markdown(f"<div><span class='medal-pill {c}'>{med}</span> <strong>{r['Competition']}</strong> <small>({r['Date']})</small></div>", unsafe_allow_html=True)

# 3. HISTORIQUE
with tab_historique:
    st.header("Palmarès Global")
    h = get_history_data()
    if not h.empty and 'Date' in h.columns:
        st.dataframe(h.sort_values('Date', ascending=False), use_container_width=True, hide_index=True)

# 4. COACH
with tab_coach:
    if st.text_input("Code", type="password") == "1234":
        
        # --- CALENDRIER ---
        with st.expander("📅 Calendrier Saison", expanded=False):
            c1, c2, c3 = st.columns([3, 2, 1])
            n = c1.text_input("Nom")
            d = c2.date_input("Date")
            if c3.button("Ajouter"):
                cal = get_calendar_db()
                new = pd.DataFrame([{"Nom_Competition": n, "Date_Prevue": str(d)}])
                save_data(pd.concat([cal, new], ignore_index=True) if not cal.empty else new, "Calendrier", ["Nom_Competition", "Date_Prevue"])
                st.success("Ajouté"); st.rerun()
            
            cal = get_calendar_db()
            if not cal.empty:
                ed = st.data_editor(cal, num_rows="dynamic")
                if st.button("💾 Save Cal"): save_data(ed, "Calendrier", ["Nom_Competition", "Date_Prevue"]); st.rerun()

        opts = get_valid_competitions()

        # --- INSCRIPTIONS ---
        with st.expander("📝 Inscriptions", expanded=False):
            if 'inscr_df' not in st.session_state:
                st.session_state['inscr_df'] = pd.DataFrame(columns=["Compétition", "Nom Complet", "Année Naissance", "Poids (kg)", "Sexe (M/F)", "Catégorie Calculée"])
            
            ed_i = st.data_editor(st.session_state['inscr_df'], num_rows="dynamic", column_config={
                "Compétition": st.column_config.SelectboxColumn(options=opts, required=True),
                "Sexe (M/F)": st.column_config.SelectboxColumn(options=["M", "F"], required=True),
                "Année Naissance": st.column_config.NumberColumn(format="%d"),
                "Poids (kg)": st.column_config.NumberColumn(format="%.1f")
            }, use_container_width=True)
            
            c1, c2, c3 = st.columns(3)
            if c1.button("Calculer"):
                for i, r in ed_i.iterrows():
                    if r["Année Naissance"] and r["Poids (kg)"]:
                        ed_i.at[i, "Catégorie Calculée"] = calculer_categorie(r["Année Naissance"], r["Poids (kg)"], r.get("Sexe (M/F)", "M"))
                st.session_state['inscr_df'] = ed_i; st.rerun()
            
            if c3.button("💾 Sauvegarder"):
                # Save to PreInscriptions
                pre = get_preinscriptions_db()
                # Mapping
                to_save = ed_i.rename(columns={"Compétition": "Competition_Cible", "Nom Complet": "Nom", "Année Naissance": "Annee", "Poids (kg)": "Poids", "Sexe (M/F)": "Sexe", "Catégorie Calculée": "Categorie"})
                save_data(pd.concat([pre, to_save], ignore_index=True) if not pre.empty else to_save, "PreInscriptions", ["Competition_Cible", "Nom", "Annee", "Poids", "Sexe", "Categorie"])
                st.success("Sauvegardé"); st.session_state['inscr_df'] = pd.DataFrame(columns=ed_i.columns) # Reset

        st.divider()

        # --- CONFIG LIVE ---
        with st.expander("⚙️ Config Live", expanded=True):
            c1, c2 = st.columns(2)
            nom = c1.selectbox("Événement", opts)
            dt = c2.date_input("Date", st.session_state.get('Config_Date', datetime.today()))
            st.session_state['Config_Compet'] = nom
            st.session_state['Config_Date'] = dt
            
            # Checkbox qualif
            qualif = st.checkbox("Qualificatif ?")
            tgt = None
            if qualif: tgt = st.selectbox("Vers", opts, index=0)
            st.session_state['Target_Compet'] = tgt

            if st.button("📥 Importer Inscrits"):
                pre = get_preinscriptions_db()
                if not pre.empty:
                    sub = pre[pre['Competition_Cible'] == nom]
                    if not sub.empty:
                        cur = get_live_data()
                        rows = []
                        for _, r in sub.iterrows():
                            if r['Nom'] and (cur.empty or r['Nom'] not in cur['Combattant'].values):
                                rows.append({"Combattant": r['Nom'], "Aire":0, "Numero":0, "Casque":"Rouge", "Statut":"A venir", "Palmares":"", "Details_Tour":"", "Medaille_Actuelle":""})
                        if rows: 
                            save_data(pd.concat([cur, pd.DataFrame(rows)], ignore_index=True), "Feuille 1", [])
                            st.success("Import OK"); st.rerun()
                    else: st.warning("Personne inscrit pour ça.")
                else: st.warning("Base inscriptions vide.")

        # --- GESTION LIVE ---
        st.subheader("⚡ Gestion Live")
        live = get_live_data()
        act = live[live['Statut'] != "Terminé"]['Combattant'].tolist() if not live.empty else []
        
        if act:
            sel = st.selectbox("Boxeur", act)
            idx = live[live['Combattant'] == sel].index[0]
            r = live.iloc[idx]
            with st.form("upd"):
                c1, c2 = st.columns(2)
                nn = c1.number_input("N°", value=int(r['Numero']) if r['Numero'] else 0)
                nm = c2.selectbox("Résultat", ["", "🥇 Or", "🥈 Argent", "🥉 Bronze", "🍫 4ème", "❌ Non classé"])
                tour = st.text_input("Tour (ex: Finale)", value=str(r['Details_Tour']))
                
                if st.form_submit_button("✅ Mise à Jour"):
                    live.at[idx, 'Numero'] = nn
                    live.at[idx, 'Medaille_Actuelle'] = nm
                    live.at[idx, 'Details_Tour'] = tour
                    save_data(live, "Feuille 1", []); st.rerun()
                if st.form_submit_button("🏁 Terminer"):
                    live.at[idx, 'Statut'] = "Terminé"
                    live.at[idx, 'Medaille_Actuelle'] = nm
                    live.at[idx, 'Palmares'] = nm
                    save_data(live, "Feuille 1", []); st.rerun()

        st.write("---")
        # --- CLÔTURE ---
        if st.button("🏁 CLÔTURER & TRAITER", type="primary"):
            hist = get_history_data()
            ath = get_athletes_db()
            pre = get_preinscriptions_db()
            new_a, new_q, rep = [], [], []
            
            for _, r in live.iterrows():
                res = r['Medaille_Actuelle'] if r['Medaille_Actuelle'] else r['Palmares']
                if res and r['Combattant']:
                    # Archive
                    new_a.append({"Competition": nom, "Date": str(dt), "Combattant": r['Combattant'], "Medaille": res})
                    rep.append(f"{res} {r['Combattant']}")
                    
                    # Qualif Auto
                    if tgt and res in ["🥇 Or", "🥈 Argent"]:
                        # Check doublon
                        exists = False
                        if not pre.empty:
                            match = pre[(pre['Nom'] == r['Combattant']) & (pre['Competition_Cible'] == tgt)]
                            if not match.empty: exists = True
                        
                        if not exists and not ath.empty:
                            inf = ath[ath['Nom'] == r['Combattant']]
                            if not inf.empty:
                                i = inf.iloc[0]
                                cat = calculer_categorie(i['Annee_Naissance'], i['Poids'], i['Sexe'])
                                new_q.append({"Competition_Cible": tgt, "Nom": r['Combattant'], "Annee": i['Annee_Naissance'], "Poids": i['Poids'], "Sexe": i['Sexe'], "Categorie": cat})

            if new_a: save_data(pd.concat([hist, pd.DataFrame(new_a)], ignore_index=True) if not hist.empty else pd.DataFrame(new_a), "Historique", ["Competition", "Date", "Combattant", "Medaille"])
            if new_q: save_data(pd.concat([pre, pd.DataFrame(new_q)], ignore_index=True) if not pre.empty else pd.DataFrame(new_q), "PreInscriptions", ["Competition_Cible", "Nom", "Annee", "Poids", "Sexe", "Categorie"])
            
            msg = urllib.parse.quote(f"🏆 *BILAN {nom}*\n\n" + "\n".join(sorted(rep)))
            st.link_button("📲 WhatsApp Bilan", f"https://wa.me/?text={msg}")
            st.success("Clôturé !")

        if st.button("🗑️ Vider Live"):
            save_data(pd.DataFrame(columns=live.columns), "Feuille 1", [])
            st.rerun()
