[Setup]
AppId=ChessBookArena
AppName=CHESS BOOK ARENA
AppVersion=0.1.0
DefaultDirName={localappdata}\Programs\ChessBookArena
DefaultGroupName=CHESS BOOK ARENA
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=CHESS-BOOK-ARENA-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\CHESS-BOOK-ARENA.exe
[Files]
Source: "..\dist\CHESS-BOOK-ARENA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\examples\*"; DestDir: "{app}\examples"; Flags: ignoreversion
Source: "..\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\THIRD-PARTY.md"; DestDir: "{app}"
[Icons]
Name: "{group}\CHESS BOOK ARENA"; Filename: "{app}\CHESS-BOOK-ARENA.exe"
Name: "{autodesktop}\CHESS BOOK ARENA"; Filename: "{app}\CHESS-BOOK-ARENA.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"
[Run]
Filename: "{app}\CHESS-BOOK-ARENA.exe"; Description: "Launch CHESS BOOK ARENA"; Flags: nowait postinstall skipifsilent
