# Testa tudo: sobe os dois servidores, roda o teste normal e o de saturacao, gera os relatorios e desliga.
# Uso (PowerShell, dentro de C:\UTFPR\DIS):   .\testar.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Esperar($porta) {
    Write-Host "esperando servidor na porta $porta..."
    while (-not (Test-NetConnection 127.0.0.1 -Port $porta -InformationLevel Quiet -WarningAction SilentlyContinue)) { Start-Sleep 1 }
}

Write-Host "== atividade 2 (operacoes basicas)"
python interpretada\atividade2.py

Write-Host "== compilando o C#"
dotnet build compilada -c Release -v q -nologo | Out-Null

Write-Host "== subindo os servidores"
$py = Start-Process python -ArgumentList "server.py" -WorkingDirectory interpretada -PassThru -WindowStyle Minimized
$cs = Start-Process compilada\bin\Release\net10.0\compilada.exe -WorkingDirectory compilada -PassThru -WindowStyle Minimized
try {
    Esperar 8001; Esperar 8002

    Write-Host "== teste normal (3 clientes x 15 sinais)"
    python client.py py
    python client.py cs
    python comparar.py

    Write-Host "== teste de saturacao (20 clientes x 5 sinais)"
    python client.py py sat
    python client.py cs sat
    python comparar.py sat
}
finally {
    Write-Host "== desligando os servidores"
    Stop-Process -Id $py.Id, $cs.Id -Force -ErrorAction SilentlyContinue
}
Write-Host "pronto! abra relatorio_comparativo.html e relatorio_saturacao.html"
