#define AppVer "1.0.0"

[Setup]
AppId={{9E347ED8-1F42-49DF-B361-2B730176AC95}
AppName=Учебный комплект giga-agent для ДПО
AppVersion={#AppVer}
AppPublisher=LeonDeTur
AppPublisherURL=https://github.com/LeonDeTur/giga-agent-test
AppSupportURL=https://github.com/LeonDeTur/giga-agent-test
AppUpdatesURL=https://github.com/LeonDeTur/giga-agent-test/releases
VersionInfoVersion={#AppVer}.0
VersionInfoProductVersion={#AppVer}.0
VersionInfoCompany=LeonDeTur
VersionInfoProductName=Учебный комплект giga-agent для ДПО
VersionInfoDescription=Установщик учебного комплекта giga-agent для ДПО
VersionInfoCopyright=giga-agent: ai-forever, лицензия MIT
#ifdef SIGN
SignTool=dposign
SignedUninstaller=yes
#endif
DefaultDirName={sd}\DPO\dpo-giga-agent
DefaultGroupName=ДПО агенты
DisableDirPage=no
UsePreviousAppDir=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=dpo-giga-agent-setup
Compression=lzma2
SolidCompression=yes
; Reserve space for downloaded components.
ExtraDiskSpaceRequired=7516192768

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicons"; Description: "Создать ярлыки на рабочем столе"

[Files]
; Recreate output directories without packaging user results.
Source: "..\dpo-giga-agent\*"; DestDir: "{app}"; Excludes: ".env,.venv,.giga_agent,.cache,tools,.downloads,__pycache__,*.pyc,*.log,litellm.yaml,OFFLINE,\data\*\output"; Flags: recursesubdirs createallsubdirs ignoreversion

[Dirs]
Name: "{app}\data\01_procurement\output"
Name: "{app}\data\02_assignments\output"
Name: "{app}\data\03_appeals\output"

[Icons]
Name: "{userprograms}\ДПО агенты\ДПО агенты — запустить"; Filename: "{app}\start.cmd"; WorkingDir: "{app}"
Name: "{userprograms}\ДПО агенты\ДПО агенты — остановить"; Filename: "{app}\stop.cmd"; WorkingDir: "{app}"
Name: "{userprograms}\ДПО агенты\Удалить учебный комплект"; Filename: "{uninstallexe}"; WorkingDir: "{app}"
Name: "{userdesktop}\ДПО агенты — запустить"; Filename: "{app}\start.cmd"; WorkingDir: "{app}"; Tasks: desktopicons
Name: "{userdesktop}\ДПО агенты — остановить"; Filename: "{app}\stop.cmd"; WorkingDir: "{app}"; Tasks: desktopicons

[Run]
Filename: "{app}\install.cmd"; Parameters: "-NoShortcuts"; WorkingDir: "{app}"; Description: "Запустить установку компонентов (нужны интернет и ключ GigaChat)"; Flags: postinstall nowait skipifsilent

[UninstallRun]
; Prevent pause on failure from blocking uninstallation.
Filename: "{cmd}"; Parameters: "/c ""if exist ""{app}\tools\uv\uv.exe"" if exist ""{app}\.venv\"" ""{app}\stop.cmd"" < NUL"""; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "StopCourseServices"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\tools"
Type: filesandordirs; Name: "{app}\.cache"
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\.downloads"
Type: filesandordirs; Name: "{app}\.giga_agent"
Type: files; Name: "{app}\.env"
Type: files; Name: "{app}\litellm.yaml"
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    if Length(WizardDirValue) > 80 then
    begin
      MsgBox('Путь к папке слишком длинный: допускается не более 80 символов из-за ограничения длины путей Windows. Выберите короткий путь, например C:\DPO\dpo-giga-agent. Кириллица и пробелы допустимы.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;
