@echo off
REM Windows -> WSL shim for THC-Hydra. The native backend's HydraIntegration
REM invokes this as `hydra`; it forwards to the real hydra installed in WSL,
REM translating Windows wordlist paths to WSL paths. Authorized lab use only.
setlocal
for /f "usebackq delims=" %%p in (`wsl -d Ubuntu wslpath -u "%~dp0hydra-wrap.sh"`) do set "WRAP=%%p"
wsl -d Ubuntu bash "%WRAP%" %*
exit /b %errorlevel%
