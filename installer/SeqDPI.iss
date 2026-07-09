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
LicenseFile=
OutputDir=..\dist\installer
OutputBaseFilename=SeqDPI-Setup
SetupIconFile=
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne SeqDPI kısayolu ekle"; GroupDescription: "Kısayollar:"; Flags: checkedonce
Name: "launchafter"; Description: "Kurulum bitince SeqDPI'yi aç"; GroupDescription: "Son adım:"; Flags: checkedonce

[Files]
Source: "..\dist\SeqDPI.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "SeqDPI'yi aç"; Flags: nowait postinstall skipifsilent; Tasks: launchafter

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\SeqDPI\engine-turkey-current"
Type: files; Name: "{userappdata}\SeqDPI\seqdpi.log"
