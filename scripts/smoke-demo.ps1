param(
    [string]$ApiBaseUrl = "",
    [string]$OutputDir = "logs\smoke",
    [string]$SessionId = "script-smoke",
    [switch]$ExecuteScreenActions,
    [int]$TimeoutSec = 90
)

. "$PSScriptRoot\poc-common.ps1"

$root = Get-PocRepoRoot
$config = Get-PocConfig -Root $root
if (-not $ApiBaseUrl) {
    $ApiBaseUrl = $config.ApiBaseUrl
}
$ApiBaseUrl = $ApiBaseUrl.TrimEnd("/")

$cases = @(
    @{ id = "GEN-W-001"; text = "我是演示嘉宾"; expected_type = "answer"; contains = "通用可配置数字人" },
    @{ id = "GEN-K-001"; text = "这个系统能做什么？"; expected_type = "answer"; contains = "语音唤醒" },
    @{ id = "GEN-D-001"; text = "当前核心指标怎么样？"; expected_type = "answer"; contains = "示例指标" },
    @{ id = "GEN-S-001"; text = "请切换到成品库存页面"; expected_type = "screen_control"; action_id = "SWITCH_TAB_ORG" },
    @{ id = "GEN-S-002"; text = "返回总览"; expected_type = "screen_control"; action_id = "SWITCH_HOME" }
)

$results = @()
foreach ($case in $cases) {
    $body = @{
        session_id = "$SessionId-$(Get-PocTimestamp)"
        text = $case.text
        context = @{
            mode = "smoke"
            screen_id = "scripts"
        }
    } | ConvertTo-Json -Depth 6

    $started = Get-Date
    try {
        $response = Invoke-PocJsonRequest -Uri "$ApiBaseUrl/api/chat" -Method Post -Body $body -TimeoutSec $TimeoutSec
        $ok = $response.type -eq $case.expected_type
        $actionId = ""
        if (($response.PSObject.Properties.Name -contains "action") -and $null -ne $response.action) {
            $actionId = [string]$response.action.id
        }
        if ($ok -and $case.ContainsKey("contains")) {
            $ok = ([string]$response.speak_text).Contains([string]$case.contains)
        }
        if ($ok -and $case.ContainsKey("action_id")) {
            $ok = $actionId -eq $case.action_id
        }
        $executeResult = $null
        if ($ok -and $ExecuteScreenActions -and $response.type -eq "screen_control") {
            $executeBody = @{
                session_id = $response.session_id
                action_id = $actionId
                params = @{}
            } | ConvertTo-Json -Depth 6
            $executeResult = Invoke-PocJsonRequest -Uri "$ApiBaseUrl/api/screen/execute" -Method Post -Body $executeBody -TimeoutSec 15
            $ok = [bool]$executeResult.success
        }
        $screenExecuted = $false
        if ($executeResult) {
            $screenExecuted = [bool]$executeResult.success
        }

        $results += [pscustomobject]@{
            id = $case.id
            text = $case.text
            ok = $ok
            type = $response.type
            action_id = $actionId
            latency_ms = [int]((Get-Date) - $started).TotalMilliseconds
            speak_text = $response.speak_text
            screen_executed = $screenExecuted
            error = $null
        }
    } catch {
        $results += [pscustomobject]@{
            id = $case.id
            text = $case.text
            ok = $false
            type = ""
            action_id = ""
            latency_ms = [int]((Get-Date) - $started).TotalMilliseconds
            speak_text = ""
            screen_executed = $false
            error = $_.Exception.Message
        }
    }
}

$fullOutputDir = if ([System.IO.Path]::IsPathRooted($OutputDir)) { $OutputDir } else { Join-Path $root $OutputDir }
New-Item -ItemType Directory -Force -Path $fullOutputDir | Out-Null
$stamp = Get-PocTimestamp
$jsonPath = Join-Path $fullOutputDir "smoke-demo-$stamp.json"
$mdPath = Join-Path $fullOutputDir "smoke-demo-$stamp.md"
$results | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

$lines = @(
    "# Demo smoke result",
    "",
    "- Generated: $(Get-Date -Format s)",
    "- API: $ApiBaseUrl",
    "",
    "| ID | OK | Type | Latency | Action | Text |",
    "| --- | --- | --- | ---: | --- | --- |"
)
foreach ($result in $results) {
    $text = ([string]$result.speak_text).Replace("|", "\|")
    if (-not $text -and $result.error) {
        $text = ([string]$result.error).Replace("|", "\|")
    }
    $lines += "| $($result.id) | $($result.ok) | $($result.type) | $($result.latency_ms) ms | $($result.action_id) | $text |"
}
$lines -join "`n" | Set-Content -LiteralPath $mdPath -Encoding UTF8

$results | Format-Table id, ok, type, latency_ms, action_id -AutoSize
Write-Host "Smoke report: $mdPath"

if (@($results | Where-Object { -not $_.ok }).Count -gt 0) {
    exit 1
}
exit 0
