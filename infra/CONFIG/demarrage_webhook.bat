@echo off
(
echo ========================================================
echo [ %DATE% %TIME% ] DEMARRAGE DU WEBHOOK IA
echo [ INFO ] Identite d'execution : %USERNAME%
echo ========================================================

echo [ 1 ] Deplacement dans le repertoire de travail...
cd /d "C:\AGENT_IA"

echo [ 2 ] Activation de l'environnement Conda...
call "C:\ProgramData\miniconda3\Scripts\activate.bat" base

echo [ 3 ] Lancement du Webhook via chemin absolu...
"C:\ProgramData\miniconda3\python.exe" api_webhook.py

echo [ 4 ] Arret inattendu du Webhook.
) >> "C:\AGENT_IA\console_brute_webhook.txt" 2>&1