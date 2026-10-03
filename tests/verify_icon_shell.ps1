param(
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$Output,
    [switch]$ShortcutReference
)
# Read Windows Shell's actual icon for an existing exe/ico/shortcut; no cache reset.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class IconShell {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct Info {
        public IntPtr hIcon;
        public int iIcon;
        public uint attributes;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string displayName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 80)] public string typeName;
    }
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr SHGetFileInfo(string path, uint attributes, ref Info info, uint size, uint flags);
    [DllImport("user32.dll")]
    public static extern bool DestroyIcon(IntPtr icon);
}
"@
$sourcePath = (Resolve-Path -LiteralPath $Source).Path
$temporaryLink = $null
if ($ShortcutReference) {
    # A reference shortcut receives the same normal Windows arrow overlay as a real link.
    $temporaryLink = Join-Path ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($Output))) (([Guid]::NewGuid().ToString()) + '.lnk')
    $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($temporaryLink)
    $shortcut.TargetPath = $sourcePath
    $shortcut.IconLocation = $sourcePath + ',0'
    $shortcut.Save()
    $sourcePath = $temporaryLink
}
$info = New-Object IconShell+Info
try {
$result = [IconShell]::SHGetFileInfo($sourcePath, 0, [ref]$info, [Runtime.InteropServices.Marshal]::SizeOf($info), 0x100)
if ($result -eq [IntPtr]::Zero -or $info.hIcon -eq [IntPtr]::Zero) { throw 'Windows Shell did not return an icon.' }
try {
    $icon = [Drawing.Icon]::FromHandle($info.hIcon)
    $bitmap = $icon.ToBitmap()
    try { $bitmap.Save([IO.Path]::GetFullPath($Output), [Drawing.Imaging.ImageFormat]::Png) }
    finally { $bitmap.Dispose(); $icon.Dispose() }
} finally { [IconShell]::DestroyIcon($info.hIcon) | Out-Null }

} finally {
    if ($temporaryLink -and (Test-Path -LiteralPath $temporaryLink)) { Remove-Item -LiteralPath $temporaryLink -Force }
}
