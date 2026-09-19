[Setup]
AppName=OSINT Nexus
AppVersion=1.0.0
DefaultDirName={localappdata}\Programs\OSINT Nexus
DefaultGroupName=OSINT Nexus
OutputDir=dist
OutputBaseFilename=OSINT-Nexus-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
ChangesAssociations=yes
SetupIconFile=app\icon.ico
UninstallDisplayIcon={app}\osint-nexus.exe

[Files]
Source: "dist\osint-nexus\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\OSINT Nexus"; Filename: "{app}\osint-nexus.exe"
Name: "{userdesktop}\OSINT Nexus"; Filename: "{app}\osint-nexus.exe"

[Run]
Filename: "{app}\osint-nexus.exe"; Description: "Launch OSINT Nexus"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Registry]
Root: HKCU; Subkey: "Software\Classes\.osint"; ValueType: string; ValueName: ""; ValueData: "OSINTNexusFile"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\OSINTNexusFile"; ValueType: string; ValueName: ""; ValueData: "OSINT Nexus Workspace"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\OSINTNexusFile\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\osint-nexus.exe,0"
Root: HKCU; Subkey: "Software\Classes\OSINTNexusFile\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\osint-nexus.exe"" ""%1"""
