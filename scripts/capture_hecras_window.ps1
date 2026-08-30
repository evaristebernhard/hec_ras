param(
  [Parameter(Mandatory=$true)]
  [ValidateScript({ Test-Path $_ -PathType Leaf })]
  [string]$Project,
  [Parameter(Mandatory=$true)]
  [string]$Output
)

Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class WinCapture {
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}
'@

$rasExe = 'C:\Program Files (x86)\HEC\HEC-RAS\7.0.1\Ras.exe'
$proc = Start-Process -FilePath $rasExe -ArgumentList @('"'+$Project+'"') -PassThru
Start-Sleep -Seconds 6
$proc.Refresh()
$h = $proc.MainWindowHandle
if($h -eq [IntPtr]::Zero) {
  $candidate = Get-Process ras -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
  if($candidate) { $proc = $candidate; $h = $candidate.MainWindowHandle }
}
if($h -eq [IntPtr]::Zero) { throw 'HEC-RAS main window not found' }
[void][WinCapture]::SetForegroundWindow($h)
Start-Sleep -Milliseconds 800
$rect = New-Object WinCapture+RECT
[void][WinCapture]::GetWindowRect($h, [ref]$rect)
$width = [Math]::Max(1, $rect.Right - $rect.Left)
$height = [Math]::Max(1, $rect.Bottom - $rect.Top)
$bmp = New-Object System.Drawing.Bitmap $width,$height
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $gfx.GetHdc()
try { [void][WinCapture]::PrintWindow($h, $hdc, 2) } finally { $gfx.ReleaseHdc($hdc) }
$gfx.Dispose()
$dir = Split-Path $Output
if(-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$bmp.Save($Output, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Output "Saved $Output ($width x $height)"
Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
