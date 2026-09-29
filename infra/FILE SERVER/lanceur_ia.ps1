# ====================================================================
# PROJET CHADIBOT - LANCEUR D'OUVERTURE DE FICHIERS CLIENT (doc-ia:)
# Emplacement : \\<VOTRE_SERVEUR_FICHIER>\services\INFORMATIQUE\lanceur_ia.ps1
# ====================================================================

param (
    [string]$UriBrute
)

# 1. Clé/Jeton secret de sécurité
$JETON_SECRET = "Jtekt2026_Chadibot*"

# Fichier de log local client pour le débogage (optionnel)
$LogFile = "$env:TEMP\log_lanceur_ia.txt"

function Write-Log([string]$message) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "[$timestamp] $message" -ErrorAction SilentlyContinue
}

try {
    Write-Log "----------------------------------------"
    Write-Log "URI reçue brute : $UriBrute"

    if ([string]::IsNullOrWhiteSpace($UriBrute)) {
        Write-Log "ERROR : Aucune URI fournie en argument."
        exit 1
    }

    # 2. Nettoyage du protocole custom "doc-ia:"
    # Exemple d'URI brute transmise par Windows : "doc-ia:OPEN|Jtekt2026_Chadibot*|S%3A%5CINFORMATIQUE%5C..."
    $payload = $UriBrute -replace "^doc-ia:", ""
    $payload = $payload.TrimEnd('/')

    # 3. Découpage du Payload (Format : ACTION|JETON|CHEMIN_ENCODE)
    $parties = $payload.Split('|')

    if ($parties.Count -lt 3) {
        Write-Log "ERROR : Format d'URI invalide. Reçu : $payload"
        exit 1
    }

    $action = $parties[0].ToUpper()
    $jetonRecu = $parties[1]
    $cheminEncode = $parties[2]

    # 4. Vérification de sécurité du jeton
    if ($jetonRecu -ne $JETON_SECRET) {
        Write-Log "ERROR : Jeton de sécurité invalide ($jetonRecu)."
        exit 1
    }

    # 5. Décodage de l'URL pour reconstituer le chemin du fichier
    $cheminFichier = [System.Uri]::UnescapeDataString($cheminEncode)
    Write-Log "Action : $action | Chemin décodé : $cheminFichier"

    # Convertit les lettres de lecteur réseau (ex: S:\) en chemin UNC si besoin
    if ($cheminFichier -match "^(?i)S:\\") {
        $cheminFichier = $cheminFichier -replace "^(?i)S:\\", "\\<VOTRE_SERVEUR_FICHIER>\Services\"
    }

    # 6. Vérification de l'existence du fichier
    if (-not (Test-Path -Path $cheminFichier)) {
        Write-Log "ERROR : Fichier introuvable sur le réseau : $cheminFichier"
        [System.Windows.Forms.MessageBox]::Show("Le fichier spécifié est introuvable sur le réseau :`n\$cheminFichier", "ChadiBot - Erreur", "OK", "Error") | Out-Null
        exit 1
    }

    # 7. Exécution selon le mode d'action
    switch (\$action) {
        "OPEN" {
            # Ouverture classique avec l'application associée dans Windows (PDF, Word, Excel, etc.)
            Write-Log "Ouverture du document avec l'application par défaut..."
            Start-Process -FilePath \$cheminFichier
        }
        "EDIT" {
            # Ouverture pour consultation/édition de code ou texte
            Write-Log "Ouverture du fichier en mode édition..."
            Start-Process -FilePath "notepad.exe" -ArgumentList "`"$cheminFichier`""
        }
        "RUN" {
            # Exécution d'un script ou d'un programme (.ps1, .bat, .exe, .msi)
            Write-Log "Exécution du programme/script..."
            \\(ext = [System.IO.Path]::GetExtension(\\)cheminFichier).ToLower()
            
            if (\$ext -eq ".msi") {
                Start-Process -FilePath "msiexec.exe" -ArgumentList "/i `"$cheminFichier`""
            } elseif (\$ext -eq ".ps1") {
                Start-Process -FilePath "powershell.exe" -ArgumentList "-ExecutionPolicy Bypass -File `"$cheminFichier`""
            } else {
                Start-Process -FilePath \$cheminFichier
            }
        }
        default {
            Write-Log "Action inconnue (\$action), tentative d'ouverture par défaut..."
            Start-Process -FilePath \$cheminFichier
        }
    }

    Write-Log "SUCCESS : Action \$action exécutée avec succès pour \$cheminFichier"

} catch {
    Write-Log "CRITICAL ERROR : \$_"
    exit 1
}
# 🛠️ Rappel du fonctionnement et du déploiement GPO
# Déploiement du script :
# Le fichier doit être placé sur le serveur de fichiers partagé : \\<VOTRE_SERVEUR_FICHIER>\services\INFORMATIQUE\lanceur_ia.ps1
# 
# Configuration de la GPO Registre Client :
# Clef : HKEY_LOCAL_MACHINE\SOFTWARE\Classes\doc-ia\shell\open\command
# Valeur (Par défaut) :
# powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File "\\<VOTRE_SERVEUR_FICHIER>\services\INFORMATIQUE\lanceur_ia.ps1" "%1"