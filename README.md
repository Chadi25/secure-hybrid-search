# Secure Hybrid Search AI (ChadiBot V4)

Ce projet est un moteur de recherche documentaire hybride et sécurisé (Lexical + Sémantique Vectoriel) conçu pour s'interfacer avec un serveur de fichiers d'entreprise. Il respecte scrupuleusement les droits NTFS des utilisateurs (SSO Active Directory) et se met à jour en temps réel lors de l'ajout, de la modification ou de la suppression de fichiers.

## 🚀 Architecture

Le projet est divisé en deux parties principales :

1. **Serveur de Fichiers (FILE SERVER) :**
   - **`Watcher_IA.ps1`** : Un script PowerShell qui surveille les modifications de fichiers en temps réel et notifie le serveur IA via un webhook.
   - **`lanceur_ia.ps1` & `doc_ia_protocol.reg`** : Un gestionnaire de protocole (`doc-ia://`) permettant d'ouvrir des documents directement depuis le navigateur web de manière sécurisée.
   - **`web.config`** : Configuration IIS pour gérer le Reverse Proxy vers l'interface Streamlit et transmettre l'identité de l'utilisateur (SSO).

2. **Serveur IA (AI SERVER) :**
   - **`app.py`** : L'interface utilisateur développée avec Streamlit. Elle interroge Ollama (LLM) pour la compréhension du langage naturel, filtre les résultats via SQLite (Lexical), utilise FAISS (Vectoriel Sémantique) et valide les droits d'accès en direct.
   - **`api_webhook.py`** : API Flask qui écoute les événements du serveur de fichiers et met à jour dynamiquement la base SQLite et le cerveau vectoriel FAISS.
   - **`init_faiss_v4.py`** : Script de construction et d'entraînement initial du modèle vectoriel de recherche sémantique.
   - **`start_faiss_background.bat`** : Batch pour reconstruire l'index en tâche de fond.

## ⚙️ Déploiement

Avant de déployer, vous devez parcourir le code et rechercher le tag `[MODIFIER_ICI]`. Voici les étapes principales :

### 1. Préparation du Serveur IA
- Installez les dépendances via `pip install -r requirements.txt`.
- Assurez-vous d'avoir une instance **Ollama** fonctionnelle avec le modèle `llama3.2` ou modifiez la variable `URL_OLLAMA` dans `app.py`.
- Modifiez les variables de chemin (logs, lecteurs réseaux) dans `api_webhook.py` et `app.py`.
- Lancer la création de l'index initial via `start_faiss_background.bat`.
- Démarrez l'API webhook et l'interface Streamlit (ex: via des services Windows ou un gestionnaire de processus).

### 2. Préparation du Serveur de Fichiers
- Adaptez les adresses IP et chemins réseau dans `Watcher_IA.ps1` et lancez-le en tâche de fond.
- Déployez la configuration IIS `web.config` pour exposer le portail Web.
- Déployez `doc_ia_protocol.reg` et `lanceur_ia.ps1` via GPO sur les postes clients pour que les liens "Ouvrir" / "Editer" fonctionnent dans l'interface.

## 🔒 Sécurité
- **Authentification SSO** : Le serveur WebIIS frontal s'occupe de l'authentification et passe le relais via un jeton temporaire.
- **Vérification NTFS en direct** : L'IA valide silencieusement les permissions de lecture via l'Active Directory, en garantissant que seuls les documents autorisés sont exposés à un utilisateur, avec des vérifications renforcées (Live) sur des zones dites "Sanctuaires".

## 📚 Documentation Supplémentaire
Le dossier `DOC/` contient la documentation de l'architecture originelle (du passage de la v3 à la v4 industrielle).
