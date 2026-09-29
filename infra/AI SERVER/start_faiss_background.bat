@echo off
REM [MODIFY_HERE] Log file path
set LOG_FILE=C:\AGENT_IA\log_faiss_reconstruction.txt
echo ======================================================== > %LOG_FILE%
echo [ %DATE% %TIME% ] START OF FAISS REBUILD >> %LOG_FILE%
echo ======================================================== >> %LOG_FILE%

REM [MODIFY_HERE] Path to the AI agent root folder
cd /d "C:\AGENT_IA"
REM [MODIFY_HERE] Path to activate your Python/Conda environment
call "C:\ProgramData\miniconda3\Scripts\activate.bat" base
python.exe init_faiss_v4.py >> %LOG_FILE% 2>&1

echo ======================================================== >> %LOG_FILE%
echo [ %DATE% %TIME% ] END OF REBUILD >> %LOG_FILE%