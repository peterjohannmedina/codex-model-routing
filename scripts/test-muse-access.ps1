[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://192.168.1.214:4000/v1',
    [string]$Model = 'muse',
    [ValidateRange(1, 32768)]
    [int]$MaxTokens = 1024,
    [ValidateRange(1, 600)]
    [int]$TimeoutSec = 180,
    [switch]$CatalogOnly
)

$ErrorActionPreference = 'Stop'
$normalizedBaseUrl = $BaseUrl.TrimEnd('/')
$modelsUri = "$normalizedBaseUrl/models"
$completionsUri = "$normalizedBaseUrl/chat/completions"

function Write-Result {
    param(
        [hashtable]$Result,
        [int]$ExitCode = 0
    )

    $Result | ConvertTo-Json -Depth 8
    if ($ExitCode -ne 0) {
        exit $ExitCode
    }
}

try {
    $modelsResponse = Invoke-WebRequest -Uri $modelsUri -Method Get -UseBasicParsing -TimeoutSec $TimeoutSec
    $models = $modelsResponse.Content | ConvertFrom-Json
} catch {
    Write-Result -Result @{
        status = 'fail'
        stage = 'catalog'
        endpoint = $modelsUri
        model = $Model
        error = $_.Exception.Message
    } -ExitCode 1
}

$modelIds = @($models.data | ForEach-Object { [string]$_.id })
$catalogAdvertised = $modelIds -contains $Model
if (-not $catalogAdvertised) {
    Write-Result -Result @{
        status = 'fail'
        stage = 'catalog'
        endpoint = $modelsUri
        model = $Model
        catalog_advertised = $false
        advertised_models = $modelIds
    } -ExitCode 1
}

if ($CatalogOnly) {
    Write-Result -Result @{
        status = 'pass'
        stage = 'catalog'
        endpoint = $modelsUri
        model = $Model
        catalog_advertised = $true
    }
    exit 0
}

$payload = @{
    model = $Model
    messages = @(
        @{
            role = 'user'
            content = 'Answer with exactly the two words: MUSE ONLINE'
        }
    )
    max_tokens = $MaxTokens
    temperature = 0
    stream = $false
} | ConvertTo-Json -Depth 8

$started = Get-Date
try {
    $completion = Invoke-RestMethod -Uri $completionsUri -Method Post -ContentType 'application/json' -Body $payload -TimeoutSec $TimeoutSec
} catch {
    Write-Result -Result @{
        status = 'fail'
        stage = 'completion'
        endpoint = $completionsUri
        model = $Model
        catalog_advertised = $true
        error = $_.Exception.Message
    } -ExitCode 1
}
$elapsedSeconds = [math]::Round(((Get-Date) - $started).TotalSeconds, 2)

$choice = @($completion.choices)[0]
$message = $choice.message
$content = if ($null -eq $message.content) { '' } else { [string]$message.content }
$reasoning = if ($null -eq $message.reasoning_content) { '' } else { [string]$message.reasoning_content }
$reportedModel = if ($null -eq $completion.model) { '' } else { [string]$completion.model }
$contentUsable = $content.Trim().Length -gt 0
$reportedModelMatches = $reportedModel -eq $Model
$passed = $contentUsable -and $reportedModelMatches

Write-Result -Result @{
    status = if ($passed) { 'pass' } else { 'fail' }
    stage = 'completion'
    endpoint = $completionsUri
    model = $Model
    catalog_advertised = $true
    request_succeeded = $true
    reported_model = $reportedModel
    reported_model_matches_request = $reportedModelMatches
    finish_reason = [string]$choice.finish_reason
    content_usable = $contentUsable
    content_length = $content.Length
    reasoning_length = $reasoning.Length
    elapsed_seconds = $elapsedSeconds
    max_tokens = $MaxTokens
} -ExitCode ([int](-not $passed))
