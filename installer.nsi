; ArknightsPassMaker NSIS Installer

!pragma codepage "UTF-8"
!include "MUI2.nsh"
!include "FileFunc.nsh"

!ifndef MyAppVersion
  !define MyAppVersion "2.2"
!endif

!define MyAppName "ArknightsPassMaker"
!define MyAppNameCN "ArknightsPassMaker"
!define MyAppPublisher "Rafael-ban"
!define MyAppURL "https://github.com/rhodesepass/neo-assetmaker"
!define MyAppExeName "ArknightsPassMaker.exe"
!define MyAppIcon "resources\icons\favicon.ico"
!define AppMutex "ArknightsPassMakerMutex"
!define ArchiveName "${MyAppName}_v${MyAppVersion}.7z"

; ========== Basic Settings ==========
Name "${MyAppName}"
OutFile "dist\${MyAppName}_v${MyAppVersion}_Setup_NSIS.exe"
InstallDir "$LOCALAPPDATA\${MyAppName}"
InstallDirRegKey HKCU "Software\${MyAppName}" ""
RequestExecutionLevel user
BrandingText "${MyAppName} v${MyAppVersion}"
SetCompressor /SOLID lzma
Unicode True

; ========== Interface Settings ==========
!define MUI_ICON "${MyAppIcon}"
!define MUI_UNICON "${MyAppIcon}"
!define MUI_WELCOMEFINISHPAGE_BITMAP "resources\installer\wizard.bmp"
!define MUI_WELCOMEFINISHPAGE_BITMAP_NOSTRETCH
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "resources\installer\wizard_small.bmp"
!define MUI_HEADERIMAGE_UNBITMAP "resources\installer\wizard_small.bmp"
!define MUI_LICENSEPAGE "resources\installer\LICENSE.txt"

!define MUI_FINISHPAGE_RUN "$INSTDIR\${MyAppExeName}"
!define MUI_FINISHPAGE_SHOWREADME ""
!define MUI_FINISHPAGE_LINK "GitHub Project Page"
!define MUI_FINISHPAGE_LINK_LOCATION "${MyAppURL}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "resources\installer\LICENSE.txt"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_COMPONENTS
!insertmacro MUI_UNPAGE_DIRECTORY
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "SimpChinese"

; ========== Installation Type ==========
InstType "Full Installation"

; ========== File Installation ==========
Section "Main Program" SEC_MAIN
  SectionIn RO

  ; Clean old files on upgrade
  Call CleanOldFiles

  ; Extract 7z.exe + 7z.dll and 7z archive to temp dir
  InitPluginsDir
  SetOutPath "$PLUGINSDIR"

  ; Embed 7z.exe + 7z.dll (standalone extraction tool)
  File /oname=7z.exe "tools\nsis\7z.exe"
  File /oname=7z.dll "tools\nsis\7z.dll"

  ; Embed 7z archive
  File /oname=data.7z "dist\${ArchiveName}"

  ; Extract 7z to installation directory
  SetOutPath "$INSTDIR"
  ExecWait '"$PLUGINSDIR\7z.exe" x "$PLUGINSDIR\data.7z" -y -o"$INSTDIR"' $0

  ; Clean temp files
  Delete "$PLUGINSDIR\7z.exe"
  Delete "$PLUGINSDIR\7z.dll"
  Delete "$PLUGINSDIR\data.7z"

  ; Check extraction result
  StrCmp $0 0 +3
    MessageBox MB_ICONSTOP "Extraction failed (error code: $0). Please try again."
    Abort

  ; Write uninstall info
  WriteRegStr HKCU "Software\${MyAppName}" "" $INSTDIR
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${MyAppName}" \
                   "DisplayName" "${MyAppName}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${MyAppName}" \
                   "UninstallString" "$INSTDIR\uninst.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${MyAppName}" \
                   "QuietUninstallString" "$\"$INSTDIR\uninst.exe$\" /S"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${MyAppName}" \
                   "DisplayIcon" "$\"$INSTDIR\${MyAppExeName}$\""
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${MyAppName}" \
                   "DisplayVersion" "${MyAppVersion}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${MyAppName}" \
                   "Publisher" "${MyAppPublisher}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${MyAppName}" \
                   "URLInfoAbout" "${MyAppURL}"
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${MyAppName}" \
                   "EstimatedSize" "$0"

  WriteUninstaller "$INSTDIR\uninst.exe"
SectionEnd

Section /o "Desktop Shortcut" SEC_DESKTOP
  CreateShortcut "$DESKTOP\${MyAppName}.lnk" "$INSTDIR\${MyAppExeName}"
  CreateShortcut "$SMPROGRAMS\${MyAppName}\${MyAppName}.lnk" "$INSTDIR\${MyAppExeName}"
SectionEnd

Section -Post
  WriteUninstaller "$INSTDIR\uninst.exe"
SectionEnd

; ========== Uninstall ==========
Section "Uninstall"
  ; Clean runtime files (preserve user config)
  RMDir /r "$INSTDIR\logs"
  RMDir /r "$INSTDIR\.recovery"
  Delete "$INSTDIR\stdout.log"
  Delete "$INSTDIR\stderr.log"
  Delete "$INSTDIR\crash.log"

  ; Delete installed files
  RMDir /r "$INSTDIR\lib"
  RMDir /r "$INSTDIR\resources"
  RMDir /r "$INSTDIR\simulator"
  RMDir /r "$INSTDIR\epass_flasher"
  RMDir /r "$INSTDIR\class_icons"
  Delete "$INSTDIR\${MyAppExeName}"
  Delete "$INSTDIR\material_core_worker.exe"
  Delete "$INSTDIR\material_core_service.exe"
  Delete "$INSTDIR\uninst.exe"
  Delete "$INSTDIR\install_manifest.txt"

  ; Delete shortcuts
  Delete "$DESKTOP\${MyAppName}.lnk"
  RMDir /r "$SMPROGRAMS\${MyAppName}"

  ; Delete registry
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${MyAppName}"
  DeleteRegKey HKCU "Software\${MyAppName}"

  ; Delete empty directories
  RMDir "$INSTDIR"
SectionEnd

; ========== Functions ==========
Function .onInit
  ; Check if already running
  System::Call 'kernel32::CreateMutex(i 0, i 0, t "${AppMutex}") i .r1 ?e'
  Pop $2
  StrCmp $2 0 done_check
    MessageBox MB_ICONEXCLAMATION|MB_OKCANCEL \
      "${MyAppName} is currently running. Please close it before installing.$\r$\n$\r$\nClick OK to force close and continue." \
      /SD IDOK
    Pop $0
    StrCmp $0 IDCANCEL abort_install
    ; Force close
    FindWindow $0 "" "${MyAppName}"
    StrCmp $0 0 done_check
      SendMessage $0 0x0010 0 0 /TIMEOUT=3000
done_check:
  Goto +2
abort_install:
  Abort
FunctionEnd

;Function un.onInit
;  MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 \
;    "Are you sure you want to completely remove $(^Name) and all its components?"
;  Pop $0
;  StrCmp $0 IDYES +2
;  Abort
;FunctionEnd

Function CleanOldFiles
  ; Clean old files on upgrade (whitelist reverse cleanup)
  ; Whitelist: config/ logs/ uninst.exe
  ; Delete everything else

  ; Clean lib/
  IfFileExists "$INSTDIR\lib\*.*" 0 +3
    RMDir /r "$INSTDIR\lib"

  ; Clean resources/
  IfFileExists "$INSTDIR\resources\*.*" 0 +3
    RMDir /r "$INSTDIR\resources"

  ; Clean simulator/
  IfFileExists "$INSTDIR\simulator\*.*" 0 +3
    RMDir /r "$INSTDIR\simulator"

  ; Clean epass_flasher/
  IfFileExists "$INSTDIR\epass_flasher\*.*" 0 +3
    RMDir /r "$INSTDIR\epass_flasher"

  ; Clean class_icons/
  IfFileExists "$INSTDIR\class_icons\*.*" 0 +3
    RMDir /r "$INSTDIR\class_icons"

  ; Clean root directory files (keep uninst.exe, config, logs, .recovery)
  FindFirst $0 $1 "$INSTDIR\*.*"
  loop_files:
    StrCmp $1 "" done_files
    StrCmp $1 "." next_file
    StrCmp $1 ".." next_file
    StrCmp $1 "uninst.exe" next_file
    StrCmp $1 "config" next_file
    StrCmp $1 "logs" next_file
    StrCmp $1 ".recovery" next_file

    ; Check if directory
    IfFileExists "$INSTDIR\$1\*.*" is_dir is_file

  is_file:
    Delete "$INSTDIR\$1"
    Goto next_file

  is_dir:
    RMDir /r "$INSTDIR\$1"
    Goto next_file

  next_file:
    FindNext $0 $1
    Goto loop_files

  done_files:
    FindClose $0
FunctionEnd
