# ====================================================================
# SCRIPT WATCHER IA - RETOUR V3.1 (LE VRAI CODE ORIGINAL SUR TOUT LE SERVEUR)
# ====================================================================

$Global:LogFileMain = "C:\Scripts_Admin\log_IA.txt" # [MODIFY_HERE] Path to the log file on your file server
$DossierASurveiller = "D:\Services" # [MODIFY_HERE] The physical folder to monitor on the file server
$Global:UrlWebhook = "http://<YOUR_AI_SERVER_IP>:8000/webhook" # [MODIFY_HERE] Replace with your AI server IP

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

    # Local path to network share translation (e.g.: D:\Services\ -> S:\)
    # [MODIFY_HERE] Adapt according to your network mount point
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