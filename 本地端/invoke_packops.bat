@echo off
setlocal
REM Read JSON from file into variable
set "PARAMS="
for /f "usebackq delims=" %%A in ("E:\Trae\021\invoke_packops_get_search.json") do set "PARAMS=%%A"

echo Params: %PARAMS%

REM Pass JSON as a single quoted argument to CLI
tcb fn invoke packOps -e cloud1-7grjr7usb5d86f59 --params "%PARAMS%"
endlocal