param(
  [Parameter(Mandatory=$true)]
  [ValidateScript({ Test-Path $_ -PathType Leaf })]
  [string]$Project,
  [Parameter(Mandatory=$true)]
  [ValidateScript({ Test-Path $_ -PathType Leaf })]
  [string]$Plan,
  [int]$TimeoutSeconds = 90
)

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class Win32RAS {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lp);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, EnumWindowsProc cb, IntPtr lp);
  [DllImport("user32.dll", CharSet=CharSet.Auto)] public static extern int GetClassName(IntPtr hWnd, StringBuilder s, int nMaxCount);
  [DllImport("user32.dll", CharSet=CharSet.Auto)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder s, int nMaxCount);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
}
'@

function Get-Text([IntPtr]$h) {
  $b = New-Object System.Text.StringBuilder 2048
  [void][Win32RAS]::GetWindowText($h,$b,$b.Capacity)
  return $b.ToString()
}
function Get-Class([IntPtr]$h) {
  $b = New-Object System.Text.StringBuilder 256
  [void][Win32RAS]::GetClassName($h,$b,$b.Capacity)
  return $b.ToString()
}

$log = Join-Path (Split-Path $Project) 'ras_prepare_dialogs.log'
"START $(Get-Date -Format o)" | Set-Content -Encoding UTF8 $log
$rasExe = 'C:\Program Files (x86)\HEC\HEC-RAS\7.0.1\Ras.exe'
$proc = Start-Process -FilePath $rasExe -ArgumentList @('-c',('"'+$Project+'"'),('"'+$Plan+'"')) -PassThru
"Ras.exe PID=$($proc.Id)" | Add-Content $log
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$seen = @{}

while ((Get-Date) -lt $deadline) {
  $active = @{}
  Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName.ToLower() -in @('ras','pipeserver','rasprocess','rasplotdriver') } | ForEach-Object { $active[[uint32]$_.Id] = $_.ProcessName }

  $topCb = [Win32RAS+EnumWindowsProc]{ param([IntPtr]$h,[IntPtr]$lp)
    if (-not [Win32RAS]::IsWindowVisible($h)) { return $true }
    if ((Get-Class $h) -ne '#32770') { return $true }
    [uint32]$windowPid = 0
    [void][Win32RAS]::GetWindowThreadProcessId($h,[ref]$windowPid)
    if (-not $active.ContainsKey($windowPid)) { return $true }
    if ($seen.ContainsKey($h.ToInt64())) { return $true }

    $title = Get-Text $h
    $bodyParts = New-Object System.Collections.Generic.List[string]
    $buttons = New-Object System.Collections.Generic.List[object]
    $childCb = [Win32RAS+EnumWindowsProc]{ param([IntPtr]$c,[IntPtr]$clp)
      $cls = Get-Class $c; $txt = Get-Text $c
      if ($cls -eq 'Static' -and $txt) { $bodyParts.Add($txt) }
      if ($cls -eq 'Button' -and $txt) { $buttons.Add([pscustomobject]@{H=$c;Text=$txt}) }
      return $true
    }
    [void][Win32RAS]::EnumChildWindows($h,$childCb,[IntPtr]::Zero)
    $preferred = @('OK','&OK','Yes','&Yes','Close','&Close','Accept','&Accept','I Agree','Agree')
    $pick = $null
    foreach($want in $preferred) {
      $norm = $want.Replace('&','').Trim().ToLower()
      $pick = $buttons | Where-Object { $_.Text.Replace('&','').Trim().ToLower() -eq $norm } | Select-Object -First 1
      if($pick){ break }
    }
    if(-not $pick){ $pick = $buttons | Select-Object -First 1 }
    $body = ($bodyParts -join ' | ')
    if($pick) {
      "DIALOG pid=$windowPid process=$($active[$windowPid]) title=[$title] body=[$body] click=[$($pick.Text)]" | Add-Content $log
      [void][Win32RAS]::SendMessage($pick.H,0x00F5,[IntPtr]::Zero,[IntPtr]::Zero)
    } else {
      "DIALOG pid=$windowPid process=$($active[$windowPid]) title=[$title] body=[$body] NO_BUTTON" | Add-Content $log
    }
    $seen[$h.ToInt64()] = $true
    return $true
  }
  [void][Win32RAS]::EnumWindows($topCb,[IntPtr]::Zero)

  try { $proc.Refresh() } catch {}
  if($proc.HasExited) { break }
  Start-Sleep -Milliseconds 750
}

try { $proc.Refresh() } catch {}
if(-not $proc.HasExited) {
  "TIMEOUT Ras.exe still running" | Add-Content $log
  Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
} else {
  "EXIT code=$($proc.ExitCode)" | Add-Content $log
}
"END $(Get-Date -Format o)" | Add-Content $log
Get-Content $log
