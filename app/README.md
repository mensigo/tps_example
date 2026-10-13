# Payment-chain predictor

The service accepts the contents of the two supplied JSON files in one request,
computes payment-chain timing and factory-transition summaries, and returns one JSON result.
The CPU-bound Pandas/NumPy work runs from the async endpoint in a one-thread executor.

## Start

```bash
docker compose up --build
```

## Query

```bash
jq -n \
  --slurpfile data data/data2k.json \
  --slurpfile params data/params.json \
  '{data: $data[0], params: $params[0]}' |
  curl -sS -X POST http://localhost:8088/predict \
    -H 'Content-Type: application/json; charset=utf-8' \
    --data-binary @- | jq
```

The generated API documentation is at `http://localhost:8088/docs`.

## Load test with Locust

From the repository root, start the API and the Locust web UI:

```bash
docker compose up --build
```

Open `http://localhost:8089` and click **Start**. The built-in profile grows
the concurrent request count in one-minute steps: 1, 2, 4, 8, 16, 32, then 64.
It stops automatically after the final plateau.

The workload serializes `data/data2k.json` and `data/params.json` once at
startup; every request posts that exact combined JSON payload to `/predict`.
Use the **Charts** page to see the completed **Requests/s** (TPS) curve as the
user count rises, and the **Statistics** page's aggregate row for failure
count and the **95%** end-to-end latency. With this deployment's one CPU and
single prediction-executor thread, saturation is where completed TPS flattens
while p95 rises sharply. Each virtual user waits for a response before sending
its next request, so Requests/s represents fully processed requests rather
than merely submitted work.
