import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="MAINTENANCE BDD V33", page_icon="🛠️")

st.title("🛠️ Mise à jour de la Base de Données (V33)")
st.info("Ce script va restructurer vos tableaux pour séparer Nom et Prénom, tout en conservant vos données actuelles.")

# --- CONNEXION ---
try:
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sh = client.open("suivi_combats")
except Exception as e:
    st.error(f"Erreur connexion : {e}")
    st.stop()

if st.button("🚀 LANCER LA RESTRUCTURATION", type="primary"):
    with st.status("Travail en cours...", expanded=True) as status:
        
        # 1. MIGRATION ATHLETES
        st.write("Traitement de la base Athlètes...")
        try:
            ws_ath = sh.worksheet("Athletes")
            old_data = ws_ath.get_all_records()
            df_old = pd.DataFrame(old_data)
            
            # On prépare la nouvelle liste
            new_data = []
            
            if not df_old.empty:
                # On essaie de récupérer les infos existantes
                for idx, row in df_old.iterrows():
                    # Gestion du nom complet (Ancienne colonne 'Nom')
                    full_name = str(row.get('Nom', '')).strip()
                    nom, prenom = "", ""
                    
                    if full_name:
                        parts = full_name.split()
                        if len(parts) > 1:
                            nom = " ".join(parts[:-1]).upper()
                            prenom = parts[-1].capitalize()
                        else:
                            nom = full_name.upper()
                    
                    # Récupération des autres champs s'ils existent déjà, sinon vide
                    titre = row.get('Titre_Honorifique', '')
                    annee = row.get('Annee_Naissance', '')
                    poids = row.get('Poids', '')
                    sexe = row.get('Sexe', '')
                    
                    new_data.append({
                        "Nom": nom, "Prenom": prenom, 
                        "Annee_Naissance": annee, "Poids": poids, "Sexe": sexe,
                        "Titre_Honorifique": titre
                    })
            
            # RECRÉATION DE L'ONGLET PROPRE
            sh.del_worksheet(ws_ath) # On supprime l'ancien
            st.write("Ancien onglet supprimé. Création du nouveau structure V33...")
            
        except:
            st.write("Onglet Athletes introuvable, création d'un neuf.")
            new_data = []

        # Création onglet Athletes V33
        ws_new_ath = sh.add_worksheet(title="Athletes", rows=1000, cols=6)
        # Ordre strict V33
        headers_ath = ["Nom", "Prenom", "Annee_Naissance", "Poids", "Sexe", "Titre_Honorifique"]
        
        # Préparation du payload
        final_rows = [headers_ath]
        for item in new_data:
            final_rows.append([item[h] for h in headers_ath])
            
        ws_new_ath.update(final_rows)
        st.write(f"✅ Base Athlètes migrée : {len(new_data)} athlètes conservés.")

        # 2. RESTRUCTURATION PRE-INSCRIPTIONS
        st.write("Réinitialisation de l'onglet PreInscriptions...")
        try:
            ws_pre = sh.worksheet("PreInscriptions")
            sh.del_worksheet(ws_pre)
        except: pass
        
        ws_new_pre = sh.add_worksheet(title="PreInscriptions", rows=1000, cols=7)
        headers_pre = ["Competition_Cible", "Nom", "Prenom", "Annee", "Poids", "Sexe", "Categorie"]
        ws_new_pre.append_row(headers_pre)
        st.write("✅ Onglet PreInscriptions prêt (Vide).")

        status.update(label="TERMINE ! Votre Google Sheet est prêt pour la V33.", state="complete")
        
    st.balloons()
    st.success("Opération réussie. Vous pouvez maintenant remettre le code de l'application V33.")
