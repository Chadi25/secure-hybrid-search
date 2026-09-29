import sqlite3
import faiss
import pickle
import re
import numpy as np
import os
import math
import random
import threading
from sentence_transformers import SentenceTransformer
from loguru import logger

# --- CONFIGURATION ---
CHEMIN_BDD = "chadibot_v4.db"
CHEMIN_FAISS = "index_faiss.bin"
CHEMIN_MAPPING = "mapping_faiss.pkl"

# --- VERROU MULTI-THREADING ET VARIABLES GLOBALES ---
faiss_lock = threading.Lock()
model_st = None
index_faiss = None
mapping_data = {'ids_sqlite': [], 'mapping': {}}

def nettoyer_chemin_pour_ia(chemin: str) -> str:
    """Nettoie le chemin d'accès pour ne garder que les termes significatifs."""
    if not chemin:
        return ""
    chemin_propre = re.sub(r'[\\/_\-\.]', ' ', chemin)
    mots = [mot for mot in chemin_propre.split() if len(mot) > 1]
    return " ".join(mots).lower()

def construire_cerveau_ia():
    """Construit l'index vectoriel FAISS V4 (IndexIVFFlat) de masse depuis SQLite."""
    logger.info("🧠 Démarrage de la construction du Cerveau Vectoriel V4...")
    
    # 1. Extraction ciblée (Filtre VIP : documents textuels/humains uniquement)
    logger.info("📂 Lecture de la base SQLite pour isoler les documents textuels (VIP)...")
    conn = sqlite3.connect(CHEMIN_BDD)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT f.id, (d.chemin_dossier || '\\' || f.nom_fichier) AS chemin_complet, f.nom_fichier 
        FROM fichiers f
        JOIN dossiers d ON f.dossier_id = d.id
        WHERE f.est_indexable_faiss = 1
    ''')
    lignes = cursor.fetchall()
    conn.close()
    
    total_vip = len(lignes)
    if total_vip == 0:
        logger.error("❌ Aucun fichier VIP trouvé dans la base. Le scan est-il bien terminé ?")
        return
        
    logger.info(f"🎯 {total_vip} documents VIP identifiés pour l'IA.")
    
    # 2. Préparation du Modèle Sémantique
    logger.info("🤖 Chargement du modèle SentenceTransformer en RAM...")
    model_st = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    dimension_vecteur = 384
    
    # 3. Paramétrage mathématique de FAISS (IndexIVFFlat)
    nlist = int(4 * math.sqrt(total_vip))
    nlist = max(100, min(nlist, 4096))
    quantizer = faiss.IndexFlatL2(dimension_vecteur)
    index_ivf = faiss.IndexIVFFlat(quantizer, dimension_vecteur, nlist)
    
    # 4. Entraînement des clusters sur échantillon
    taille_echantillon = min(50000, total_vip)
    logger.info(f"🏋️ Entraînement de FAISS sur un échantillon de {taille_echantillon} vecteurs (Calcul des clusters)...")
    
    echantillon_brut = random.sample(lignes, taille_echantillon)
    echantillon_chemins = [nettoyer_chemin_pour_ia(row[1]) for row in echantillon_brut]
    vecteurs_echantillon = model_st.encode(echantillon_chemins, batch_size=64, show_progress_bar=True).astype('float32')
    
    index_ivf.train(vecteurs_echantillon)
    logger.success("✅ Entraînement des clusters FAISS terminé.")
    
    # 5. Encodage et Injection par Lots (Batching de 20 000)
    logger.info("🧬 Début de l'encodage massif et de l'injection en base (Batch de 20 000)...")
    mapping_data_local = {'ids_sqlite': [], 'mapping': {}}
    batch_size = 20000
    
    for i in range(0, total_vip, batch_size):
        lot = lignes[i : i + batch_size]
        ids = []
        chemins_propres = []
        
        for rowid, chemin_complet, nom_fichier in lot:
            ids.append(rowid)
            chemins_propres.append(nettoyer_chemin_pour_ia(chemin_complet))
            mapping_data_local['mapping'][rowid] = {"nom": nom_fichier, "chemin": chemin_complet}
            
        mapping_data_local['ids_sqlite'].extend(ids)
        
        vecteurs_lot = model_st.encode(chemins_propres, batch_size=64, show_progress_bar=False).astype('float32')
        ids_np = np.array(ids).astype('int64')
        
        index_ivf.add_with_ids(vecteurs_lot, ids_np)
        logger.info(f"⏳ Progression : {min(i + batch_size, total_vip)} / {total_vip} vecteurs calculés et injectés...")
        
    # 6. Sauvegarde Atomique sur Disque
    logger.info("💾 Sauvegarde de la base vectorielle sur le disque...")
    chemin_faiss_tmp = CHEMIN_FAISS + ".tmp"
    chemin_mapping_tmp = CHEMIN_MAPPING + ".tmp"
    
    faiss.write_index(index_ivf, chemin_faiss_tmp)
    with open(chemin_mapping_tmp, 'wb') as f:
        pickle.dump(mapping_data_local, f)
        
    os.replace(chemin_faiss_tmp, CHEMIN_FAISS)
    os.replace(chemin_mapping_tmp, CHEMIN_MAPPING)
    
    logger.success(f"🎉 MIGRATION IA TERMINÉE : Cerveau vectoriel de {index_ivf.ntotal} documents créé avec succès !")

def charger_modeles_en_memoire():
    """Charge le modèle IA et la base vectorielle une seule fois en RAM pour le Webhook."""
    global model_st, index_faiss, mapping_data
    if model_st is None:
        logger.info("🧠 [FAISS] Chargement du modèle SentenceTransformer en RAM (Delta Mode)...")
        model_st = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    if os.path.exists(CHEMIN_FAISS) and os.path.exists(CHEMIN_MAPPING):
        if index_faiss is None:
            index_faiss = faiss.read_index(CHEMIN_FAISS)
        if not mapping_data['mapping']:
            with open(CHEMIN_MAPPING, 'rb') as f:
                mapping_data = pickle.load(f)

def traiter_delta(action: str, rowid: int, chemin: str = None, nom: str = None):
    """La fonction chirurgicale appelée par le Webhook. (Version Multi-Threading et Écriture Atomique)"""
    with faiss_lock:
        charger_modeles_en_memoire()
        global index_faiss, mapping_data
        
        id_np = np.array([rowid]).astype('int64')

        try:
            if action in ["Created", "Changed", "Renamed"]:
                # 1. Suppression de l'ancien vecteur s'il existait déjà
                try: 
                    index_faiss.remove_ids(id_np)
                except Exception: 
                    pass
                
                # 2. Calcul du nouveau vecteur
                phrase_ia = nettoyer_chemin_pour_ia(chemin)
                vecteur = model_st.encode([phrase_ia]).astype('float32')
                
                # 3. Ajout dans FAISS
                index_faiss.add_with_ids(vecteur, id_np)
                
                # 4. Mise à jour du Mapping
                mapping_data['mapping'][rowid] = {"nom": nom, "chemin": chemin}
                if rowid not in mapping_data['ids_sqlite']:
                    mapping_data['ids_sqlite'].append(rowid)
                    
                logger.success(f"⚡ [FAISS] Injection Delta réussie pour : {nom}")

            elif action == "Deleted":
                # Suppression chirurgicale
                try: 
                    index_faiss.remove_ids(id_np)
                except Exception: 
                    pass
                
                if rowid in mapping_data['mapping']:
                    del mapping_data['mapping'][rowid]
                if rowid in mapping_data['ids_sqlite']:
                    mapping_data['ids_sqlite'].remove(rowid)
                logger.warning(f"🗑️ [FAISS] Vecteur supprimé (ID: {rowid})")

            # 5. Sauvegarde Atomique (Bouclier anti-corruption)
            chemin_faiss_tmp = CHEMIN_FAISS + ".tmp"
            chemin_mapping_tmp = CHEMIN_MAPPING + ".tmp"
            
            faiss.write_index(index_faiss, chemin_faiss_tmp)
            with open(chemin_mapping_tmp, 'wb') as f:
                pickle.dump(mapping_data, f)
                
            os.replace(chemin_faiss_tmp, CHEMIN_FAISS)
            os.replace(chemin_mapping_tmp, CHEMIN_MAPPING)
                
        except Exception as e:
            logger.error(f"❌ [FAISS] Erreur lors du Delta (ID: {rowid}) : {e}")

if __name__ == "__main__":
    construire_cerveau_ia()