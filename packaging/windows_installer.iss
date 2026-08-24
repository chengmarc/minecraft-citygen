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

[Code]
var
  DeleteGeneratedDataSelected: Boolean;

function InitializeUninstall(): Boolean;
begin
  DeleteGeneratedDataSelected := True;
  Result := True;
end;

procedure InitializeUninstallProgressForm();
var
  Form: TSetupForm;
  DescriptionLabel: TNewStaticText;
  DeleteGeneratedDataCheckBox: TNewCheckBox;
  UninstallButton, CancelButton: TNewButton;
  ButtonWidth: Integer;
begin
  if UninstallSilent then
    Exit;

  Form := CreateCustomForm(ScaleX(430), ScaleY(170), False, True);
  try
    Form.Caption := 'Uninstall CityGen';

    DescriptionLabel := TNewStaticText.Create(Form);
    DescriptionLabel.AutoSize := False;
    DescriptionLabel.WordWrap := True;
    DescriptionLabel.Left := ScaleX(12);
    DescriptionLabel.Top := ScaleY(12);
    DescriptionLabel.Width := Form.ClientWidth - ScaleX(24);
    DescriptionLabel.Caption := 'Choose whether to delete generated artifacts and saved settings before uninstall starts.';
    DescriptionLabel.Parent := Form;
    DescriptionLabel.AdjustHeight;

    DeleteGeneratedDataCheckBox := TNewCheckBox.Create(Form);
    DeleteGeneratedDataCheckBox.Parent := Form;
    DeleteGeneratedDataCheckBox.Caption := 'Delete generated artifacts and saved settings';
    DeleteGeneratedDataCheckBox.Checked := DeleteGeneratedDataSelected;
    DeleteGeneratedDataCheckBox.Left := DescriptionLabel.Left;
    DeleteGeneratedDataCheckBox.Top := DescriptionLabel.Top + DescriptionLabel.Height + ScaleY(14);
    DeleteGeneratedDataCheckBox.Width := DescriptionLabel.Width;
    DeleteGeneratedDataCheckBox.Height := ScaleY(34);

    UninstallButton := TNewButton.Create(Form);
    UninstallButton.Parent := Form;
    UninstallButton.Caption := 'Uninstall';
    UninstallButton.Top := Form.ClientHeight - ScaleY(33);
    UninstallButton.Height := ScaleY(23);
    UninstallButton.ModalResult := mrOk;
    UninstallButton.Default := True;

    CancelButton := TNewButton.Create(Form);
    CancelButton.Parent := Form;
    CancelButton.Caption := 'Cancel';
    CancelButton.Top := UninstallButton.Top;
    CancelButton.Height := UninstallButton.Height;
    CancelButton.ModalResult := mrCancel;
    CancelButton.Cancel := True;

    ButtonWidth := Form.CalculateButtonWidth([UninstallButton.Caption, CancelButton.Caption]);
    UninstallButton.Width := ButtonWidth;
    CancelButton.Width := ButtonWidth;
    CancelButton.Left := Form.ClientWidth - ButtonWidth - ScaleX(10);
    UninstallButton.Left := CancelButton.Left - ButtonWidth - ScaleX(6);

    Form.ActiveControl := UninstallButton;
    Form.FlipAndCenterIfNeeded(True, UninstallProgressForm, False);

    if Form.ShowModal() = mrOk then
      DeleteGeneratedDataSelected := DeleteGeneratedDataCheckBox.Checked
    else
      Abort;
  finally
    Form.Free();
  end;
end;

procedure DeleteGeneratedDataDirectory(Path: String);
begin
  if DirExists(Path) then
  begin
    Log('Deleting CityGen generated data: ' + Path);
    if not DelTree(Path, True, True, True) then
      Log('CityGen generated data could not be fully deleted: ' + Path);
  end;
end;

procedure DeleteGeneratedData();
begin
  DeleteGeneratedDataDirectory(ExpandConstant('{app}\artifacts'));
  DeleteGeneratedDataDirectory(ExpandConstant('{app}\src\config'));
  RemoveDir(ExpandConstant('{app}\src'));

  DeleteGeneratedDataDirectory(ExpandConstant('{localappdata}\CityGen\artifacts'));
  DeleteGeneratedDataDirectory(ExpandConstant('{localappdata}\CityGen\src\config'));
  RemoveDir(ExpandConstant('{localappdata}\CityGen\src'));
  RemoveDir(ExpandConstant('{localappdata}\CityGen'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if DeleteGeneratedDataSelected then
      DeleteGeneratedData()
    else
      Log('Keeping CityGen generated artifacts and saved settings.');
  end;
end;
