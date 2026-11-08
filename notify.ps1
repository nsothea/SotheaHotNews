param(
    [string]$TitleB64 = "",
    [string]$BodyB64 = "",
    [string]$UrlB64 = "",
    [string]$ButtonB64 = "",
    [string]$WebUrlB64 = "",
    [string]$WebButtonB64 = ""
)

[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlCommands, ContentType = WindowsRuntime] | Out-Null

$title = "War News Alert"
if ($TitleB64 -ne "") {
    $bytes = [System.Convert]::FromBase64String($TitleB64)
    $title = [System.Text.Encoding]::UTF8.GetString($bytes)
}

$body = "New war development detected."
if ($BodyB64 -ne "") {
    $bytes = [System.Convert]::FromBase64String($BodyB64)
    $body = [System.Text.Encoding]::UTF8.GetString($bytes)
}

$articleUrl = "https://news.google.com"
if ($UrlB64 -ne "") {
    $bytes = [System.Convert]::FromBase64String($UrlB64)
    $articleUrl = [System.Text.Encoding]::UTF8.GetString($bytes)
}

$articleButtonText = "Original Source"
if ($ButtonB64 -ne "") {
    $bytes = [System.Convert]::FromBase64String($ButtonB64)
    $articleButtonText = [System.Text.Encoding]::UTF8.GetString($bytes)
}

$webUrl = "http://localhost:5000"
if ($WebUrlB64 -ne "") {
    $bytes = [System.Convert]::FromBase64String($WebUrlB64)
    $webUrl = [System.Text.Encoding]::UTF8.GetString($bytes)
}

$webButtonText = "Open Web Portal"
if ($WebButtonB64 -ne "") {
    $bytes = [System.Convert]::FromBase64String($WebButtonB64)
    $webButtonText = [System.Text.Encoding]::UTF8.GetString($bytes)
}

$titleEscaped = [System.Security.SecurityElement]::Escape($title)
$bodyEscaped = [System.Security.SecurityElement]::Escape($body)
$articleUrlEscaped = [System.Security.SecurityElement]::Escape($articleUrl)
$articleButtonEscaped = [System.Security.SecurityElement]::Escape($articleButtonText)
$webUrlEscaped = [System.Security.SecurityElement]::Escape($webUrl)
$webButtonEscaped = [System.Security.SecurityElement]::Escape($webButtonText)

$template = @"
<toast activationType="protocol" launch="$webUrlEscaped">
    <visual>
        <binding template="ToastGeneric">
            <text>$titleEscaped</text>
            <text>$bodyEscaped</text>
        </binding>
    </visual>
    <actions>
        <action activationType="protocol" content="$webButtonEscaped" arguments="$webUrlEscaped" />
        <action activationType="protocol" content="$articleButtonEscaped" arguments="$articleUrlEscaped" />
    </actions>
    <audio src="ms-winsoundevent:Notification.Default" />
</toast>
"@

try {
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml($template)
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    $appId = "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId)
    $notifier.Show($toast)
} catch {
    Write-Error $_
}
