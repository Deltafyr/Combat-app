import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURATION ---
st.set_page_config(page_title="Fight Tracker", page_icon="🥊", layout="wide")

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
    if df.empty:
        return pd.DataFrame(columns=["Combattant", "Aire", "Numero", "Casque", "Statut"])
    return df

def save_full_dataframe(df):
    sh = get_connection()
    sh.clear()
    sh.update([df.columns.values.tolist()] + df.values.tolist())

# --- INTERFACE ---
tab_public, tab_coach = st.tabs(["📢 Écran Public", "🛠️ Espace Coach"])

# --- ONGLET PUBLIC (LECTURE) ---
with tab_public:
    st.header("🥊 Ordre de Passage")
    if st.button("🔄 Actualiser"):
        st.rerun()
    
    try:
        df = get_data()
        if not df.empty:
            # Nettoyage et Tri
            df['Numero'] = pd.to_numeric(df['Numero'], errors='coerce').fillna(999) # 999 si pas de numéro
            df['Aire'] = pd.to_numeric(df['Aire'], errors='coerce').fillna(0)
            
            # On ne montre que ceux qui ont un numéro de combat valide
            df_active = df[df['Numero'] < 999]
            df_sorted = df_active.sort_values(by=['Numero', 'Aire'])
            
            cols = st.columns(1) 
            for i, row in df_sorted.iterrows():
                if row['Statut'] != "Terminé":
                    icon = "🔴" if row['Casque'] == "Rouge" else "🔵"
                    statut_icon = "⏳" if row['Statut'] == "A venir" else "🔥 EN COURS"
                    border = "2px solid #FF4B4B" if row['Statut'] == "En cours" else "1px solid #444"
                    
                    st.markdown(f"""
                    <div style="padding: 15px; border-radius: 8px; border: {border}; margin-bottom: 10px; background-color: #0E1117;">
                        <div style="display:flex; justify-content:space-between;">
                            <h2 style="margin:0;">Combat #{int(row['Numero'])}</h2>
                            <h3 style="margin:0; color: orange;">Aire {int(row['Aire'])}</h3>
                        </div>
                        <div style="font-size:1.5em; margin-top:10px;">{icon} <strong>{row['Combattant']}</strong></div>
                        <div style="margin-top:5px; font-style:italic;">{statut_icon} {row['Statut']}</div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("Aucun combat affiché.")
    except Exception as e:
        st.error(f"Erreur : {e}")

# --- ONGLET COACH (ÉCRITURE RAPIDE) ---
with tab_coach:
    password = st.text_input("🔑 Mot de passe", type="password")
    
    if password == "1234":
        
        # PARTIE 1 : PRÉPARATION DE L'ÉQUIPE (MATIN)
        with st.expander("📝 1. Initialiser mon Équipe (À faire le matin)", expanded=False):
            st.caption("Collez ici la liste de vos boxeurs (un par ligne). L'appli va créer les fiches.")
            team_text = st.text_area("Liste des Noms", placeholder="Dupont\nMartin\nBenzema")
            
            if st.button("🚀 Créer les fiches vides"):
                if team_text:
                    current_df = get_data()
                    new_rows = []
                    names = team_text.split('\n')
                    
                    for name in names:
                        name = name.strip()
                        if name:
                            # On vérifie si le nom existe déjà pour pas faire de doublon
                            if not current_df.empty and name in current_df['Combattant'].values:
                                continue
                            
                            new_rows.append({
                                "Combattant": name,
                                "Aire": "", # Vide au début
                                "Numero": "", # Vide au début
                                "Casque": "Rouge",
                                "Statut": "A venir"
                            })
                    
                    if new_rows:
                        new_df = pd.DataFrame(new_rows)
                        final_df = pd.concat([current_df, new_df], ignore_index=True)
                        save_full_dataframe(final_df)
                        st.success(f"{len(new_rows)} fiches créées ! Allez remplir les numéros ci-dessous.")
                        st.rerun()
                    else:
                        st.warning("Aucun nouveau nom ajouté (ils existent peut-être déjà).")

        st.divider()

        # PARTIE 2 : TABLEAU DE BORD (JOURNÉE)
        st.subheader("2. Remplir & Gérer")
        st.info("Remplissez juste les colonnes 'Aire' et 'N°' au fur et à mesure.")
        
        current_df = get_data()
        
        edited_df = st.data_editor(
            current_df,
            num_rows="dynamic",
            column_config={
                "Combattant": st.column_config.TextColumn("Nom", disabled=True), # On bloque le nom pour pas faire d'erreur
                "Aire": st.column_config.NumberColumn("Aire", step=1, help="Mettez 0 si inconnu"),
                "Numero": st.column_config.NumberColumn("N° Cbt", step=1, help="Mettez 0 si inconnu"),
                "Casque": st.column_config.SelectboxColumn("Casque", options=["Rouge", "Bleu"]),
                "Statut": st.column_config.SelectboxColumn("Statut", options=["A venir", "En cours", "Terminé"]),
            },
            use_container_width=True,
            height=600, # Grand tableau confortable
            key="editor"
        )
        
        if st.button("💾 SAUVEGARDER LES MODIFICATIONS", type="primary", use_container_width=True):
            save_full_dataframe(edited_df)
            st.toast("Mise à jour effectuée !", icon="✅")
            st.rerun()
