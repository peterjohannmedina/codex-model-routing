# Resolve known existing stores only. Calling this function never reads/decrypts
# a key. The launcher calls it only after admission and metered-call consent.
function Resolve-RoutingCredential {
    param([string]$ExplicitPath, [string]$PortablePath, [string]$LegacyPath)
    if ($ExplicitPath) {
        return [pscustomobject]@{ Path = $ExplicitPath; Source = 'explicit_windows_dpapi' }
    }
    if (Test-Path -LiteralPath $PortablePath -PathType Leaf) {
        return [pscustomobject]@{ Path = $PortablePath; Source = 'windows_dpapi' }
    }
    if (Test-Path -LiteralPath $LegacyPath -PathType Leaf) {
        return [pscustomobject]@{ Path = $LegacyPath; Source = 'legacy_windows_dpapi' }
    }
    return [pscustomobject]@{ Path = $null; Source = 'none' }
}
