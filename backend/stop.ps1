# Stop Northline backend processes (stale uvicorn reload children often block port 8000 on Windows)
Write-Host "Stopping Northline backend processes..."

Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  Where-Object { $_ -gt 0 } |
  ForEach-Object {
    Write-Host "  Killing PID $_ (port 8000)"
    Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
  }

Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match 'run\.py|uvicorn.*app\.main' } |
  ForEach-Object {
    Write-Host "  Killing python PID $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }

Start-Sleep -Seconds 2
$still = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($still) {
  Write-Host "WARNING: port 8000 is still in use. Close the backend terminal or end the process in Task Manager."
} else {
  Write-Host "Port 8000 is free."
}
