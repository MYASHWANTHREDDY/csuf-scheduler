param(
  [string]$BaseUrl = "https://csuf-scheduler.onrender.com",
  [string]$Email = "admin@csuf.edu",
  [string]$Password = "password"
)

$ErrorActionPreference = "Stop"

function Parse-ShiftDateTime {
  param(
    [string]$DateStr,
    [string]$Range
  )
  $normalizedRange = $Range.Replace([char]8211, '-').Replace([char]8212, '-')
  $parts = $normalizedRange -split '-'
  $startText = "{0} {1}" -f $DateStr, $parts[0].Trim()
  $endText = "{0} {1}" -f $DateStr, $parts[1].Trim()
  $start = [datetime]::ParseExact($startText, "yyyy-MM-dd HH:mm", $null)
  $end = [datetime]::ParseExact($endText, "yyyy-MM-dd HH:mm", $null)
  if ($end -le $start) { $end = $end.AddDays(1) }
  return @($start, $end)
}

$s = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$loginBody = @{ email = $Email; password = $Password } | ConvertTo-Json
$null = Invoke-RestMethod -Uri "$BaseUrl/api/users/login" -Method Post -WebSession $s -ContentType "application/json" -Body $loginBody

$schedules = Invoke-RestMethod -Uri "$BaseUrl/api/scheduler/schedules" -Method Get -WebSession $s
$latest = $schedules | Sort-Object id -Descending | Select-Object -First 1
if (-not $latest) {
  Write-Host "No schedules found."
  exit 1
}

$sch = Invoke-RestMethod -Uri "$BaseUrl/api/scheduler/schedules/$($latest.id)" -Method Get -WebSession $s
$cfg = Invoke-RestMethod -Uri "$BaseUrl/api/scheduler/configs/$($sch.config_id)" -Method Get -WebSession $s

$data = @($sch.schedule_data)
$ass = @{}
$hrs = @{}
$issues = New-Object System.Collections.ArrayList
$coverageIssues = New-Object System.Collections.ArrayList

foreach ($day in $data) {
  $dow = [int]([datetime]::ParseExact($day.date, "yyyy-MM-dd", $null).DayOfWeek)
  $slot = @{ PS_AM = 0; PS_PM = 0; PSL = 0 }

  foreach ($sh in @($day.shifts)) {
    $times = Parse-ShiftDateTime -DateStr $day.date -Range $sh.time
    $assigned = @($sh.assigned)

    if ($sh.name -eq "Morning 6hr" -or $sh.name -eq "Morning 12hr") { $slot.PS_AM += $assigned.Count }
    if ($sh.name -eq "Morning 12hr" -or $sh.name -eq "Afternoon 6hr" -or $sh.name -eq "Afternoon 12hr") { $slot.PS_PM += $assigned.Count }
    if ($sh.name -eq "Afternoon 12hr" -or $sh.name -eq "Evening 6hr") { $slot.PSL += $assigned.Count }

    $seen = @{}
    foreach ($e in $assigned) {
      $id = [string]$e.employee_id
      if ($seen.ContainsKey($id)) {
        [void]$issues.Add("Duplicate same-shift assignment: employee $id on $($day.date) $($sh.name)")
      }
      $seen[$id] = $true

      if (-not $ass.ContainsKey($id)) { $ass[$id] = @() }
      $ass[$id] += [pscustomobject]@{
        S = $times[0]
        E = $times[1]
        D = $day.date
        N = $sh.name
        H = [double]$sh.duration_hours
      }

      if (-not $hrs.ContainsKey($id)) { $hrs[$id] = 0.0 }
      $hrs[$id] += [double]$sh.duration_hours
    }
  }

  if ($cfg.daily_staffing_requirements) {
    $reqAM = [int]$cfg.daily_staffing_requirements.PS_AM."$dow"
    $reqPM = [int]$cfg.daily_staffing_requirements.PS_PM."$dow"
    $reqPSL = [int]$cfg.daily_staffing_requirements.PSL."$dow"

    if ($slot.PS_AM -lt $reqAM) {
      [void]$coverageIssues.Add("$($day.date) PS_AM short by $($reqAM - $slot.PS_AM) (have $($slot.PS_AM), need $reqAM)")
    }
    if ($slot.PS_PM -lt $reqPM) {
      [void]$coverageIssues.Add("$($day.date) PS_PM short by $($reqPM - $slot.PS_PM) (have $($slot.PS_PM), need $reqPM)")
    }
    if ($slot.PSL -lt $reqPSL) {
      [void]$coverageIssues.Add("$($day.date) PSL short by $($reqPSL - $slot.PSL) (have $($slot.PSL), need $reqPSL)")
    }
  }
}

$overlaps = 0
$restViolations = 0
$hoursViolations = 0
$consecutiveViolations = 0

foreach ($id in $ass.Keys) {
  $arr = @($ass[$id] | Sort-Object S)

  if ($hrs[$id] -gt [double]$cfg.max_weekly_hours) {
    $hoursViolations++
    [void]$issues.Add("Hours violation: employee $id has $([math]::Round($hrs[$id],1))h above max $($cfg.max_weekly_hours)h")
  }

  for ($i = 1; $i -lt $arr.Count; $i++) {
    if ($arr[$i].S -lt $arr[$i - 1].E) {
      $overlaps++
      [void]$issues.Add("Overlap: employee $id on $($arr[$i].D)")
    }

    $rest = ($arr[$i].S - $arr[$i - 1].E).TotalHours
    if ($rest -lt [double]$cfg.min_rest_hours) {
      $restViolations++
      [void]$issues.Add("Rest violation: employee $id only $([math]::Round($rest,1))h below min $($cfg.min_rest_hours)h")
    }
  }

  $days = @($arr | ForEach-Object { [datetime]::ParseExact($_.D, "yyyy-MM-dd", $null) } | Sort-Object -Unique)
  $streak = 1
  for ($i = 1; $i -lt $days.Count; $i++) {
    if (($days[$i] - $days[$i - 1]).TotalDays -eq 1) {
      $streak++
    } else {
      $streak = 1
    }
    if ($streak -gt [int]$cfg.max_consecutive_days) {
      $consecutiveViolations++
      [void]$issues.Add("Consecutive-days violation: employee $id streak $streak above max $($cfg.max_consecutive_days)")
      break
    }
  }
}

$flags = @($sch.flags_data)
$underFlags = @($flags | Where-Object { $_.issue -like "*Understaffed*" })

Write-Host ("AUDIT schedule_id={0} config_id={1} status={2}" -f $sch.id, $sch.config_id, $sch.status)
Write-Host ("RULES max_weekly={0} min_rest={1} max_consecutive={2}" -f $cfg.max_weekly_hours, $cfg.min_rest_hours, $cfg.max_consecutive_days)
Write-Host ("COUNTS overlaps={0} rest_violations={1} weekly_hours_violations={2} consecutive_day_violations={3} coverage_shortfalls={4} understaffed_flags={5}" -f $overlaps, $restViolations, $hoursViolations, $consecutiveViolations, $coverageIssues.Count, $underFlags.Count)

if ($coverageIssues.Count -gt 0) {
  Write-Host "\nCOVERAGE_SHORTFALLS (first 15):"
  $coverageIssues | Select-Object -First 15 | ForEach-Object { Write-Host "- $_" }
}

if ($issues.Count -gt 0) {
  Write-Host "\nPOLICY_ISSUES (first 20):"
  $issues | Select-Object -First 20 | ForEach-Object { Write-Host "- $_" }
}

if ($underFlags.Count -gt 0) {
  Write-Host "\nUNDERSTAFFED_FLAGS (first 12):"
  $underFlags | Select-Object -First 12 | ForEach-Object {
    $d = $_.date
    $shift = $_.shift
    $req = $_.required
    $asg = $_.assigned
    Write-Host "- $d $shift need=$req assigned=$asg"
  }
}
