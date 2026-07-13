# Kill anything still bound to port 8000 (stale uvicorn reload children on Windows)
& "$PSScriptRoot\stop.ps1"

Set-Location $PSScriptRoot
python run.py
