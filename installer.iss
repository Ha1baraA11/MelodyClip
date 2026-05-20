[Setup]
AppName=SongShareTool
AppVersion=1.0.0
AppPublisher=SongShareTool
AppPublisherURL=https://github.com/Ha1baraA11/Auto-Video-Tool
DefaultDirName=D:\SongShareTool
DefaultGroupName=SongShareTool
OutputBaseFilename=SongShareTool-Setup
OutputDir=dist
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Dirs]
Name: "{app}\output"

[Files]
; 主程序目录（PyInstaller 输出）
Source: "dist\SongShareTool\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

; 内置音频文件（已由 PyInstaller 打包，此处为冗余保险）
; Source: "开头(含橱窗引导).mp3"; DestDir: "{app}"; Flags: ignoreversion
; Source: "结尾(含橱窗引导).mp3"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\歌曲分享视频生成工具"; Filename: "{app}\SongShareTool.exe"; WorkingDir: "{app}"
Name: "{group}\卸载 SongShareTool"; Filename: "{uninstallexe}"
Name: "{commondesktop}\歌曲分享视频生成工具"; Filename: "{app}\SongShareTool.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\SongShareTool.exe"; Description: "立即启动 SongShareTool"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\output"
Type: files; Name: "{app}\config.json"
