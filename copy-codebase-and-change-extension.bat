@echo off
setlocal enabledelayedexpansion

:: =============================================================================
:: Title:       Recursive File Copier and Renamer
:: Description: Prompts the user to copy and rename files of provided type
::              Handles duplicates by numbering them, but clears the old folder
:: =============================================================================

:: --- Configuration ---
set "DEST_FOLDER_NAME=codebase-txt"
set "DEST_DIR=%~dp0%DEST_FOLDER_NAME%"
set /a "totalFileCount=0"

:: --- Initial Setup ---
title Fast File Copier
cls
echo =================================================
echo  Initializing...
echo =================================================
echo.

:: First clean up the destination directory ONCE at the start
if exist "%DEST_DIR%\" (
    echo Found old "%DEST_FOLDER_NAME%" directory. Removing it...
    rd /s /q "%DEST_DIR%"
)

:: always create it fresh
echo Creating destination directory...
mkdir "%DEST_DIR%"
if errorlevel 1 (
    echo [ERROR] Could not create destination directory. Halting.
    goto :FINISH
)
echo Setup complete.


:MAIN_LOOP
:: Main loop for user prompts
echo.
echo =================================================
echo  Fast Recursive File Copier
echo =================================================
echo.
echo Total files copied so far: !totalFileCount!
echo Destination folder: %DEST_FOLDER_NAME%
echo.
echo To finish, just press Enter without typing anything.
echo.

:: get the source file extension from the user
set "SOURCE_EXT="
set /p "SOURCE_EXT=Enter SOURCE extension (e.g., log): "

:: exit condition for the loop
if not defined SOURCE_EXT goto :FINISH

:: get the destination file extension from the user
set "DEST_EXT="
set /p "DEST_EXT=Enter DESTINATION extension (e.g., txt): "

:: a little input validation
if not defined DEST_EXT (
    echo.
    echo [WARNING] No destination extension provided. Skipping...
    goto :MAIN_LOOP
)

:: Sanitize the extensions (add a dot if missing)
if not "%SOURCE_EXT:~0,1%"=="." set "SOURCE_EXT=.%SOURCE_EXT%"
if not "%DEST_EXT:~0,1%"=="." set "DEST_EXT=.%DEST_EXT%"

echo.
echo --- Processing ---
echo Searching for *!SOURCE_EXT! files to copy as *!DEST_EXT!...
echo.

set /a "sessionFileCount=0"

:: file processing loop
for /r . %%I in ("*%SOURCE_EXT%") do (
    set "SOURCE_FILE_PATH=%%~fI"
    set "BASE_NAME=%%~nI"
    set "DEST_FILE_PATH=%DEST_DIR%\!BASE_NAME!!DEST_EXT!"

    echo Copying "!BASE_NAME!!SOURCE_EXT!"...

    :: check for duplicates and handle them by numbering
    if exist "!DEST_FILE_PATH!" (
        set "copied=false"
        :: try to find a free number, up to 999
        for /L %%N in (1,1,999) do (
            if not !copied! == true (
                set "NEW_DEST_PATH=%DEST_DIR%\!BASE_NAME!(%%N)!DEST_EXT!"
                if not exist "!NEW_DEST_PATH!" (
                    echo   -> Duplicate found. Renaming to "!BASE_NAME!(%%N)!DEST_EXT!"
                    copy "!SOURCE_FILE_PATH!" "!NEW_DEST_PATH!" > nul
                    set "copied=true"
                )
            )
        )
    ) else (
        :: no duplicate, just a simple copy
        copy "!SOURCE_FILE_PATH!" "!DEST_FILE_PATH!" > nul
    )
    
    set /a "sessionFileCount+=1"
    set /a "totalFileCount+=1"
)

echo.
echo Copied !sessionFileCount! file(s) in this session.
goto :MAIN_LOOP


:FINISH
:: final exit sequence
cls
echo.
echo Checking for "Duplicate" file to clean up...
if exist "Duplicate" (
    del /F /Q "Duplicate"
    echo "Duplicate" file was found and has been removed.
) else (
    echo No "Duplicate" file found.
)
echo.
echo ---
echo Script finished. Total files copied: !totalFileCount!.
echo Window will close in 3 seconds...
timeout /t 3 /nobreak > nul
exit /b