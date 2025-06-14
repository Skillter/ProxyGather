@echo off
setlocal

set /p "oldext=Enter current extension (e.g., txt): "
set /p "newext=Enter new extension (e.g., md): "

if not "%oldext:~0,1%"=="." set "oldext=.%oldext%"
if not "%newext:~0,1%"=="." set "newext=.%newext%"

if not exist "codebase-txt" mkdir "codebase-txt"

echo.
echo Copying *%oldext% files to codebase-txt...
echo.

for /r %%F in (*%oldext%) do (
    copy "%%~fF" "codebase-txt\"
)

echo.
echo Renaming files in codebase-txt...
echo.

pushd codebase-txt
for %%G in (*%oldext%) do (
    ren "%%G" "%%~nG%newext%"
)
popd

echo.
echo Done.
pause
endlocal