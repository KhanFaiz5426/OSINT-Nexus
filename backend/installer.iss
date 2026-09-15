[Setup]
AppName=OSINT Nexus
AppVersion=1.0.0
DefaultDirName={localappdata}\Programs\OSINT Nexus
DefaultGroupName=OSINT Nexus
OutputDir=dist
OutputBaseFilename=OSINT-Nexus-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Files]
Source: "dist\osint-nexus\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\OSINT Nexus"; Filename: "{app}\osint-nexus.exe"
Name: "{commondesktop}\OSINT Nexus"; Filename: "{app}\osint-nexus.exe"

[Run]
Filename: "{app}\osint-nexus.exe"; Description: "Launch OSINT Nexus"; Flags: nowait postinstall skipifsilent
