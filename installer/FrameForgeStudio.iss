#define MyAppId "{{6F628B0F-DA54-4904-9A65-BAA5A3F4C95A}}"
#define MyAppName "饺子创作台"
#define MyAppPublisher "饺子创作台"

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#ifndef SourceDir
  #error SourceDir must be provided to the compiler.
#endif

#ifndef OutputDir
  #define OutputDir SourceDir
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=饺子创作台-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
WizardResizable=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\FrameForgeStudio.exe
SetupLogging=yes
VersionInfoVersion={#AppVersion}
ChangesAssociations=no
CloseApplications=yes
#ifdef IconFile
SetupIconFile={#IconFile}
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\FrameForgeStudio.exe"; IconFilename: "{app}\jiaozi-creation-studio.ico"; IconIndex: 0
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\FrameForgeStudio.exe"; IconFilename: "{app}\jiaozi-creation-studio.ico"; IconIndex: 0; Tasks: desktopicon

[Run]
Filename: "{app}\FrameForgeStudio.exe"; Description: "启动饺子创作台"; Flags: nowait postinstall skipifsilent
