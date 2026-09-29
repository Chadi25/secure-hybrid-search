import streamlit as st
import sqlite3
import requests
import json
import os
import unicodedata
import re
import ctypes
from ctypes import wintypes
import spacy
import faiss
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
from contextlib import closing
from typing import List, Tuple, Optional
import urllib.parse
import sys
from loguru import logger
import win32net
import win32security
import ntsecuritycon
import pywintypes
# mot de passe secret pour pouvoir utiliser doc-ia
JETON_SECRET = "Jtekt2026_Chadibot*"

#  ==========================================
# MISE EN PLACE LOGS 
#  ==========================================
logger.remove()
logger.add(sys.stderr, colorize=True, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")
# [MODIFIER_ICI] Modifiez le chemin des logs pour correspondre à votre infrastructure
logger.add(
    "C:/AGENT_IA/log_streamlit_propre.log", 
    rotation="5 MB",       
    retention="10 days",   
    encoding="utf-8",      
    level="DEBUG",         
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}"
)

# ==========================================
# 🧠 1. CHARGEMENT CACHÉ DES MODÈLES (RAM)
# ==========================================
def obtenir_date_cerveau():
    try:
        return os.path.getmtime("index_faiss.bin")
    except OSError:
        return 0 

@st.cache_resource 
def load_all_models(date_fichier): 
    logger.info("⏳ [DÉMARRAGE] Chargement des modèles en RAM...")
    
    try:
        nlp_model = spacy.load("fr_core_news_sm")
    except OSError:
        logger.error("[ERREUR] spaCy introuvable.")
        nlp_model = None

    try:
        semantic_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    except Exception as e:
        logger.error(f"[ERREUR] SentenceTransformer : {e}")
        semantic_model = None

    try:
        faiss_idx = faiss.read_index("index_faiss.bin")
        with open("mapping_faiss.pkl", "rb") as f:
            mapping_data = pickle.load(f)
        logger.info("✅ [DÉMARRAGE] Cerveau FAISS mis à jour et chargé en mémoire !")
    except Exception as e:
        logger.error(f"[ERREUR] Base FAISS ou mapping introuvable : {e}")
        faiss_idx = None
        mapping_data = None

    return nlp_model, semantic_model, faiss_idx, mapping_data

date_actuelle = obtenir_date_cerveau()
nlp, model_semantique, index_faiss, mapping_faiss = load_all_models(date_actuelle)

# ==========================================
# ⚙️ 2. CONFIGURATION GLOBALE
# ==========================================
CHEMIN_BDD = "chadibot_v4.db"
# [MODIFIER_ICI] L'URL de votre instance Ollama (local ou distante)
URL_OLLAMA = "http://localhost:11434/api/generate"
MODELE_OLLAMA = "llama3.2"

st.set_page_config(page_title="Assistant Documentaire V3", page_icon="🤖", layout="centered")

if not index_faiss:
    st.sidebar.error("🚨 Base Vectorielle FAISS absente. L'approche sémantique est HORS SERVICE.")





# ==========================================
# 🔐 PÉAGE SSO (PORTAIL D'ENTRÉE)
# ==========================================
# ==========================================
# 🔐 PÉAGE SSO (PORTAIL D'ENTRÉE)
# ==========================================

# ==========================================
# 🔐 PÉAGE SSO (PORTAIL D'ENTRÉE SÉPARÉ)
# ==========================================

if "identite_verrouillee" not in st.session_state:
    jeton_url = st.query_params.get("sso")
    
    if jeton_url:
        # [MODIFIER_ICI] Dossier où les jetons SSO sont générés temporairement par le serveur WebIIS
        chemin_jeton = f"C:/AGENT_IA/.streamlit/{jeton_url}.tok"
        if os.path.exists(chemin_jeton):
            with open(chemin_jeton, "r") as f:
                st.session_state.identite_verrouillee = f.read().strip()
            os.remove(chemin_jeton) 
            st.query_params.clear()
            st.rerun()
        else:
            st.error("❌ Jeton expiré.")
            st.stop()
    else:
        # Le bouton pointe désormais vers l'application IIS isolée
        st.markdown("""
            <div style='text-align: center; margin-top: 100px; font-family: sans-serif;'>
                <h2 style='color: #333;'>🔐 Accès Sécurisé ZekiBot</h2>
                <p style='color: #666; margin-bottom: 30px;'>Connexion silencieuse à l'intranet</p>
                <a href="/auth/login.aspx" target="_parent">
                    <button style='background-color: #0288d1; color: white; padding: 14px 28px; border: none; border-radius: 6px; font-size: 16px; cursor: pointer; font-weight: bold;'>
                        Entrer
                    </button>
                </a>
            </div>
        """, unsafe_allow_html=True)
        st.stop()

identite_actuelle = st.session_state.identite_verrouillee

# ==========================================
# ==========================================
# ==========================================

# ==========================================
# 🔍 3. LE MOTEUR LEXICAL (Ollama + SQLite)
# ==========================================
def extraire_mots_cles_ia(phrase_utilisateur: str) -> Optional[str]:
    phrase_propre = phrase_utilisateur.replace("'", " ").replace("’", " ").strip().lower()
    
    phrase_propre = phrase_propre.replace(".exe", " .exe").replace(".pdf", " .pdf").replace(".doc", " .doc").replace(".msi", " .msi")
    phrase_propre = phrase_propre.replace("d'install", "install").replace("dinstall", "install")
    phrase_propre = phrase_propre.replace("sentinel one", "sentinelone").replace("sentinelle one", "sentinelone")
    phrase_propre = re.sub(r'(?<!\.)\bdoc\b', 'docs', phrase_propre)
    phrase_propre = re.sub(r'\s+', ' ', phrase_propre).strip()
    
    mots_bruts = phrase_propre.split()
    
    # 1. On isole les mots importants tapés par l'utilisateur
    mots_utiles_originaux = [m for m in mots_bruts if len(m) > 1 and m not in ["le", "la", "les", "de", "du", "des", "un", "une", "toute", "cherche", "trouve", "donne", "fichier", "pour"]]
    
    # 2. BYPASS IA : Si c'est juste une requête de mots-clés purs, on ne consulte pas Llama
    mots_concepts = ["installeur", "install", "installation", "setup", "fichier", "cherche", "trouve", "donne", "veux"]
    besoin_ia = any(mot in mots_bruts for mot in mots_concepts)
    
    if not besoin_ia:
        mots_directs = " ".join(mots_utiles_originaux)
        logger.debug(f"⚡ Bypass IA (Requête simple) : '{mots_directs}'")
        return mots_directs

    # 3. Le Prompt corrigé pour l'IA
    prompt = f"""Tu es un expert en extraction de mots-clés.
    RÈGLE 1 : Garde TOUJOURS les mots importants de la requête (noms, sujets, marques). Ne les supprime JAMAIS.
    RÈGLE 2 : Ajoute ".exe" et ".msi" UNIQUEMENT SI la requête contient "install", "setup", ou "installeur".
    RÈGLE 3 : Ne réponds RIEN D'AUTRE que le JSON.

    Exemples :
    Requête : "installeur sentinelone" -> {{"mots": [".exe", ".msi", "sentinelone"]}}
    Requête : "cherche doc mabeo" -> {{"mots": ["docs", "mabeo"]}}

    Requête : "{phrase_propre}" -> """

    schema = {"type": "object", "properties": {"mots": {"type": "array", "items": {"type": "string"}}}, "required": ["mots"]}
    payload = {"model": MODELE_OLLAMA, "prompt": prompt, "format": schema, "stream": False, "temperature": 0.0}
    
    try:
        response = requests.post(URL_OLLAMA, json=payload, timeout=(5, 30))
        response.raise_for_status()
        
        reponse_brute = response.json()["response"].strip()
        if not reponse_brute.startswith("{"): reponse_brute = "{" + reponse_brute
            
        mots_liste = json.loads(reponse_brute).get("mots", [])
        
        mots_valides = []
        if isinstance(mots_liste, str): mots_liste = mots_liste.split()
        for m in mots_liste:
            mots_separes = str(m).split()
            for mot in mots_separes:
                mot_nettoye = re.sub(r'[^\w\.]', '', mot)
                if len(mot_nettoye) > 1:
                    mots_valides.append(mot_nettoye)

        # 4. 🛡️ FAILSAFE CRITIQUE : L'anti-hallucination
        a_garde_un_mot_original = any(mot in mots_utiles_originaux for mot in mots_valides)
        if not a_garde_un_mot_original and mots_utiles_originaux:
            logger.warning("🚨 L'IA a perdu les mots-clés. Failsafe activé.")
            # On force la réinjection de vos mots d'origine + les extensions devinées par l'IA
            mots_valides = mots_utiles_originaux + [m for m in mots_valides if m.startswith('.')]

        resultat_final = " ".join(mots_valides)
        logger.debug(f"🧠 Mots extraits (IA) : {resultat_final}")
        return resultat_final if mots_valides else " ".join(mots_utiles_originaux)

    except Exception as e:
        logger.error(f"[ERREUR LEXICAL] : {e}")
        return " ".join(mots_utiles_originaux)
        
def chercher_sqlite(mots_cles_stricts: str) -> List[Tuple[str, str]]:
    if not mots_cles_stricts: return []
    try:
        with closing(sqlite3.connect(CHEMIN_BDD)) as conn:
            # ---> LA LIGNE MAGIQUE EST ICI <---
            conn.execute('pragma journal_mode=wal') 
            
            cursor = conn.cursor()
            mots = mots_cles_stricts.lower().split()
            if not mots: return []
            
            # Recherche HYPER-LARGE : Dans le nom du fichier OU dans le chemin du dossier
            conditions = " AND ".join(["(f.nom_fichier LIKE ? OR d.chemin_dossier LIKE ?)"] * len(mots))
            valeurs = tuple(val for mot in mots for val in (f"%{mot}%", f"%{mot}%"))
            
            requete = f'''
                SELECT f.nom_fichier, d.chemin_dossier || '\\' || f.nom_fichier AS chemin_complet
                FROM fichiers f
                JOIN dossiers d ON f.dossier_id = d.id
                WHERE {conditions}
                LIMIT 150
            '''
            
            cursor.execute(requete, valeurs)
            resultats = cursor.fetchall()
            
            # CE LOG EST VITAL POUR NOTRE DIAGNOSTIC :
            logger.debug(f"🗄️ SQL a trouvé {len(resultats)} fichiers AVANT de passer le Bouclier NTFS.")
            
            return resultats
            
    except Exception as e:
        logger.error(f"[ERREUR SQL BLINDÉ] {e}")
        return []
# ==========================================
# 🧠 4. LE MOTEUR SÉMANTIQUE (FAISS)
# ==========================================
def chercher_faiss(phrase_utilisateur: str) -> List[Tuple[str, str]]:
    if not phrase_utilisateur or not model_semantique or not index_faiss: return []
    
    phrase_propre = re.sub(r'[^\w\s]', ' ', phrase_utilisateur).lower()
    vecteur_requete = np.array(model_semantique.encode([phrase_propre])).astype('float32')
    
    # NOUVEAUTÉ V4 : On indique à FAISS de chercher dans les 10 meilleurs clusters
    index_faiss.nprobe = 10 
    
    distances, indices = index_faiss.search(vecteur_requete, 15)
    
    resultats = []
    for distance, idx in zip(distances[0], indices[0]):
        rowid = int(idx)
        if rowid != -1 and distance < 30.0 and rowid in mapping_faiss['mapping']:
            info = mapping_faiss['mapping'][rowid]
            resultats.append((info['nom'], info['chemin']))
            
    return resultats

# ==========================================
# 🛡️ 5.5 LE BOUCLIER NTFS (Vérification des droits)
# ==========================================
def obtenir_groupes_utilisateur(identite: str) -> set:
    """Interroge l'AD et injecte les vrais SIDs Windows."""
    groupes = {identite.upper()} # Le faux TOUT_LE_MONDE a été supprimé ici
    try:
        domaine, user = identite.split("\\") if "\\" in identite else (None, identite)
        
        dc_name = None
        if domaine:
            try:
                dc_name = win32net.NetGetAnyDCName(None, domaine)
            except Exception as e:
                pass

        try:
            groupes_globaux = win32net.NetUserGetGroups(dc_name, user)
            for g in groupes_globaux:
                if isinstance(g, dict): nom = g.get('name', str(g))
                elif isinstance(g, tuple): nom = g[0]
                else: nom = str(g)
                groupes.add(f"{domaine}\\{nom}".strip().upper())
        except Exception: pass

        try:
            groupes_locaux = win32net.NetUserGetLocalGroups(dc_name, user)
            for g in groupes_locaux:
                if isinstance(g, dict): nom = g.get('name', str(g))
                elif isinstance(g, tuple): nom = g[0]
                else: nom = str(g)
                groupes.add(f"{domaine}\\{nom}".strip().upper())
        except Exception: pass
            
    except Exception as e:
        logger.error(f"⚠️ Erreur AD globale : {e}")
    
    # Injection des groupes natifs réels de Windows (FR/EN)
    groupes.update({
        "\\TOUT LE MONDE", "\\EVERYONE", 
        "NT AUTHORITY\\UTILISATEURS AUTHENTIFIÉS", "NT AUTHORITY\\AUTHENTICATED USERS",
        "BUILTIN\\UTILISATEURS", "BUILTIN\\USERS"
    })
    
    logger.debug(f"🔑 Groupes Sécurisés : {groupes}")
    return groupes
CACHE_ACL_DOSSIERS = {}

def a_le_droit_de_lire(chemin_fichier: str, groupes_utilisateur: set, cursor) -> bool:
    """Vérifie les droits (SQLite ultra-rapide pour 95% de l'usine, Live NTFS pour les 5% Top Secret)."""
    chemin_dossier = os.path.dirname(chemin_fichier)
    
    if len(chemin_dossier) <= 3 and chemin_dossier.upper().startswith("S:"):
        return True
        
    if chemin_dossier in CACHE_ACL_DOSSIERS:
        return CACHE_ACL_DOSSIERS[chemin_dossier]

    # --- LE SANCTUAIRE : VÉRIFICATION LIVE OBLIGATOIRE ---
    # [MODIFIER_ICI] Liste des dossiers très sensibles nécessitant une vérification directe NTFS sans utiliser le cache
    zones_interdites = ["\\RH\\", "\\RH-", "\\INFIRMERIE", "\\SERVICE MEDICAL", "\\COMPTA", "\\FINANCESI", "\\DIRECTION", "\\PAIE"]
    chemin_maj = chemin_dossier.upper()
    
    if any(zone in chemin_maj for zone in zones_interdites):
        # 🚨 DANGER : Zone sensible détectée. On ignore SQLite et on demande à Windows.
        # [MODIFIER_ICI] Conversion du chemin réseau "S:" vers le chemin UNC complet du serveur de fichier. 
        # Remplacez 'faf-fls' par le nom de votre serveur de fichiers
        chemin_unc = re.sub(r'(?i)^s:[\\/]+', r'\\\\<VOTRE_SERVEUR_FICHIER>\\Services\\', chemin_dossier)
        chemin_unc = os.path.normpath(chemin_unc)
        
        try:
            sd = win32security.GetFileSecurity(chemin_unc, win32security.DACL_SECURITY_INFORMATION)
            dacl = sd.GetSecurityDescriptorDacl()
            
            if dacl is None: return True # Dossier grand ouvert
            
            droit_accorde = False
            for i in range(dacl.GetAceCount()):
                ace = dacl.GetAce(i)
                if ace[1] & ntsecuritycon.FILE_READ_DATA:
                    try:
                        nom, domaine, _ = win32security.LookupAccountSid(None, ace[2])
                        groupe_ace = f"{domaine}\\{nom}".upper() if domaine else f"\\{nom}".upper()
                        if groupe_ace in groupes_utilisateur:
                            if ace[0][0] == win32security.ACCESS_DENIED_ACE_TYPE:
                                CACHE_ACL_DOSSIERS[chemin_dossier] = False
                                return False # Refus catégorique Windows
                            elif ace[0][0] == win32security.ACCESS_ALLOWED_ACE_TYPE:
                                droit_accorde = True
                    except: continue
            
            CACHE_ACL_DOSSIERS[chemin_dossier] = droit_accorde
            return droit_accorde
            
        except Exception as e:
            logger.error(f"🛑 [SANCTUAIRE] Erreur lecture Live sur {chemin_unc} : {e}. ACCÈS REFUSÉ PAR DÉFAUT.")
            CACHE_ACL_DOSSIERS[chemin_dossier] = False
            return False
            
    # --- LA ROUTE NORMALE (VITESSE ÉCLAIR VIA SQLITE) ---
    try:
        cursor.execute("SELECT acl_sids FROM dossiers WHERE chemin_dossier = ?", (chemin_dossier,))
        resultat = cursor.fetchone()
        
        if resultat and resultat[0]:
            groupes_autorises = {g.upper() for g in json.loads(resultat[0])}
            if groupes_utilisateur.intersection(groupes_autorises):
                CACHE_ACL_DOSSIERS[chemin_dossier] = True
                return True
                
        CACHE_ACL_DOSSIERS[chemin_dossier] = False
        return False
        
    except Exception as e:
        logger.error(f"❌ Erreur DB ACL sur {chemin_dossier} : {e}")
        CACHE_ACL_DOSSIERS[chemin_dossier] = False
        return False
    
# ==========================================
# ⚖️ 5. L'ARBITRE : RECIPROCAL RANK FUSION + SECURITE NTFS
# ==========================================
import sqlite3 # À vérifier si déjà présent en haut de votre script

def fusion_rrf(resultats_sqlite: List[Tuple[str, str]], resultats_faiss: List[Tuple[str, str]], mots_cles_ia: str, groupes_utilisateur: set) -> List[dict]:
    scores = {}
    k = 60 
    mots_cles = mots_cles_ia.lower() if mots_cles_ia else ""
    mots_cles_liste = mots_cles.split()
    
    extensions_exigees = [mot for mot in mots_cles_liste if mot.startswith('.')]
            
    for rank, (nom, chemin) in enumerate(resultats_sqlite):
        scores[chemin] = {"nom": nom, "score": 1.0 / (k + rank + 1), "sources": "🔍 [Match Lexical]"}
        
    for rank, (nom, chemin) in enumerate(resultats_faiss):
        if chemin in scores:
            scores[chemin]["score"] += 1.0 / (k + rank + 1)
            scores[chemin]["sources"] = "🏆 [Alliance Lexicale & Sémantique]" 
        else:
            scores[chemin] = {"nom": nom, "score": 1.0 / (k + rank + 1), "sources": "🧠 [Match Sémantique FAISS]"}

    mots_recherche_importants = [m for m in mots_cles_liste if not m.startswith('.') and m not in ['exe', 'pdf', 'doc', 'txt']]
    phrase_recherche = " ".join(mots_recherche_importants).strip()

    for chemin in scores:
        nom_fichier = scores[chemin]["nom"].lower()
        nom_sans_ext, ext_fichier = os.path.splitext(scores[chemin]["nom"])
        nom_sans_ext = nom_sans_ext.lower().strip()
        
        if extensions_exigees and ext_fichier.lower() not in extensions_exigees:
            scores[chemin]["score"] *= 0.01
            if "Rejeté" not in scores[chemin]["sources"]:
                scores[chemin]["sources"] += " 📉 (Rejeté : Mauvais format)"
                
        # --- L'ANALYSE DU TITRE ---
        mots_trouves_dans_titre = 0
        for mot in mots_recherche_importants:
            if len(mot) > 2 and mot in nom_fichier:
                mots_trouves_dans_titre += 1
        
        if mots_trouves_dans_titre > 0:
            scores[chemin]["score"] *= (2 ** mots_trouves_dans_titre)
            
            if mots_trouves_dans_titre == len(mots_recherche_importants) and len(mots_recherche_importants) > 0:
                scores[chemin]["score"] *= 15.0 
                scores[chemin]["sources"] = "🎯 [Titre Parfait] " + scores[chemin]["sources"]
            elif "Titre" not in scores[chemin]["sources"]:
                scores[chemin]["sources"] = "🎯 [Titre Partiel] " + scores[chemin]["sources"]

        # --- NOUVEAU : LE GOD MODE ---
        if phrase_recherche and len(phrase_recherche) > 3:
            # 1. Si la phrase exacte est contenue
            if phrase_recherche in nom_fichier:
                scores[chemin]["score"] *= 50.0
                scores[chemin]["sources"] = scores[chemin]["sources"].replace("🎯 [Titre Parfait]", "").replace("🎯 [Titre Partiel]", "")
                if "Phrase Exacte" not in scores[chemin]["sources"]:
                    scores[chemin]["sources"] = "⭐⭐ [Phrase Exacte] " + scores[chemin]["sources"]
            
            # 2. Si le nom du fichier EST EXACTEMENT la recherche
            if nom_sans_ext == phrase_recherche:
                scores[chemin]["score"] *= 500.0
                scores[chemin]["sources"] = scores[chemin]["sources"].replace("⭐⭐ [Phrase Exacte]", "")
                scores[chemin]["sources"] = "👑 [CLONE PARFAIT] " + scores[chemin]["sources"]
            
    resultats_tries = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
    
    resultats_autorises = []
    logger.info(f"🛡️ Audit NTFS (Mode Cache V4) sur {len(resultats_tries)} résultats.")
    
    
    # On ouvre la base de données SQLite pour lire les droits
    conn = sqlite3.connect("chadibot_v4.db") # Modifiez le nom du fichier si nécessaire
    cursor = conn.cursor()
    
    try:
        for chemin, data in resultats_tries:
            # 1. LE FIX CRASH : On envoie le 'cursor' à la fonction de vérification
            if a_le_droit_de_lire(chemin, groupes_utilisateur, cursor):
                resultats_autorises.append({"chemin": chemin, "nom": data["nom"], "sources": data["sources"]})
                
            # 2. LA GUILLOTINE : On s'arrête à 40 résultats validés.
            # Inutile de vérifier les droits de 2000 fichiers si on n'en affiche que quelques-uns.
            if len(resultats_autorises) >= 40:
                break
    finally:
        # On ferme proprement la base de données, quoi qu'il arrive
        conn.close()
            
    return resultats_autorises

# ==========================================
# 🎨 6. INTERFACE UTILISATEUR & HTML
# ==========================================
def generer_html_boutons(chemin_complet: str) -> str:
    chemin_encode = urllib.parse.quote(chemin_complet)
    style = "display: inline-block; padding: 6px 12px; color: white; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 0.85em; margin: 6px 8px 5px 0;"
    
    _, extension = os.path.splitext(chemin_complet)
    extensions_code = {".bat", ".cmd", ".ps1", ".py", ".json", ".ini", ".md", ".sh", ".exe",".msi"}
    
    if extension.lower() in extensions_code:
        return f'<a href="doc-ia:EDIT|{JETON_SECRET}|{chemin_encode}" style="{style} background-color: #2e7d32;">👁️ Lire le code</a><a href="doc-ia:RUN|{JETON_SECRET}|{chemin_encode}" style="{style} background-color: #d32f2f;">⚠️ Executer (IT)</a>'
    
    return f'<a href="doc-ia:OPEN|{JETON_SECRET}|{chemin_encode}" style="{style} background-color: #0277bd;">📂 Ouvrir le document</a>'
    
st.title("🤖 Assistant Documentaire V3")
st.caption("Recherche Multi-agents (Hybride BM25 Exact + Mathématiques IA vectorielles)")

if "messages" not in st.session_state: st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]): st.markdown(message["content"], unsafe_allow_html=True)

if prompt := st.chat_input("Ex: trouve moi le .exe pour l'antivirus..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        with st.spinner("Interrogation du Moteur Lexical 🔍..."):
            mots_cles = extraire_mots_cles_ia(prompt)
            res_sqlite = chercher_sqlite(mots_cles) if mots_cles else []
            
        with st.spinner("Analyse du Moteur Sémantique Vectoriel 🧠..."):
            res_faiss = chercher_faiss(prompt)
            
        with st.spinner("Délibération par le Juge RRF ⚖️ et Vérification des Droits 🛡️..."):
            
            logger.info(f"👤 Utilisateur identifié par SSO : {identite_actuelle}")
            
            # 1. On récupère les groupes AD de l'utilisateur (mise en cache dans la session pour ne pas saturer l'AD)
            if "groupes_ad" not in st.session_state:
                st.session_state.groupes_ad = obtenir_groupes_utilisateur(identite_actuelle)
            
            # 2. --- L'APPEL AU MOTEUR EST ICI (On passe les groupes et non plus le nom) ---
            resultats_finaux = fusion_rrf(res_sqlite, res_faiss, mots_cles, st.session_state.groupes_ad)
   

       
            
            # --- AFFICHAGE ---
            if resultats_finaux:
                reponse = f"✅ Traduction cognitive de l'IA : `{mots_cles if mots_cles else '[Recherche Sémantique Pure]'}`<br><br><b>🎯 CIBLES LOCALISÉES & AUTORISÉES :</b><br>"
                
                top = resultats_finaux[:3]
                for item in top:
                    border_color = "#fbc02d" if "Alliance" in item['sources'] else ("#0288d1" if "Lexical" in item['sources'] else "#8e24aa")
                    if "Rejeté" in item['sources']:
                        border_color = "#d32f2f" 
                    
                    reponse += (
                        f"<div style='background: rgba(128, 128, 128, 0.05); padding: 14px; "
                        f"border-left: 6px solid {border_color}; border-radius: 6px; margin-bottom: 12px; font-family: sans-serif;'>"
                        f"<span style='font-size: 0.75rem; text-transform: uppercase; color:{border_color}; font-weight:800; letter-spacing:0.5px;'>"
                        f"{item['sources']}</span><br>"
                        f"<h4 style='margin: 8px 0px 4px 0px; font-size:1.05rem; font-weight:700;'>{item['nom']}</h4>"
                        f"<code style='background:rgba(128,128,128,0.15); padding:3px 6px; border-radius:3px; color:#777; font-size: 0.78rem; word-break:break-all;'>{item['chemin']}</code><br>"
                        f"<div style='margin-top: 10px;'>{generer_html_boutons(item['chemin'])}</div>"
                        f"</div>"
                    )
                
                autres = resultats_finaux[3:8]
                if autres:
                    reponse += "<details style='margin-top: 20px; font-size:0.9em;'><summary style='cursor:pointer; color:#0288d1; font-weight:bold;'>📂 Voir les résultats secondaires</summary><ul style='padding-top:10px; list-style-type: none;'>"
                    for i in autres:
                        reponse += f"<li style='margin-bottom:10px;'>💾 <b>{i['nom']}</b> <br><i style='color:#f57c00; font-size:0.8rem;'>{i['sources']}</i> <br><span style='color:grey;font-size:0.75rem;'>{i['chemin']}</span></li>"
                    reponse += "</ul></details>"
                
                message_placeholder.markdown(reponse, unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": reponse})
            else:
                msg = "❌ Opération Blanche. Aucun document ne correspond à cette recherche hybride ou vous n'avez pas les droits nécessaires."
                message_placeholder.error(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})