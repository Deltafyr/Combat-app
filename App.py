
import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURATION & DESIGN COMPACT (CSS) ---
st.set_page_config(page_title="Fight Tracker", page_icon="🥊", layout="wide")

# Injection de CSS pour réduire la police sur mobile
st.markdown("""
    <style>
        /* Réduire la taille globale des textes */
        html, body, [class*="css"]  {
            font-family: 'Roboto', sans-serif;
            font-size: 14px; 
        }
        h1 { font-size: 1.5rem !important; }
        h2 { font-size: 1.2rem !important; }
        h3 { font-size: 1.0rem !important; }
        
        /* Réduire les marges entre les éléments pour gagner de la place */
        .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }
        /* Design des cartes compactes */
        .combat-card {
            background-color: #1E1E1E;
            border-radius: 6px;
            padding: 8px 12px;
            margin-bottom: 6px;
            border-left: 4px solid #555;
            box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        }
        .combat-info { display: flex; justify-content: space-between; align-items: center; }
        .combat-num { font-weight: bold; font-size: 1.1em; color: #eee; }
        .combat-aire { background: #333; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; color: #FFD700; }
        .fighter-name { font-size: 1.2em; font-weight: 600; margin-top: 4px; color: #fff; }
        .status-badge { font-size: 0.75em; color: #aaa; margin-top: 2px; }
    </style>
""", unsafe_allow_html=True)

# --- CONNEXION ---
def get_connection():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("suivi_combats").sheet1 
    return sheet

def get_data():
    sh = get_connection()
    data = sh.get_all_records()
    df = pd.DataFrame(data)
    # Structure de base si vide
    required_cols = ["Combattant", "Aire", "Numero", "Casque", "Statut", "Palmares"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = "" # Créer la colonne vide si elle manque
    return df

def save_full_dataframe(df):
    sh = get_connection()
    sh.clear()
    sh.update([df.columns.values.tolist()] + df.values.tolist())

# --- INTERFACE ---
tab_public, tab_palmares, tab_coach = st.tabs(["📢 LISTE", "🏆 PALMARÈS", "🛠️ COACH"])

# ==========================================
# 1. ONGLET PUBLIC (COMPACT)
# ==========================================
with tab_public:
    if st.button("🔄", key="refresh_pub", help="Actualiser"):
        st.rerun()
    
    try:
        df = get_data()
        if not df.empty:
            # Séparation : Active vs Palmares
            # On considère actif si la colonne Palmares est vide
            df_active = df[df['Palmares'] == ""]
            
            # Nettoyage
            df_active['Numero'] = pd.to_numeric(df_active['Numero'], errors='coerce').fillna(0)
            df_active['Aire'] = pd.to_numeric(df_active['Aire'], errors='coerce').fillna(0)
            df_active = df_active[df_active['Numero'] > 0] # On cache les fiches non remplies
            df_sorted = df_active.sort_values(by=['Numero', 'Aire'])
            
            for i, row in df_sorted.iterrows():
                icon = "🔴" if row['Casque'] == "Rouge" else "🔵"
                statut_txt = row['Statut']
                border_color = "#00C853" if "En cours" in statut_txt else "#555"
                if "En cours" in statut_txt: border_color = "#FF4B4B" # Rouge si en cours
                
                st.markdown(f"""
                <div class="combat-card" style="border-left: 4px solid {border_color};">
                    <div class="combat-info">
                        <span class="combat-num">Cbt #{int(row['Numero'])}</span>
                        <span class="combat-aire">Aire {int(row['Aire'])}</span>
                    </div>
                    <div class="fighter-name">{icon} {row['Combattant']}</div>
                    <div class="status-badge">{statut_txt}</div>
                </div>
                """, unsafe_allow_html=True)
                
            if df_sorted.empty:
                st.caption("Aucun combat actif dans la liste d'attente.")
                
        else:
            st.info("Liste vide.")
    except Exception as e:
        st.error(f"Erreur: {e}")

# ==========================================
# 2. ONGLET PALMARÈS (RÉSULTATS FINAUX)
# ==========================================
with tab_palmares:
    st.header("🏆 Résultats du Club")
    if st.button("🔄", key="refresh_pal"):
        st.rerun()
        
    try:
        df = get_data()
        if not df.empty:
            # On ne garde que ceux qui ont un Palmares rempli
            df_finished = df[df['Palmares'] != ""]
            
            if not df_finished.empty:
                # Ordre : Or d'abord, Argent ensuite...
                colors = {"🥇 Or": 1, "🥈 Argent": 2, "🥉 Bronze": 3, "🍫 4ème": 4, "❌ Non classé": 5}
                df_finished['Order'] = df_finished['Palmares'].map(colors).fillna(99)
                df_finished = df_finished.sort_values('Order')
                
                for i, row in df_finished.iterrows():
                    medaille = row['Palmares']
                    style_medaille = "color: #FFD700;" if "Or" in medaille else "color: #EEE;"
                    
                    st.markdown(f"""
                    <div style="background:#222; padding:10px; border-radius:5px; margin-bottom:5px; border:1px solid #444;">
                        <div style="font-size:1.1em; font-weight:bold; {style_medaille}">{medaille}</div>
                        <div style="font-size:1.3em; color:white;">{row['Combattant']}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Aucun résultat final pour l'instant.")
    except:
        pass

# ==========================================
# 3. ONGLET COACH (GESTION ÉVOLUTION)
# ==========================================
with tab_coach:
    password = st.text_input("🔑 Code Coach", type="password")
    
    if password == "1234":
        current_df = get_data()
        
        # --- A. ACTION RAPIDE (WIZARD) ---
        st.subheader("⚡ Gestion des Résultats")
        st.caption("Sélectionnez un boxeur actif pour mettre à jour sa situation.")
        
        # On liste seulement les boxeurs actifs (sans palmarès)
        active_fighters = current_df[current_df['Palmares'] == ""]['Combattant'].tolist()
        
        if active_fighters:
            selected_fighter = st.selectbox("Boxeur", active_fighters)
            
            # On récupère les infos actuelles de ce boxeur
            fighter_row = current_df[current_df['Combattant'] == selected_fighter].iloc[0]
            current_num = fighter_row['Numero']
            current_aire = fighter_row['Aire']
            
            st.info(f"Actuellement : Combat #{current_num} (Aire {current_aire})")
            
            col_win, col_end = st.columns(2)
            
            # --- SCÉNARIO 1 : VICTOIRE -> SUITE DU TOURNOI ---
            with col_win:
                with st.popover("✅ VICTOIRE (Continue)"):
                    st.markdown("### Prochain Combat ?")
                    new_num = st.number_input("Nouveau N° Combat", min_value=1, step=1)
                    new_aire = st.number_input("Nouvelle Aire", min_value=1, step=1, value=int(current_aire) if current_aire else 1)
                    new_casque = st.radio("Nouveau Casque", ["Rouge", "Bleu"])
                    
                    if st.button("Valider la Qualification"):
                        # Logique : On met à jour la ligne existante
                        idx = current_df[current_df['Combattant'] == selected_fighter].index[0]
                        current_df.at[idx, 'Numero'] = new_num
                        current_df.at[idx, 'Aire'] = new_aire
                        current_df.at[idx, 'Casque'] = new_casque
                        current_df.at[idx, 'Statut'] = "A venir" # Reset statut
                        save_full_dataframe(current_df)
                        st.toast(f"{selected_fighter} passe au combat #{new_num} !")
                        st.rerun()

            # --- SCÉNARIO 2 : FIN DE PARCOURS (PODIUM OU DÉFAITE) ---
            with col_end:
                with st.popover("🏁 FIN DU TOURNOI"):
                    st.markdown("### Résultat Final ?")
                    resultat = st.selectbox("Classement", ["🥇 Or", "🥈 Argent", "🥉 Bronze", "🍫 4ème", "❌ Non classé"])
                    
                    if st.button("Archiver dans Palmarès"):
                        # Logique : On met le palmarès et on vide le numéro pour sortir du tri
                        idx = current_df[current_df['Combattant'] == selected_fighter].index[0]
                        current_df.at[idx, 'Palmares'] = resultat
                        current_df.at[idx, 'Statut'] = "Terminé"
                        save_full_dataframe(current_df)
                        st.toast(f"{selected_fighter} termine {resultat} !")
                        st.rerun()

        else:
            st.warning("Plus aucun combattant actif !")

        st.divider()

        # --- B. INITIALISATION (LISTE MATIN) ---
        with st.expander("📝 Initialiser l'équipe (Matin)"):
            team_text = st.text_area("Liste noms", height=100)
            if st.button("Créer fiches"):
                names = team_text.split('\n')
                new_rows = []
                for name in names:
                    if name.strip():
                        new_rows.append({
                            "Combattant": name.strip(), "Aire": 0, "Numero": 0, 
                            "Casque": "Rouge", "Statut": "A venir", "Palmares": ""
                        })
                if new_rows:
                    final = pd.concat([current_df, pd.DataFrame(new_rows)], ignore_index=True)
                    save_full_dataframe(final)
                    st.rerun()

        # --- C. TABLEAU TOTAL (CORRECTION) ---
        with st.expander("🛠️ Tableau Complet (Correction)"):
             # ASTUCE : On convertit en numérique avant l'éditeur pour éviter le bug de saisie
            current_df['Aire'] = pd.to_numeric(current_df['Aire'], errors='coerce').fillna(0)
            current_df['Numero'] = pd.to_numeric(current_df['Numero'], errors='coerce').fillna(0)
            
            edited_df = st.data_editor(current_df, key="editor_full", num_rows="dynamic")
            if st.button("Sauvegarder Tableau"):
                save_full_dataframe(edited_df)
                st.rerun()
