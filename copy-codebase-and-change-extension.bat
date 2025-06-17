@echo off
setlocal enabledelayedexpansion

:: Prompt user for original and new extensions
set /p orig_ext=Enter the original file extension (e.g., log): 
set /p new_ext=Enter the new file extension (e.g., txt): 

:: Create output directory
set "outdir=database-txt"
if not exist "%outdir%" mkdir "%outdir%"

:: Normalize extensions (remove leading dots if present)
set "orig_ext=%orig_ext:.=%"
set "new_ext=%new_ext:.=%"

:: Search recursively and copy files with new extension
for /R %%f in (*.%orig_ext%) do (
    set "src=%%~f"
    set "base=%%~nf"
    copy "%%~f" "%outdir%\!base!.%new_ext%" >nul
    echo Copied: "%%~f" -> "%outdir%\!base!.%new_ext%"
)

echo Done.
pause
