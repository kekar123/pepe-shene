$env:PYTHONIOENCODING = "utf-8"
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
chcp 65001 > $null
python "c:\Users\Zona7_2\Documents\GitHub\pepe-shene\pepe parser\app.py"
