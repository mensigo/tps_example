# Payment-chain predictor

The service accepts the contents of the two supplied JSON files in one request,
computes payment-chain timing and factory-transition summaries, and returns one JSON result.
The CPU-bound Pandas/NumPy work runs from the async endpoint in a one-thread executor.

## Start

```powershell
Set-Location app
docker compose up --build
```

## Query

```powershell
$body = @{ data = (Get-Content ../data/data2k.json -Raw | ConvertFrom-Json); params = (Get-Content ../data/params.json -Raw | ConvertFrom-Json) } | ConvertTo-Json -Depth 20
$utf8Body = [System.Text.Encoding]::UTF8.GetBytes($body)
Invoke-RestMethod -Uri http://localhost:8088/predict -Method Post -ContentType 'application/json; charset=utf-8' -Body $utf8Body
```

The generated API documentation is at `http://localhost:8088/docs`.
