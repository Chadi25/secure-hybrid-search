# Secure Hybrid Search AI (ChadiBot V4)

This project is a hybrid and secure document search engine (Lexical + Vector Semantic) designed to interface with an enterprise file server. It strictly respects users' NTFS permissions (via Active Directory SSO) and updates in real-time when files are added, modified, or deleted.

## 🚀 Architecture

The project is divided into two main parts:

1. **File Server (FILE SERVER):**
   - **`Watcher_IA.ps1`**: A PowerShell script that monitors file modifications in real-time and notifies the AI server via a webhook.
   - **`lanceur_ia.ps1` & `doc_ia_protocol.reg`**: A custom protocol handler (`doc-ia://`) allowing users to open documents securely and directly from the web browser.
   - **`web.config`**: IIS configuration to manage the Reverse Proxy to the Streamlit interface and pass user identity (SSO).

2. **AI Server (AI SERVER):**
   - **`app.py`**: The user interface developed with Streamlit. It queries Ollama (LLM) for natural language understanding, filters results via SQLite (Lexical), uses FAISS (Semantic Vector), and validates access rights in real-time.
   - **`api_webhook.py`**: A Flask API that listens to file server events and dynamically updates the SQLite database and the FAISS vector brain.
   - **`init_faiss_v4.py`**: Script for the initial build and training of the semantic search vector model.
   - **`start_faiss_background.bat`**: A batch script to rebuild the index in the background.

## ⚙️ Deployment

Before deploying, you must go through the code and look for the `[MODIFY_HERE]` tags. Here are the main steps:

### 1. AI Server Setup
- Install the dependencies via `pip install -r requirements.txt`.
- Make sure you have a working **Ollama** instance with the `llama3.2` model, or change the `URL_OLLAMA` variable in `app.py`.
- Modify path variables (logs, network drives) in `api_webhook.py` and `app.py`.
- Start the initial index creation via `start_faiss_background.bat`.
- Start the webhook API and the Streamlit interface (e.g., via Windows services or a process manager).

### 2. File Server Setup
- Adapt IP addresses and network paths in `Watcher_IA.ps1` and run it as a background task.
- Deploy the IIS `web.config` configuration to expose the Web portal.
- Deploy `doc_ia_protocol.reg` and `lanceur_ia.ps1` via GPO on client workstations so that the "Open" / "Edit" links work properly from the UI.

## 🔒 Security
- **SSO Authentication**: The frontend WebIIS server handles authentication and passes the identity via a temporary token.
- **Live NTFS Verification**: The AI silently validates read permissions via Active Directory, ensuring that only authorized documents are exposed to a user, with reinforced (Live) checks on "Sanctuary" zones.

## 📚 Additional Documentation
The `DOC/` folder contains the original architectural documentation (covering the transition from v3 to the industrial v4).
