# ====================================================================
# SCRIPT WATCHER IA - RETOUR V3.1 (LE VRAI CODE ORIGINAL SUR TOUT LE SERVEUR)
# ====================================================================

$Global:LogFileMain = "C:\Scripts_Admin\log_IA.txt" # [MODIFIER_ICI] Chemin du fichier de log sur votre serveur de fichiers
$DossierASurveiller = "D:\Services" # [MODIFIER_ICI] Le dossier physique à surveiller sur le serveur de fichiers
$Global:UrlWebhook = "http://<VOTRE_IP_AI_SERVER>:8000/webhook" # [MODIFIER_ICI] Remplacez par l'IP de votre serveur IA

Add-Content -Path $Global:LogFileMain -Value "======================================"
Add-Content -Path $Global:LogFileMain -Value "$(Get-Date) - [START] Démarrage V3.1 sur TOUT LE SERVEUR"

$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $DossierASurveiller
$watcher.IncludeSubdirectories = $true
# Buffer maximum pour encaisser la charge d'un disque complet
$watcher.InternalBufferSize = 65536 

$ActionBloc = {
    $Details = $Event.SourceEventArgs
    $TypeEvenement = $Details.ChangeType
    $CheminFichierLocal = $Details.FullPath
    $NomFichier = $Details.Name

    # Filtre anti-bruit pour éviter de saturer le réseau avec les fichiers temporaires
    if ($CheminFichierLocal -match "~\$|\.tmp$|\.lock$|\.bak$|\.old$") { return }

    Start-Sleep -Milliseconds 100

    # Traduction du chemin local vers le partage réseau (ex: D:\Services\ -> S:\)
    # [MODIFIER_ICI] Adaptez selon votre point de montage réseau
    $CheminReseau = $CheminFichierLocal -replace "^(?i)D:\\Services\\", "S:\"
    $Payload = @{ fichier = $CheminReseau; evenement = $TypeEvenement.ToString() } | ConvertTo-Json -Compress
    
    try {
        $PayloadBytes = [System.Text.Encoding]::UTF8.GetBytes($Payload)
        # L'appel direct qui fonctionnait très bien dans votre V3.1
        Invoke-RestMethod -Uri $Global:UrlWebhook -Method Post -Body $PayloadBytes -ContentType "application/json; charset=utf-8" -TimeoutSec 15 | Out-Null
        
        Add-Content -Path $Global:LogFileMain -Value "$(Get-Date) - [SUCCESS] $TypeEvenement : $NomFichier"
    } catch {
        Add-Content -Path $Global:LogFileMain -Value "$(Get-Date) - [ERROR] $TypeEvenement sur $NomFichier : $_"
    }
}

Register-ObjectEvent $watcher "Created" -Action $ActionBloc | Out-Null
Register-ObjectEvent $watcher "Changed" -Action $ActionBloc | Out-Null
Register-ObjectEvent $watcher "Deleted" -Action $ActionBloc | Out-Null
Register-ObjectEvent $watcher "Renamed" -Action $ActionBloc | Out-Null

$watcher.EnableRaisingEvents = $true 
Add-Content -Path $Global:LogFileMain -Value "$(Get-Date) - [INFO] Écouteur activé sur $DossierASurveiller. En attente..."

while ($true) {
    Start-Sleep -Seconds 10
}