@echo off
setlocal enabledelayedexpansion

set /p "oldext=Enter current extension (e.g., txt): "
set /p "newext=Enter new extension (e.g., md): "

if not "%oldext:~0,1%"=="." set "oldext=.%oldext%"
if not "%newext:~0,1%"=="." set "newext=.%newext%"

set "targetdir=codebase-txt"

if not exist "%targetdir%" mkdir "%targetdir%"

echo.
echo Copying *%oldext% files to %targetdir%...
echo.

for /f "delims=" %%F in ('dir /s /b "*%oldext%" ^| findstr /v /i /c:"\\%targetdir%\\"') do (
    set "sourceFile=%%~fF"
    set "baseName=%%~nF"
    set "extName=%%~xF"
    set "fileName=%%~nxF"
    set "destPath=%targetdir%\!fileName!"

    if not exist "!destPath!" (
        echo Copying "!fileName!"
        copy "!sourceFile!" "!destPath!" > nul
    ) else (
        set "counter=1"
        :find_name
        set "newFileName=!baseName!(!counter!)!extName!"
        set "newDestPath=%targetdir%\!newFileName!"
        if exist "!newDestPath!" (
            set /a counter+=1
            goto :find_name
        ) else (
            echo Copying "!fileName!" as "!newFileName!"
            copy "!sourceFile!" "!newDestPath!" > nul
        )
    )
)

echo.
echo Renaming files in %targetdir%...
echo.

pushd %targetdir%
for %%G in (*%oldext%) do (
    echo Renaming "%%G" to "%%~nG%newext%"
    ren "%%G" "%%~nG%newext%"
)
popd

echo.
echo Done.
pause
endlocal