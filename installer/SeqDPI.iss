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
WizardResizable=no
WizardSizePercent=115
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
SetupLogging=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
turkish.WelcomeLabel1=SeqDPI kurulumuna hoş geldin
turkish.WelcomeLabel2=Next'e bas, gerekli motor kurulsun, masaüstüne SeqDPI gelsin. Sonra tek tuş.
turkish.FinishedHeadingLabel=SeqDPI hazır
turkish.FinishedLabel=Kurulum bitti. Masaüstündeki SeqDPI kısayolundan neon arayüzü açabilirsin.
english.WelcomeLabel1=Welcome to SeqDPI setup
english.WelcomeLabel2=Click Next, install the engine, get SeqDPI on your desktop. Then one click.
english.FinishedHeadingLabel=SeqDPI is ready
english.FinishedLabel=Setup is complete. Open SeqDPI from your desktop shortcut.

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne SeqDPI kısayolu ekle"; GroupDescription: "Kısayollar:"; Flags: checkedonce
Name: "launchafter"; Description: "Kurulum bitince SeqDPI'yi aç"; GroupDescription: "Son adım:"; Flags: checkedonce

[InstallDelete]
Type: files; Name: "{app}\{#MyAppExeName}"

[Files]
Source: "..\dist\SeqDPI.exe"; DestDir: "{app}"; Flags: replacesameversion restartreplace uninsrestartdelete
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

procedure PaintSeqDPIWizard();
begin
  WizardForm.Color := $221013;
  WizardForm.MainPanel.Color := $221013;
  WizardForm.InnerPage.Color := $361921;
  WizardForm.Bevel.Visible := False;

  WizardForm.WizardSmallBitmapImage.Visible := False;
  WizardForm.WizardBitmapImage.Visible := False;

  WizardForm.PageNameLabel.Font.Color := $D84FFF;
  WizardForm.PageNameLabel.Font.Style := [fsBold];
  WizardForm.PageDescriptionLabel.Font.Color := $FFD939;

  WizardForm.WelcomeLabel1.Font.Color := $FDF7FF;
  WizardForm.WelcomeLabel1.Font.Style := [fsBold];
  WizardForm.WelcomeLabel2.Font.Color := $D4ACB9;

  WizardForm.FinishedHeadingLabel.Font.Color := $5CFFB8;
  WizardForm.FinishedHeadingLabel.Font.Style := [fsBold];
  WizardForm.FinishedLabel.Font.Color := $FDF7FF;

  WizardForm.NextButton.Caption := 'Next';
  WizardForm.NextButton.Font.Style := [fsBold];
end;

function InitializeSetup(): Boolean;
begin
  StopSeqDPIStuff();
  Result := True;
end;

procedure InitializeWizard();
begin
  PaintSeqDPIWizard();
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  PaintSeqDPIWizard();
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
