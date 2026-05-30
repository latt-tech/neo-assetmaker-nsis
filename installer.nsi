; ArknightsPassMaker NSIS Installer — 内嵌 7z 压缩包
; 安装流程：解压 7za.exe → 解压 7z 归档到目标目录
; 压缩方式：NSIS 外壳使用 LZMA/SOLID，内部数据为 7z (LZMA2)

!include "MUI2.nsh"
!include "FileFunc.nsh"

!ifndef MyAppVersion
  !define MyAppVersion "2.2"
!endif

!define MyAppName "ArknightsPassMaker"
!define MyAppNameCN "明日方舟通行证素材工具箱"
!define MyAppPublisher "Rafael-ban"
!define MyAppURL "https://github.com/rhodesepass/neo-assetmaker"
!define MyAppExeName "ArknightsPassMaker.exe"
!define MyAppIcon "resources\icons\favicon.ico"
!define AppMutex "ArknightsPassMakerMutex"
!define ArchiveName "${MyAppName}_v${MyAppVersion}.7z"

; ========== 基本设置 ==========
Name "${MyAppNameCN}"
OutFile "dist\${MyAppName}_v${MyAppVersion}_Setup_NSIS.exe"
InstallDir "$LOCALAPPDATA\${MyAppName}"
InstallDirRegKey HKCU "Software\${MyAppNameCN}" ""
RequestExecutionLevel user
BrandingText "${MyAppNameCN} v${MyAppVersion}"
SetCompressor /SOLID lzma
Unicode True

; ========== 界面设置 ==========
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
!define MUI_FINISHPAGE_LINK "GitHub 项目主页"
!define MUI_FINISHPAGE_LINK_LOCATION "${MyAppURL}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "resources\installer\LICENSE.txt"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "SimpChinese"

; ========== 安装类型 ==========
InstType "完整安装"

; ========== 文件安装 ==========
Section "主程序" SEC_MAIN
  SectionIn RO

  ; 升级时先清理旧文件
  Call CleanOldFiles

  ; 在临时目录解压 7z.exe + 7z.dll 和 7z 归档
  InitPluginsDir
  SetOutPath "$PLUGINSDIR"

  ; 嵌入 7z.exe + 7z.dll（独立解压工具）
  File /oname=7z.exe "tools\nsis\7z.exe"
  File /oname=7z.dll "tools\nsis\7z.dll"

  ; 嵌入 7z 压缩包
  File /oname=data.7z "dist\${ArchiveName}"

  ; 解压 7z 到安装目录
  SetOutPath "$INSTDIR"
  ExecWait '"$PLUGINSDIR\7z.exe" x "$PLUGINSDIR\data.7z" -y -o"$INSTDIR"' $0

  ; 清理临时文件
  Delete "$PLUGINSDIR\7z.exe"
  Delete "$PLUGINSDIR\7z.dll"
  Delete "$PLUGINSDIR\data.7z"

  IntCmp $0 0 0 extract_error extract_error
  Goto extract_ok

extract_error:
  MessageBox MB_ICONSTOP "解压失败（错误码: $0），请重试。"
  Abort

extract_ok:
  ; 写入卸载信息
  WriteRegStr HKCU "Software\${MyAppNameCN}" "" $INSTDIR
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${MyAppName}" \
                   "DisplayName" "${MyAppNameCN}"
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

Section /o "桌面快捷方式" SEC_DESKTOP
  CreateShortcut "$DESKTOP\${MyAppNameCN}.lnk" "$INSTDIR\${MyAppExeName}"
  CreateShortcut "$SMPROGRAMS\${MyAppNameCN}\${MyAppNameCN}.lnk" "$INSTDIR\${MyAppExeName}"
SectionEnd

Section -Post
  WriteUninstaller "$INSTDIR\uninst.exe"
SectionEnd

; ========== 卸载 ==========
Section "Uninstall"
  ; 清理运行时文件（保留用户配置）
  RMDir /r "$INSTDIR\logs"
  RMDir /r "$INSTDIR\.recovery"
  Delete "$INSTDIR\stdout.log"
  Delete "$INSTDIR\stderr.log"
  Delete "$INSTDIR\crash.log"

  ; 删除安装的文件
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

  ; 删除快捷方式
  Delete "$DESKTOP\${MyAppNameCN}.lnk"
  RMDir /r "$SMPROGRAMS\${MyAppNameCN}"

  ; 删除注册表
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${MyAppName}"
  DeleteRegKey HKCU "Software\${MyAppNameCN}"

  ; 删除空目录
  RMDir "$INSTDIR"
SectionEnd

; ========== 函数 ==========
Function .onInit
  ; 检查是否正在运行
  System::Call 'kernel32::CreateMutex(i 0, i 0, t "${AppMutex}") i .r1 ?e'
  Pop $2
  StrCmp $2 0 +3
    MessageBox MB_ICONEXCLAMATION|MB_OKCANCEL \
      "${MyAppNameCN} 正在运行，请先关闭程序后再安装。$\r$\n$\r$\n点击"确定"强制关闭并继续安装。" \
      /SD IDOK IDOK +2
    Abort
    ; 强制关闭
    FindWindow $0 "" "${MyAppNameCN}"
    StrCmp $0 0 +2
      SendMessage $0 0x0010 0 0 /TIMEOUT=3000
FunctionEnd

Function un.onInit
  MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 \
    "您确实要完全删除 $(^Name) 及其所有组件？$\r$\n$\r$\n（用户配置目录 config/ 将被保留）" \
    IDYES +2
  Abort
FunctionEnd

Function CleanOldFiles
  ; 升级时清理旧文件（白名单反向清理）
  ; 白名单：config/ logs/ uninst.exe
  ; 其余全部删除

  ; 清理 lib/
  IfFileExists "$INSTDIR\lib\*.*" 0 +3
    RMDir /r "$INSTDIR\lib"

  ; 清理 resources/
  IfFileExists "$INSTDIR\resources\*.*" 0 +3
    RMDir /r "$INSTDIR\resources"

  ; 清理 simulator/
  IfFileExists "$INSTDIR\simulator\*.*" 0 +3
    RMDir /r "$INSTDIR\simulator"

  ; 清理 epass_flasher/
  IfFileExists "$INSTDIR\epass_flasher\*.*" 0 +3
    RMDir /r "$INSTDIR\epass_flasher"

  ; 清理 class_icons/
  IfFileExists "$INSTDIR\class_icons\*.*" 0 +3
    RMDir /r "$INSTDIR\class_icons"

  ; 清理根目录下的 exe/dll（保留 uninst.exe）
  FindFirst $0 $1 "$INSTDIR\*.*"
  loop_files:
    StrCmp $1 "" done_files
    StrCmp $1 "." next_file
    StrCmp $1 ".." next_file
    StrCmp $1 "uninst.exe" next_file
    StrCmp $1 "config" next_file
    StrCmp $1 "logs" next_file
    StrCmp $1 ".recovery" next_file
    StrCmp $1 "ArknightsPassMaker" next_file

    ; 检查是否是目录
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
