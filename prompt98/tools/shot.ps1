param([string]$Out = "$PSScriptRoot\shot.png", [string]$Title = "프롬프트")
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public class W {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  public struct RECT { public int L, T, R, B; }
}
"@
[W]::SetProcessDPIAware() | Out-Null
$found = $null
$cb = [W+EnumProc]{ param($h, $l)
  if ([W]::IsWindowVisible($h)) {
    $sb = New-Object System.Text.StringBuilder 512
    [W]::GetWindowText($h, $sb, 512) | Out-Null
    if ($sb.ToString().Contains($Title)) { $script:found = $h; return $false }
  }
  return $true }
[W]::EnumWindows($cb, [IntPtr]::Zero) | Out-Null
if (-not $found) { Write-Output "window not found"; exit 1 }
[W]::SetForegroundWindow($found) | Out-Null
Start-Sleep -Milliseconds 400
$r = New-Object W+RECT
[W]::GetWindowRect($found, [ref]$r) | Out-Null
$w = $r.R - $r.L; $h = $r.B - $r.T
$bmp = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
Write-Output "saved $Out ${w}x${h}"
