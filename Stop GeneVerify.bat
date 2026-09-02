@echo off
setlocal EnableExtensions
title GeneVerify Stop

rem ===========================================================================
rem  GeneVerify AI  -  stop the local servers
rem
rem  Stops ONLY the processes that serve this project on the two GeneVerify
rem  ports (backend 8000, frontend 5173). Before killing anything it checks the
rem  command line of the process that owns the port (and of the console window
rem  that started it) and requires a reference to this project folder plus one
rem  of the known launch signatures. A port held by an unrelated program is
rem  reported and left alone.
rem
rem  It never kills python.exe / node.exe generally, never deletes a file,
rem  never touches the database or backend\storage, and runs no git command.
rem ===========================================================================

pushd "%~dp0"
set "GV_ROOT=%CD%"

echo(
echo   ==========================================================
echo    GeneVerify AI  -  stopping local services
echo   ==========================================================
echo     project : %GV_ROOT%
echo(

set "PS="
set "PS=%PS% $root=$env:GV_ROOT; $esc=[regex]::Escape($root); "
set "PS=%PS% $sig='run\.py|vite|npm-cli\.js|npm run dev|npm\.cmd|node_modules|esbuild'; "
set "PS=%PS% $allow='cmd.exe','node.exe','python.exe','pythonw.exe','esbuild.exe'; "
set "PS=%PS% function Kids($id){ @(Get-CimInstance -ClassName Win32_Process -Filter ('ParentProcessId=' + $id) -ErrorAction SilentlyContinue | ForEach-Object { $_.ProcessId; Kids $_.ProcessId }) } "
set "PS=%PS% function Info($id){ $x=Get-CimInstance -ClassName Win32_Process -Filter ('ProcessId=' + $id) -ErrorAction SilentlyContinue; if ($x) { [string]$x.Name } else { 'gone' } } "
set "PS=%PS% foreach ($t in @(@(8000,'backend'),@(5173,'frontend'))) { "
set "PS=%PS%   $port=$t[0]; $label=$t[1]; "
set "PS=%PS%   $c=@(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue); "
set "PS=%PS%   if ($c.Count -eq 0) { Write-Host ('  ' + $label + ': not running on port ' + $port + '.'); continue } "
set "PS=%PS%   $lp=$c[0].OwningProcess; $p=Get-CimInstance -ClassName Win32_Process -Filter ('ProcessId=' + $lp) -ErrorAction SilentlyContinue; "
set "PS=%PS%   if (-not $p) { Write-Host ('  ' + $label + ': cannot inspect PID ' + $lp + ' - left alone.'); continue } "
set "PS=%PS%   $lc=[string]$p.CommandLine; $chain=@($lp); $q=$p; "
set "PS=%PS%   for ($h=0; $h -lt 6; $h++) { "
set "PS=%PS%     if (-not $q -or $q.ParentProcessId -le 0 -or $q.ParentProcessId -eq 4) { break } "
set "PS=%PS%     $par=Get-CimInstance -ClassName Win32_Process -Filter ('ProcessId=' + $q.ParentProcessId) -ErrorAction SilentlyContinue; "
set "PS=%PS%     if (-not $par) { break } "
set "PS=%PS%     if ($allow -notcontains $par.Name) { break } "
set "PS=%PS%     $pcl=[string]$par.CommandLine; "
set "PS=%PS%     if (($pcl -notmatch $sig) -and ($pcl -notmatch $esc)) { break } "
set "PS=%PS%     $chain += $par.ProcessId; $q=$par } "
set "PS=%PS%   $chain += @(Kids $lp); $chain=@($chain | Where-Object { $_ -gt 0 } | Select-Object -Unique); "
set "PS=%PS%   $all=$lc; foreach ($id in $chain) { $all += ' ' + [string](Info $id) + ' ' + (Get-CimInstance -ClassName Win32_Process -Filter ('ProcessId=' + $id) -ErrorAction SilentlyContinue).CommandLine } "
set "PS=%PS%   $inProject=($all -match $esc); $mine=($all -match $sig); "
set "PS=%PS%   if (-not ($inProject -and $mine)) { Write-Host ('  ' + $label + ': port ' + $port + ' is held by PID ' + $lp + ' (' + $p.Name + ') which is not this project''s GeneVerify server - left running, nothing was killed.'); continue } "
set "PS=%PS%   Write-Host ('  ' + $label + ': stopping ' + $chain.Count + ' process(es) started for GeneVerify on port ' + $port + ' -> ' + (($chain | ForEach-Object { (Info $_) + ':' + $_ }) -join ', ') + ''); "
set "PS=%PS%   foreach ($id in $chain) { try { Stop-Process -Id $id -Force -ErrorAction Stop } catch { } } "
set "PS=%PS% } "
set "PS=%PS% Start-Sleep -Milliseconds 1200; "
set "PS=%PS% foreach ($port in @(8000,5173)) { $a=@(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue); "
set "PS=%PS%   if ($a.Count -eq 0) { Write-Host ('  port ' + $port + ': free.') } "
set "PS=%PS%   else { Write-Host ('  port ' + $port + ': still listening (PID ' + $a[0].OwningProcess + ') - it is not a GeneVerify process of this project, so it was left alone.') } } "

powershell -NoProfile -ExecutionPolicy Bypass -Command "%PS%"

echo(
echo   Done. No file was deleted, no data was changed, nothing was seeded,
echo   and no git command was run. The database in backend\geneverify.db and
echo   the uploaded documents in backend\storage are exactly as they were.
echo(
echo   Restart the application any time with:  Start GeneVerify.bat
echo(
pause
popd
endlocal
exit /b 0
