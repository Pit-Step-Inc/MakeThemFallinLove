@echo off
REM ---------------------------------------------------------------
REM  Launch Chrome with the autoplay gate disabled, so the title BGM
REM  starts with no click at all.
REM
REM  Browsers block audible autoplay until the user interacts with the
REM  page. That policy cannot be turned off from page code, only by a
REM  Chrome launch flag. This starts a SEPARATE Chrome profile in TEMP,
REM  because Chrome ignores launch flags when an instance with the same
REM  profile is already running.
REM
REM    tools\play.bat                     ... opens http://127.0.0.1:5173/
REM    tools\play.bat http://host:port/   ... opens the given URL
REM
REM  Start the dev server first:  python tools\serve.py
REM ---------------------------------------------------------------
setlocal

set "URL=http://127.0.0.1:5173/"
if not "%~1"=="" set "URL=%~1"

set "CHROME="
for %%P in (
  "%ProgramFiles%\Google\Chrome\Application\chrome.exe"
  "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
  "%LocalAppData%\Google\Chrome\Application\chrome.exe"
) do if exist %%~P if not defined CHROME set "CHROME=%%~P"

if not defined CHROME (
  echo [play] chrome.exe not found. Edit this file and set CHROME manually.
  exit /b 1
)

echo [play] chrome : %CHROME%
echo [play] url    : %URL%

start "" "%CHROME%" ^
  --autoplay-policy=no-user-gesture-required ^
  --user-data-dir="%TEMP%\mtfil-chrome" ^
  --no-first-run ^
  --no-default-browser-check ^
  "%URL%"
