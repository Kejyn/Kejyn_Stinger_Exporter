#define MyAppName "Kejyn Stinger Exporter"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "KejynDev"
#define MyAppExeName "KejynStingerExporter.exe"

[Setup]
AppId={{EFB41CD1-6F67-47BB-A892-34F10D3E59D6}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Kejyn Stinger Exporter
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=KejynStingerExporter-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[Files]
Source: "..\dist\KejynStingerExporter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\build\browsers\*"; DestDir: "{app}\browsers"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Kejyn Stinger Exporter"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Kejyn Stinger Exporter"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer Kejyn Stinger Exporter"; Flags: nowait postinstall skipifsilent
