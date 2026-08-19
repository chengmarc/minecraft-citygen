#define AppName "CityGen"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #error SourceDir is required
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif
#ifndef OutputBaseFilename
  #define OutputBaseFilename "CityGen-setup"
#endif

[Setup]
AppId={{E1622F56-1DDB-4F95-BD84-B0BC71A0CE83}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=CityGen
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
SetupIconFile={#SourceDir}\app-icon.ico
UninstallDisplayIcon={app}\CityGen.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\CityGen.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\CityGen.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CityGen.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
