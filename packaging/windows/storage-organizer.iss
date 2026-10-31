#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "Storage Organizer"
#define AppPublisher "Storage Organizer contributors"

[Setup]
AppId={{7B876E0F-9CA3-4B29-9E5A-535D6DFE41A9}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\Storage Organizer
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
OutputDir=..\..\release-assets
OutputBaseFilename=StorageOrganizer-Setup-{#AppVersion}-windows-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\StorageOrganizer.exe
SetupLogging=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\..\dist\StorageOrganizer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\StorageOrganizer.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\StorageOrganizer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\StorageOrganizer.exe"; Description: "Launch {#AppName}"; Flags: postinstall nowait skipifsilent
