$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectRoot

python start.py scrape --config config.yaml
python start.py publish-google-reviews --config config.yaml
