from flask import Flask, request, jsonify
import sqlite3
import os
import init_faiss_v4  # <-- On pointe vers le nouveau cerveau
import sys
import json
import win32security
import pywintypes
import ntsecuritycon
import re
from loguru import logger

# --- CONFIGURATION LOGURU ---
logger.remove()
logger.add(sys.stderr, colorize=True, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
# [MODIFIER_ICI] Chemin des logs.
logger.add("C:/AGENT_IA/log_webhook_propre.log", rotation="5 MB", retention="10 days", encoding="utf-8", level="DEBUG")

app = Flask(__name__)
CHEMIN_BDD = "chadibot_v4.db"  # <-- La nouvelle base de données
# [MODIFIER_ICI] Lettre du lecteur mappé sur le serveur IA pointant vers le serveur de fichiers
RACINE_SCAN = "S:\\\\"

EXTENSIONS_FANTOMES = {".tmp", ".lock", ".bak", ".old"}
LISTE_VIP = {".pdf", ".docx", ".doc", ".txt", ".pptx", ".ppt", ".md", ".ps1", ".py", ".bat", ".cmd"}
CACHE_SID_NOM = {}



def obtenir_groupes_dossier(chemin_dossier: str) -> list:
    """Récupère les droits NTFS avec repli automatique sur le dossier parent (Anti-Fichiers Fantômes)."""
    groupes_autorises = []
    
    # [MODIFIER_ICI] Conversion du chemin du lecteur mappé (S:) vers le chemin physique du serveur de fichiers (D:\Services\)
    # Utilisé pour interroger les ACLs distantes si nécessaire.
    chemin_local = re.sub(r'(?i)^s:\\', r'D:\\Services\\', chemin_dossier)
    chemin_local = os.path.normpath(chemin_local)
    
    chemin_actuel = chemin_local
    
    # On remonte l'arbre des dossiers jusqu'à trouver un chemin qui existe (max: racine D:\)
    while chemin_actuel and len(chemin_actuel) > 3:
        try:
            sd = win32security.GetFileSecurity(chemin_actuel, win32security.DACL_SECURITY_INFORMATION)
            dacl = sd.GetSecurityDescriptorDacl()
            
            if dacl is None: return ["Tout_le_monde"]
            
            for i in range(dacl.GetAceCount()):
                ace = dacl.GetAce(i)
                if ace[0][0] == win32security.ACCESS_ALLOWED_ACE_TYPE and (ace[1] & ntsecuritycon.FILE_READ_DATA):
                    sid_str = win32security.ConvertSidToStringSid(ace[2])
                    if sid_str not in CACHE_SID_NOM:
                        try:
                            nom, domaine, _ = win32security.LookupAccountSid(None, ace[2])
                            CACHE_SID_NOM[sid_str] = f"{domaine}\\{nom}"
                        except:
                            CACHE_SID_NOM[sid_str] = f"SID_ORPHELIN_{sid_str}"
                    groupes_autorises.append(CACHE_SID_NOM[sid_str])
                    
            return list(set(groupes_autorises))
            
        except Exception as e:
            # Si le fichier/dossier est introuvable (Erreur 3 ou 2) ou verrouillé
            # On coupe le dernier élément du chemin pour tester le dossier parent
            parent = os.path.dirname(chemin_actuel)
            
            # Sécurité pour ne pas boucler à l'infini si on arrive tout en haut
            if parent == chemin_actuel: 
                break
                
            chemin_actuel = parent # On retente avec le parent !
            
    logger.error(f"Erreur NTFS irrécupérable (même sur le parent) pour {chemin_local}")
    return []

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data: return jsonify({"erreur": "Aucune donnée"}), 400

    chemin_fichier = data.get('fichier')
    evenement = data.get('evenement')
    if not chemin_fichier: return jsonify({"erreur": "Chemin manquant"}), 400

    nom_fichier = os.path.basename(chemin_fichier)
    chemin_dossier = os.path.dirname(chemin_fichier)
    
    # Filtres anti-bruit
    if nom_fichier.startswith("~$"): return jsonify({"statut": "ignoré"}), 200
    _, ext = os.path.splitext(nom_fichier)
    ext = ext.lower()
    if ext in EXTENSIONS_FANTOMES: return jsonify({"statut": "ignoré"}), 200

    est_vip = 1 if ext in LISTE_VIP else 0
    chemin_relatif = chemin_fichier.replace(RACINE_SCAN, "").lstrip("\\")

    # --- L'ACTIVATION DU MODE TEMPS RÉEL (ZÉRO BLOCAGE) ---
    conn = sqlite3.connect(CHEMIN_BDD)
    conn.execute('pragma journal_mode=wal') 
    cursor = conn.cursor()
    
    try:
        # 1. Gestion du Dossier Parent
        cursor.execute("SELECT id FROM dossiers WHERE chemin_dossier = ?", (chemin_dossier,))
        dossier_row = cursor.fetchone()
        
        if dossier_row:
            dossier_id = dossier_row[0]
        else:
            # Le dossier a été créé pendant la journée, on récupère ses droits instantanément
            groupes = obtenir_groupes_dossier(chemin_dossier)
            cursor.execute("INSERT INTO dossiers (chemin_dossier, acl_sids) VALUES (?, ?)", (chemin_dossier, json.dumps(groupes)))
            dossier_id = cursor.lastrowid
            logger.info(f"📁 Nouveau dossier indexé à la volée : {chemin_dossier}")

        # 2. Recherche de l'existence du fichier
        cursor.execute("SELECT id, est_indexable_faiss FROM fichiers WHERE dossier_id = ? AND nom_fichier = ?", (dossier_id, nom_fichier))
        ligne_fichier = cursor.fetchone()

        file_id = None
        ancien_vip_statut = 0

        # 3. Application de l'événement
        if evenement == "Deleted":
            if ligne_fichier:
                file_id, ancien_vip_statut = ligne_fichier
                cursor.execute("DELETE FROM fichiers WHERE id = ?", (file_id,))
                logger.warning(f"❌ [SQL] Suppression : {nom_fichier} (ID: {file_id})")
        
        elif evenement in ["Created", "Changed", "Renamed"]:
            if ligne_fichier:
                file_id, ancien_vip_statut = ligne_fichier
                cursor.execute("UPDATE fichiers SET nom_fichier = ?, extension = ?, est_indexable_faiss = ?, chemin_relatif = ? WHERE id = ?", 
                               (nom_fichier, ext, est_vip, chemin_relatif, file_id))
                logger.info(f"🔄 [SQL] Mise à jour : {nom_fichier} (ID: {file_id})")
            else:
                cursor.execute("INSERT INTO fichiers (dossier_id, nom_fichier, extension, est_indexable_faiss, chemin_relatif) VALUES (?, ?, ?, ?, ?)", 
                               (dossier_id, nom_fichier, ext, est_vip, chemin_relatif))
                file_id = cursor.lastrowid
                logger.success(f"➕ [SQL] Ajout : {nom_fichier} (ID: {file_id})")

        conn.commit()

        # 4. Mise à jour chirurgicale de l'Intelligence Artificielle (FAISS)
        # On ne dérange FAISS que si le fichier était VIP ou vient de le devenir
        if file_id is not None and (est_vip == 1 or ancien_vip_statut == 1):
            init_faiss_v4.traiter_delta(evenement, file_id, chemin_fichier, nom_fichier)

    except Exception as e:
        logger.error(f"❌ Erreur critique sur {chemin_fichier} : {e}")
    finally:
        conn.close()

    return jsonify({"statut": "succès"}), 200





@app.route('/force_scan', methods=['POST'])
def force_scan():
    """Route appelée par Streamlit pour forcer l'actualisation d'un dossier précis."""
    data = request.json
    if not data or not data.get('dossier'):
        return jsonify({"erreur": "Chemin du dossier manquant"}), 400

    chemin_dossier_cible = os.path.normpath(data.get('dossier'))
    
    if not os.path.exists(chemin_dossier_cible):
        return jsonify({"erreur": "Dossier introuvable sur le réseau"}), 404

    logger.info(f"🔄 Demande d'actualisation forcée reçue pour : {chemin_dossier_cible}")
    
    try:
        # 1. Lire les droits actuels du dossier
        groupes = obtenir_groupes_dossier(chemin_dossier_cible)
        acl_json = json.dumps(groupes)

        conn = sqlite3.connect(CHEMIN_BDD)
        cursor = conn.cursor()

        # 2. Vérifier si le dossier existe ou le créer
        cursor.execute("SELECT id FROM dossiers WHERE chemin_dossier = ?", (chemin_dossier_cible,))
        resultat = cursor.fetchone()
        
        if resultat:
            dossier_id = resultat[0]
            cursor.execute("UPDATE dossiers SET acl_sids = ? WHERE id = ?", (acl_json, dossier_id))
            # On purge l'ancien contenu dans SQLite
            cursor.execute("DELETE FROM fichiers WHERE dossier_id = ?", (dossier_id,))
        else:
            cursor.execute("INSERT INTO dossiers (chemin_dossier, acl_sids) VALUES (?, ?)", (chemin_dossier_cible, acl_json))
            dossier_id = cursor.lastrowid

        # 3. Lister et insérer les fichiers réels
        fichiers_trouves = 0
        for element in os.listdir(chemin_dossier_cible):
            chemin_complet = os.path.join(chemin_dossier_cible, element)
            
            if os.path.isfile(chemin_complet) and not element.startswith("~$"):
                _, ext = os.path.splitext(element)
                ext = ext.lower()
                
                if ext not in EXTENSIONS_FANTOMES:
                    est_vip = 1 if ext in LISTE_VIP else 0
                    chemin_relatif = chemin_complet.replace(RACINE_SCAN, "").lstrip("\\")
                    
                    cursor.execute(
                        "INSERT INTO fichiers (dossier_id, nom_fichier, extension, est_indexable_faiss, chemin_relatif) VALUES (?, ?, ?, ?, ?)", 
                        (dossier_id, element, ext, est_vip, chemin_relatif)
                    )
                    fichiers_trouves += 1
                    
                    # Si c'est un fichier VIP, on force FAISS à l'apprendre
                    if est_vip:
                        file_id = cursor.lastrowid
                        init_faiss_v4.traiter_delta("Created", file_id, chemin_complet, element)

        conn.commit()
        conn.close()
        logger.success(f"✅ Actualisation terminée : {fichiers_trouves} fichiers mis à jour dans {chemin_dossier_cible}")
        
        return jsonify({"statut": "succès", "fichiers_ajoutes": fichiers_trouves}), 200

    except Exception as e:
        logger.error(f"❌ Erreur lors du scan forcé de {chemin_dossier_cible} : {e}")
        return jsonify({"erreur": str(e)}), 500










if __name__ == '__main__':
    # Initialisation de FAISS en mémoire au lancement
    init_faiss_v4.charger_modeles_en_memoire()
    logger.info("🚀 Démarrage du serveur Webhook V4 (Hybride Texte/Binaire) sur le port 8000...")
    # '0.0.0.0' écoute sur toutes les interfaces réseau du serveur IA
    app.run(host='0.0.0.0', port=8000)