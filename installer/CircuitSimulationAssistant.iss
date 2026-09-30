; Package the existing PyInstaller onedir output without changing its contents.
#if (Ver < 0x06000000) || (Ver >= 0x07000000)
  #error This installer recipe requires Inno Setup 6.
#endif
#pragma message "Compiler version: " + Str(Ver >> 24) + "." + Str((Ver >> 16) & 255) + "." + Str((Ver >> 8) & 255)
#define AppName "Circuit Simulation Assistant"
#define AppExe "CircuitSimulationAssistant.exe"
#ifndef PortableDir
  #define PortableDir SourcePath + "..\dist\CircuitSimulationAssistant"
#endif

[Setup]
AppId={{B6C44674-7140-4DA4-94A0-DF276A147F8B}
AppName={#AppName}
AppVersion=0.1.0
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableDirPage=no
DisableProgramGroupPage=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\installer_output
OutputBaseFilename=CircuitSimulationAssistant-Setup
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
InfoBeforeFile=installation-notes.txt
CloseApplications=no
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#PortableDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch Circuit Simulation Assistant"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent runasoriginaluser

; Deliberately no UninstallDelete: retain user data and any unowned files.
[Code]
function CreateFile(FileName: String; DesiredAccess, ShareMode, SecurityAttributes,
  CreationDisposition, FlagsAndAttributes, TemplateFile: LongWord): LongWord;
  external 'CreateFileW@kernel32.dll stdcall';
function CloseHandle(Handle: LongWord): Integer;
  external 'CloseHandle@kernel32.dll stdcall';

function AppFileAvailable(): Boolean;
var
  ExePath: String;
  Handle: LongWord;
begin
  ExePath := ExpandConstant('{app}\{#AppExe}');
  Result := True;
  if not FileExists(ExePath) then exit;
  { Request a write handle, but never write. Windows denies it for a running
    executable. Sharing is allowed; this is not a process-kill mechanism. }
  Handle := CreateFile(ExePath, $40000000, 7, 0, 3, 0, 0);
  Result := Handle <> $FFFFFFFF;
  if Result then CloseHandle(Handle);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not AppFileAvailable() then
    Result := 'Close Circuit Simulation Assistant (Ctrl+C in its launcher) before continuing. If it is already closed, check access permissions to the installation folder.';
end;

function InitializeUninstall(): Boolean;
begin
  Result := AppFileAvailable();
  if not Result then
    SuppressibleMsgBox('Close Circuit Simulation Assistant (Ctrl+C in its launcher) before uninstalling. If it is already closed, check access permissions to the installation folder.', mbError, MB_OK, IDOK);
end;
