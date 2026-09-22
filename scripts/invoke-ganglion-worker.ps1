[CmdletBinding()]
param(
    [string]$Prompt,
    [string]$BaseUrl = $(if ($env:GANGLION_BASE_URL) { $env:GANGLION_BASE_URL } else { 'http://127.0.0.1:8471/v1' }),
    [string]$Model = $(if ($env:GANGLION_MODEL) { $env:GANGLION_MODEL } else { 'ganglion' }),
    [string]$ApiKeyEnv = $(if ($env:GANGLION_API_KEY_ENV) { $env:GANGLION_API_KEY_ENV } else { 'HELIOS_API_TOKEN' }),
    [ValidateRange(1, 4096)]
    [int]$MaxTokens = 512,
    [ValidateRange(1, 1800)]
    [int]$TimeoutSec = 300
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($Prompt) -and [Console]::IsInputRedirected) {
    $Prompt = [Console]::In.ReadToEnd()
}
if ([string]::IsNullOrWhiteSpace($Prompt)) {
    throw 'A bounded task packet is required through -Prompt or redirected standard input.'
}

$token = [Environment]::GetEnvironmentVariable($ApiKeyEnv)
if ([string]::IsNullOrWhiteSpace($token)) {
    throw "Ganglion worker requires the '$ApiKeyEnv' environment variable."
}

$payload = @{
    model = $Model
    messages = @(
        @{
            role = 'system'
            content = 'You are a bounded local worker. Complete only the supplied task packet. Return concise evidence and uncertainty. Do not edit files, use tools, request secrets, or broaden scope.'
        },
        @{ role = 'user'; content = $Prompt }
    )
    max_tokens = $MaxTokens
    temperature = 0
    reasoning_effort = 'none'
    stream = $false
}
$headers = @{ Authorization = "Bearer $token" }
$uri = "$($BaseUrl.TrimEnd('/'))/chat/completions"

try {
    $completion = Invoke-RestMethod -Uri $uri -Headers $headers -Method Post -ContentType 'application/json' -Body ($payload | ConvertTo-Json -Depth 10) -TimeoutSec $TimeoutSec
} catch {
    throw "Ganglion worker completion failed at ${uri}: $($_.Exception.Message)"
}

$content = $completion.choices[0].message.content
if ($content -is [string]) {
    $text = $content
} else {
    $text = (@($content) | ForEach-Object {
        if ($_ -is [string]) { $_ }
        elseif ($_.text) { [string]$_.text }
        elseif ($_.content) { [string]$_.content }
    }) -join ''
}
if ([string]::IsNullOrWhiteSpace($text)) {
    throw 'Ganglion worker returned no usable assistant text.'
}

Write-Output $text.Trim()
