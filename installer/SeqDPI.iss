#define MyAppName "SeqDPI"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "SeqDPI"
#define MyAppExeName "SeqDPI.exe"

[Setup]
AppId={{A9ED9AC0-0F6D-4F3F-8E5F-71E6D0E45D71}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\dist\installer
OutputBaseFilename=SeqDPI-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
CloseApplicationsFilter=SeqDPI.exe;goodbyedpi.exe
RestartApplications=no
RestartIfNeededByRun=no
AlwaysRestart=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne SeqDPI kısayolu ekle"; GroupDescription: "Kısayollar:"; Flags: checkedonce
Name: "launchafter"; Description: "Kurulum bitince SeqDPI'yi aç"; GroupDescription: "Son adım:"; Flags: checkedonce

[InstallDelete]
Type: files; Name: "{app}\{#MyAppExeName}"

[Files]
Source: "..\dist\SeqDPI.exe"; DestDir: "{app}"; Flags: ignoreversion replacesameversion restartreplace uninsrestartdelete
Source: "..\dist\engine\*"; DestDir: "{userappdata}\SeqDPI\engine-turkey-current"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "SeqDPI'yi aç"; Flags: nowait postinstall skipifsilent; Tasks: launchafter

[UninstallDelete]
Type: files; Name: "{userappdata}\SeqDPI\seqdpi.log"

[Code]
procedure RunHidden(FileName: string; Params: string);
var
  ResultCode: Integer;
begin
  Exec(FileName, Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure StopSeqDPIStuff();
begin
  RunHidden(ExpandConstant('{sys}\taskkill.exe'), '/IM SeqDPI.exe /F /T');
  RunHidden(ExpandConstant('{sys}\taskkill.exe'), '/IM goodbyedpi.exe /F /T');
  RunHidden(ExpandConstant('{sys}\sc.exe'), 'stop GoodbyeDPI');
  RunHidden(ExpandConstant('{sys}\sc.exe'), 'delete GoodbyeDPI');
  RunHidden(ExpandConstant('{sys}\sc.exe'), 'stop WinDivert');
  RunHidden(ExpandConstant('{sys}\sc.exe'), 'stop WinDivert1.4');
  RunHidden(ExpandConstant('{sys}\sc.exe'), 'stop WinDivert2.2');
end;

function InitializeSetup(): Boolean;
begin
  StopSeqDPIStuff();
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    StopSeqDPIStuff();
end;

function InitializeUninstall(): Boolean;
begin
  StopSeqDPIStuff();
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    StopSeqDPIStuff();
end;
