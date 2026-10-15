[CmdletBinding(SupportsShouldProcess = $true)]
param([string]$CredentialPath)

$ErrorActionPreference = 'Stop'
$routingCodexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex' }
$routingCredentialPath = if ($CredentialPath) { $CredentialPath } else { Join-Path $routingCodexRoot 'routing\openai-key.dpapi' }
$routingSettings = Split-Path -Parent $routingCredentialPath
$routingAncestor = [IO.Path]::GetFullPath($routingSettings)
while ($routingAncestor) {
    if (Test-Path -LiteralPath (Join-Path $routingAncestor '.git')) { throw 'Credential storage must be outside repositories.' }
    $routingAncestor = Split-Path -Parent $routingAncestor
}
if ($env:OS -ne 'Windows_NT') { throw 'This optional DPAPI entry helper requires Windows. Use an existing environment-based credential on other platforms.' }
if (-not (Get-Module -Name Microsoft.PowerShell.Security)) {
    Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1') -ErrorAction Stop
}

# HUMAN-ONLY ENTRY POINT. Codex must never execute the credential prompt/import.
# Windows DPAPI binds the encrypted value to this Windows user on this computer.
# No key argument, plaintext file, global environment setting, or API request.
if ($PSCmdlet.ShouldProcess($routingCredentialPath, 'Store user-entered key encrypted with Windows DPAPI')) {
    $routingSecureKey = Read-Host 'Enter your existing OpenAI API key (hidden; never paste into chat)' -AsSecureString
    try {
        if ($routingSecureKey.Length -eq 0) { throw 'No key entered; nothing stored.' }
        New-Item -ItemType Directory -Path $routingSettings -Force | Out-Null
        $routingEncryptedKey = ConvertFrom-SecureString -SecureString $routingSecureKey
        Set-Content -LiteralPath $routingCredentialPath -Value $routingEncryptedKey -Encoding ascii -NoNewline
        Write-Output 'Saved the encrypted key for this Windows user. No API request was made.'
    } finally {
        $routingSecureKey.Dispose()
        $routingEncryptedKey = $null
    }
}
