@echo off
(
echo ========================================================
echo [ %DATE% %TIME% ] DEMARRAGE DU SERVEUR IA
echo ========================================================

echo [ 1 ] Deplacement dans le repertoire...
cd /d "C:\AGENT_IA"

echo [ 2 ] Activation de Conda...
call "C:\ProgramData\miniconda3\Scripts\activate.bat" base

echo [ 3 ] Configuration de l'environnement pour Compte de Service...
:: On force Streamlit a ecrire dans notre dossier plutot que dans C:\Users
mkdir "C:\AGENT_IA\.streamlit" 2>nul
set USERPROFILE=C:\AGENT_IA
set HOMEPATH=\AGENT_IA
set HOMEDRIVE=C:
set STREAMLIT_CONFIG_DIR=C:\AGENT_IA\.streamlit
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

echo [ 4 ] Lancement de Streamlit...
"C:\ProgramData\miniconda3\python.exe" -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true --server.fileWatcherType none

echo [ 5 ] Arret inattendu du serveur.
) >> "C:\AGENT_IA\console_brute_streamlit.txt" 2>&1

