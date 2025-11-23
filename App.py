import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

# --- CONFIGURATION ---
st.set_page_config(page_title="Fight Tracker", page_icon="🥊", layout="wide") # Layout wide pour le grand tableau

# --- CONNEXION SECURISEE ---
def get_connection():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("suivi_combats").sheet1 
    return sheet

# --- GESTION DONNÉES ---
def get_data():
    sh = get_connection()
    data = sh.get_all_records()
    # On s'assure d'avoir les bonnes colonnes même si vide
    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame(columns=["Combattant", "Aire", "Numero", "Casque", "Statut"])
    return df

def save_full_dataframe(df):
    """Écrase et remplace tout le Google Sheet avec les nouvelles données modifiées"""
    sh = get_connection()
    sh.clear() # On efface tout
    # On remet les titres et les données
    sh.update([df.columns.values.tolist()] + df.values.tolist())

# --- PARSER INTELLIGENT ---
def magic_parser(raw_text, team_names_list):
    found_data = []
    lines = raw_text.split('\n')
    
    for fighter in team_names_list:
        fighter = fighter.strip()
        if not fighter: continue
        
        for line in lines:
            if fighter.upper() in line.upper():
                # Recherche chiffres
                numbers = re.findall(r'\d+', line)
                est_aire = 0
                est_num = 0
                
                if len(numbers) >= 2:
                    nums = [int(n) for n in numbers]
                    est_aire = min(nums)
                    est_num = max(nums)
                elif len(numbers) == 1:
                    est_num = int(numbers[0])

                found_data.append({
                    "Combattant": fighter,
                    "Aire": est_aire,
                    "Numero": est_num,
                    "Casque": "Rouge", # Valeur par défaut
                    "Statut": "A venir"
                })
                break # On arrête de chercher ce boxeur une fois trouvé
    return found_data

# --- INTERFACE ---

# Onglets principaux
tab_public, tab_coach = st.tabs(["📢 Écran Public", "🛠️ Espace Coach (Admin)"])

# ==========================================
# ONGLET 1 : PUBLIC (Lecture Seule)
# ==========================================
with tab_public:
    st.header("🥊 Ordre de Passage")
    if st.button("🔄 Actualiser l'affichage"):
        st.rerun()
        
    try:
        df = get_data()
        if not df.empty:
            # Conversion pour tri
            df['Numero'] = pd.to_numeric(df['Numero'], errors='coerce')
            df['Aire'] = pd.to_numeric(df['Aire'], errors='coerce')
            df_sorted = df.sort_values(by=['Numero', 'Aire'])
            
            # Affichage "Cartes" pour mobile
            cols = st.columns(1) 
            for i, row in df_sorted.iterrows():
                if row['Statut'] != "Terminé": # On cache les terminés du public
                    icon = "🔴" if row['Casque'] == "Rouge" else "🔵"
                    statut_icon = "⏳" if row['Statut'] == "A venir" else "🔥 EN COURS"
                    style_border = "2px solid #FF4B4B" if row['Statut'] == "En cours" else "1px solid #444"
                    
                    st.markdown(f"""
                    <div style="padding: 15px; border-radius: 8px; border: {style_border}; margin-bottom: 10px; background-color: #0E1117;">
                        <div style="display:flex; justify-content:space-between;">
                            <h2 style="margin:0;">Combat #{row['Numero']}</h2>
                            <h3 style="margin:0; color: orange;">Aire {row['Aire']}</h3>
                        </div>
                        <div style="font-size:1.5em; margin-top:10px;">{icon} <strong>{row['Combattant']}</strong></div>
                        <div style="margin-top:5px; font-style:italic;">{statut_icon} {row['Statut']}</div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("Aucun combat affiché.")
    except Exception as e:
        st.error(f"Erreur lecture : {e}")

# ==========================================
# ONGLET 2 : COACH (Sécurisé)
# ==========================================
with tab_coach:
    password = st.text_input("🔑 Mot de passe Coach", type="password")
    
    if password == "1234": # VOTRE MOT DE PASSE
        st.success("Mode Admin Activé")
        
        # --- SECTION A : ÉDITION LIVE DU TABLEAU ---
        st.subheader("1. Gérer les Combats Existants")
        st.info("Modifiez directement les cases ci-dessous (Aire, Casque, Statut).")
        
        # Chargement données actuelles
        current_df = get_data()
        
        # TABLEAU ÉDITABLE (Le cœur de la V5)
        edited_df = st.data_editor(
            current_df, 
            num_rows="dynamic", # Permet d'ajouter/supprimer des lignes
            column_config={
                "Casque": st.column_config.SelectboxColumn("Casque", options=["Rouge", "Bleu"]),
                "Statut": st.column_config.SelectboxColumn("Statut", options=["A venir", "En cours", "Terminé"]),
                "Numero": st.column_config.NumberColumn("N°", step=1),
                "Aire": st.column_config.NumberColumn("Aire", step=1)
            },
            use_container_width=True,
            key="editor"
        )
        
        col_save, col_cancel = st.columns([1, 4])
        if col_save.button("💾 SAUVEGARDER LES MODIFICATIONS", type="primary"):
            save_full_dataframe(edited_df)
            st.toast("Google Sheet mis à jour avec succès !", icon="✅")
            st.rerun()

        st.divider()
        
        # --- SECTION B : IMPORT AUTOMATIQUE ---
        st.subheader("2. Importation Rapide (Magic Parser)")
        
        with st.expander("Ouvrir l'outil d'importation"):
            col_team, col_site = st.columns(2)
            
            # ÉTAPE 1 : LA LISTE DU JOUR
            team_input = col_team.text_area(
                "A. Liste de nos Combattants (1 par ligne)", 
                placeholder="Dupont\nMartin\nRodriguez",
                height=200
            )
            
            # ÉTAPE 2 : LE TEXTE DU SITE
            site_input = col_site.text_area(
                "B. Copier-coller du site Web", 
                placeholder="Collez ici tout le texte de la page FFKMDA...",
                height=200
            )
            
            if st.button("🔍 Analyser et Préparer"):
                if team_input and site_input:
                    team_list = team_input.split('\n')
                    # On lance la recherche
                    propositions = magic_parser(site_input, team_list)
                    
                    if propositions:
                        st.session_state['import_propositions'] = propositions
                        st.success(f"{len(propositions)} correspondances trouvées !")
                    else:
                        st.warning("Aucune correspondance trouvée.")
            
            # ÉTAPE 3 : VÉRIFICATION AVANT AJOUT
            if 'import_propositions' in st.session_state:
                st.write("---")
                st.write("👀 **Vérifiez les données avant de les fusionner :**")
                
                # On transforme la liste de propositions en DataFrame pour l'éditer aussi !
                prop_df = pd.DataFrame(st.session_state['import_propositions'])
                
                edited_props = st.data_editor(
                    prop_df, 
                    key="import_editor",
                    num_rows="dynamic"
                )
                
                if st.button("➕ AJOUTER CES COMBATS À LA LISTE PRINCIPALE"):
                    # On fusionne avec les données existantes
                    final_df = pd.concat([current_df, edited_props], ignore_index=True)
                    # On sauvegarde tout
                    save_full_dataframe(final_df)
                    del st.session_state['import_propositions'] # On vide la mémoire
                    st.balloons()
                    st.success("Import réussi ! La liste principale est à jour.")
                    st.rerun()
