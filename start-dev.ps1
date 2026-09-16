$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$logDirectory = Join-Path $projectRoot '.logs'
$pythonExecutable = Join-Path $projectRoot '.venv\Scripts\python.exe'
$angularScript = Join-Path $projectRoot 'frontend\node_modules\@angular\cli\bin\ng.js'
if (-not (Test-Path -LiteralPath $pythonExecutable) -or -not (Test-Path -LiteralPath $angularScript)) {
    throw 'Installera beroenden enligt README.md först.'
}
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
foreach ($port in @(8000, 4200)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port används redan. Använd den befintliga servern eller frigör porten först."
    }
}
$backendProcess = Start-Process -FilePath $pythonExecutable -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDirectory 'backend.out.log') -RedirectStandardError (Join-Path $logDirectory 'backend.err.log')
$nodeExecutable = (Get-Command node.exe).Source
$frontendProcess = Start-Process -FilePath $nodeExecutable -ArgumentList @(('"' + $angularScript + '"'), 'serve', '--host', '127.0.0.1', '--proxy-config', 'proxy.conf.json') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDirectory 'frontend.out.log') -RedirectStandardError (Join-Path $logDirectory 'frontend.err.log')
Write-Output "Frontend: http://127.0.0.1:4200 (PID $($frontendProcess.Id))"
Write-Output "API: http://127.0.0.1:8000/docs (PID $($backendProcess.Id))"
Write-Output "Stoppa dessa servrar med: Stop-Process -Id $($backendProcess.Id),$($frontendProcess.Id)"
