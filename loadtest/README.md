# Locust saturation test

Start the API and Locust dashboard from the repository root:

```bash
docker compose up --build
```

Open `http://localhost:8089` and click **Start**. The test posts the complete
contents of `data/data2k.json` and `data/params.json` on every request.

## Load profile

The workload is a closed-concurrency test. It increases the number of virtual
users, each of which waits for its current request to finish before submitting
the next one:

| Plateau | Concurrent users | Duration |
| --- | ---: | ---: |
| 1 | 1 | 60 seconds |
| 2 | 2 | 60 seconds |
| 3 | 4 | 60 seconds |
| 4 | 8 | 60 seconds |
| 5 | 16 | 60 seconds |
| 6 | 32 | 60 seconds |
| 7 | 64 | 60 seconds |

This is not a fixed offered-rate test. For example, one user does not send one
request per second: it sends a new request immediately after the preceding
response arrives. Increasing users raises the maximum number of in-flight
requests and shows where the API stops turning additional concurrency into
additional throughput.

## Completed TPS

Completed TPS is the total number of requests that finish across all virtual
users, divided by the measurement interval in seconds:

```text
completed TPS = completed requests from every user / interval seconds
```

Do not divide by the number of users. For example, if eight users complete 240
requests in a 60-second plateau, throughput is `240 / 60 = 4 TPS`. It is also
the sum of the individual users' completion rates.

The **Requests/s** value in Locust includes completed responses, including
failed ones. Fully successful TPS is therefore:

```text
successful TPS = completed TPS * (1 - failure rate)
```

When failures are zero, Requests/s is the successful completed TPS. In Locust
2.40.1, the **Current RPS** value is a rolling average over approximately the
previous ten complete one-second buckets; the newest approximately two seconds
are excluded to avoid incomplete buckets.

## Latency and saturation

Use **Charts** to see Requests/s as the user count rises. Use the aggregate
row in **Statistics** for failure count and **95%** latency. p95 is calculated
from every individual end-to-end request latency; it is not an average of each
user's p95.

The service is saturated when adding users no longer increases completed TPS
materially, while p95 rises sharply and/or failures begin. This deployment has
a one-CPU limit and one prediction executor worker, so queueing after that
worker becomes busy is expected.
