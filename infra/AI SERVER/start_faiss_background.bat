@echo off
REM [MODIFIER_ICI] Chemin du fichier de log
set LOG_FILE=C:\AGENT_IA\log_faiss_reconstruction.txt
echo ======================================================== > %LOG_FILE%
echo [ %DATE% %TIME% ] DEBUT DE LA RECONSTRUCTION FAISS >> %LOG_FILE%
echo ======================================================== >> %LOG_FILE%

REM [MODIFIER_ICI] Chemin vers le dossier racine de l'agent IA
cd /d "C:\AGENT_IA"
REM [MODIFIER_ICI] Chemin vers l'activation de votre environnement Python/Conda
call "C:\ProgramData\miniconda3\Scripts\activate.bat" base
python.exe init_faiss_v4.py >> %LOG_FILE% 2>&1

echo ======================================================== >> %LOG_FILE%
echo [ %DATE% %TIME% ] FIN DE LA RECONSTRUCTION >> %LOG_FILE%