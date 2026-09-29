# Újraindítás utáni folytatás: adatbázis felhúzása, majd a gyűjtés folytatása.
#
# A PostgreSQL-t felhasználói folyamatként indítjuk (a telepített szolgáltatás
# indításához rendszergazda kell), ezért újraindulás után magától nem jön vissza.
# Ez a szkript bejelentkezéskor lefut, és mindent onnan folytat, ahol abbamaradt:
# a bejárás és a begyűjtés is nyilvántartja a haladását.

$ErrorActionPreference = "Continue"
$gyoker = "C:\Users\Lenovo\Documents\herendi"
$pgbin  = "C:\Program Files\PostgreSQL\18\bin"
$pgdata = Join-Path $gyoker "pgdata"
$naplo  = Join-Path $gyoker "folytatas.log"

function Jegyzet([string]$uzenet) {
    $sor = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $uzenet
    Write-Output $sor
    Add-Content -Path $naplo -Value $sor -Encoding utf8
}

Jegyzet "=== Folytatas indul ==="

# 1. PostgreSQL: csak akkor indítjuk, ha nem hallgat a porton
$fut = Test-NetConnection -ComputerName 127.0.0.1 -Port 5433 -InformationLevel Quiet -WarningAction SilentlyContinue
if ($fut) {
    Jegyzet "PostgreSQL mar fut az 5433-as porton."
} else {
    Jegyzet "PostgreSQL inditasa..."
    Start-Process -FilePath (Join-Path $pgbin "pg_ctl.exe") `
        -ArgumentList @("-D", "`"$pgdata`"", "-l", "`"$pgdata\server.log`"", "-o", "`"-p 5433`"", "start") `
        -WindowStyle Hidden
    Start-Sleep -Seconds 10
    $fut = Test-NetConnection -ComputerName 127.0.0.1 -Port 5433 -InformationLevel Quiet -WarningAction SilentlyContinue
    if ($fut) { Jegyzet "PostgreSQL elindult." } else { Jegyzet "FIGYELEM: a PostgreSQL nem indult el, lasd pgdata\server.log" }
}

$py = Join-Path $gyoker ".venv\Scripts\python.exe"
$env:PYTHONUTF8 = "1"

# 2. Vatera-bejarás (SQLite): csak ha nem fut mar
$vateraFut = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*run_gyujtes.py*" }
if ($vateraFut) {
    Jegyzet "A Vatera-lanc mar fut."
} else {
    Jegyzet "Vatera-lanc inditasa."
    Start-Process -FilePath $py -ArgumentList @("`"$gyoker\run_gyujtes.py`"") `
        -WorkingDirectory $gyoker -WindowStyle Hidden
}

# 3. Korpusz-begyujtes (PostgreSQL): csak ha nem fut mar
$korpuszFut = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*run_korpusz.py*" }
if ($korpuszFut) {
    Jegyzet "A korpusz-lanc mar fut."
} else {
    Jegyzet "Korpusz-lanc inditasa."
    Start-Process -FilePath $py -ArgumentList @("`"$gyoker\run_korpusz.py`"") `
        -WorkingDirectory $gyoker -WindowStyle Hidden
}

# 4. Alvasgatlas: a gep ne aludjon el, amig barmelyik lanc fut
$ebrenFut = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*porcelan.ebren*" }
if ($ebrenFut) {
    Jegyzet "Az alvasgatlo or mar fut."
} else {
    Jegyzet "Alvasgatlo or inditasa."
    Start-Process -FilePath $py -ArgumentList @("-m", "porcelan.ebren") `
        -WorkingDirectory $gyoker -WindowStyle Hidden
}

Jegyzet "=== Folytatas beallitva ==="
