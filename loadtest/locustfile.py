"""Locust workload that replays the bundled prediction request unchanged."""

from __future__ import annotations

import json
from pathlib import Path

from locust import HttpUser, LoadTestShape, constant, task


ROOT = Path(__file__).resolve().parents[1]
with (ROOT / 'data' / 'data2k.json').open(encoding='utf-8') as data_source:
    DATA = json.load(data_source)
with (ROOT / 'data' / 'params.json').open(encoding='utf-8') as params_source:
    PARAMS = json.load(params_source)

# Serialize once, outside the measured request path.  Every virtual user sends
# exactly the same request body containing the full data2k fixture.
PAYLOAD = json.dumps({'data': DATA, 'params': PARAMS}, ensure_ascii=False).encode('utf-8')
HEADERS = {'Content-Type': 'application/json; charset=utf-8'}

# Each level is held long enough for Locust's rolling RPS and percentile
# statistics to settle.  Users send a new request only after their previous
# request completes, so Requests/s is completed, end-to-end TPS.
STAGES: tuple[tuple[int, int], ...] = (
    (1, 60),
    (2, 60),
    (4, 60),
    (8, 60),
    (16, 60),
    (32, 60),
    (64, 60),
)


class PredictorUser(HttpUser):
    """Issue back-to-back /predict calls; concurrency is selected in the UI."""

    wait_time = constant(0)

    @task
    def predict(self) -> None:
        with self.client.post('/predict', data=PAYLOAD, headers=HEADERS, catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f'unexpected status: {response.status_code}')
                return

            try:
                body = response.json()
                if 'summary' not in body:
                    raise ValueError('response has no summary')
            except (ValueError, json.JSONDecodeError) as exc:
                response.failure(f'invalid prediction response: {exc}')


class SaturationStepShape(LoadTestShape):
    """Double concurrent requests once per minute, then end the test."""

    def tick(self) -> tuple[int, float] | None:
        elapsed_seconds = self.get_run_time()
        stage_end = 0

        for users, duration_seconds in STAGES:
            stage_end += duration_seconds
            if elapsed_seconds < stage_end:
                # Make the transition immediate; the plateau itself is what is
                # measured, not a gradual arrival ramp.
                return users, float(users)

        return None
