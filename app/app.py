"""Async payment-chain aggregation service."""

from __future__ import annotations

import asyncio
import re
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# A single worker intentionally serializes CPU-bound Pandas work.  Raise this only
# after profiling under the target deployment's expected load.
EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix='prediction')
RECIPIENT_PATTERN = re.compile(r'\(([^()]+)\)')
WORKLOAD_WINDOWS = 4_096


class PredictRequest(BaseModel):
    data: dict[str, Any] = Field(description='Contents of data2k.json')
    params: dict[str, Any] = Field(description='Contents of params.json')


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    EXECUTOR.shutdown(wait=True)


app = FastAPI(title='Payment-chain predictor', version='1.0.0', lifespan=lifespan)


def _recipient_factory(info: object) -> str:
    """Extract the target factory identifier from an event's extra information."""
    match = RECIPIENT_PATTERN.search(str(info or ''))
    return match.group(1) if match else 'unknown'


def calculate_prediction(data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Perform CPU-bound NumPy/Pandas aggregation for a batch of payment chains."""
    started = time.perf_counter()
    documents = data.get('documents')
    if not isinstance(documents, list) or not documents:
        raise ValueError('data.documents must be a non-empty array')

    document_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    for document in documents:
        if not isinstance(document, dict):
            raise TypeError('every document must be an object')
        factory = str(document.get('sendfactory_id') or 'unknown')
        document_id = str(document.get('id') or 'unknown')
        events = document.get('process', [])
        if not isinstance(events, list):
            raise TypeError('document.process must be an array')
        document_rows.append({'document_id': document_id, 'source_factory': factory, 'event_count': len(events)})
        for event in events:
            if isinstance(event, dict):
                event_rows.append(
                    {
                        'document_id': document_id,
                        'source_factory': factory,
                        'target_factory': _recipient_factory(event.get('additional_info')),
                        'status': str(event.get('status') or 'UNKNOWN'),
                        'processed_at': event.get('date_proc'),
                    }
                )

    documents_frame = pd.DataFrame(document_rows)
    events_frame = pd.DataFrame(event_rows)
    if events_frame.empty:
        raise ValueError('at least one processing event is required')

    events_frame['processed_at'] = pd.to_datetime(events_frame['processed_at'], errors='coerce')
    valid_times = events_frame.dropna(subset=['processed_at'])
    durations = valid_times.groupby('document_id')['processed_at'].agg(['min', 'max'])
    durations['duration_ms'] = (durations['max'] - durations['min']).dt.total_seconds() * 1000

    source_summary = (
        documents_frame.groupby('source_factory', as_index=False)
        .agg(payment_chains=('document_id', 'nunique'), processing_events=('event_count', 'sum'))
        .sort_values(['payment_chains', 'source_factory'], ascending=[False, True])
    )
    transitions = (
        events_frame.groupby(['source_factory', 'target_factory'], as_index=False)
        .size()
        .rename(columns={'size': 'transitions'})
        .sort_values(['transitions', 'source_factory', 'target_factory'], ascending=[False, True, True])
    )
    status_counts = events_frame['status'].value_counts().sort_index()

    # Simulate per-factory capacity analysis over processing windows.  The merges
    # enrich every payment transition with aggregate factory and route metrics
    # before calculating weighted work units for a large batch of windows.
    factory_profile = events_frame.groupby('source_factory', as_index=False).agg(
        factory_successes=('status', lambda status: int((status == 'SUCCESS').sum()))
    )
    route_profile = transitions.rename(columns={'transitions': 'route_transitions'})
    enriched_events = events_frame.merge(factory_profile, on='source_factory', how='left', validate='many_to_one')
    enriched_events = enriched_events.merge(
        route_profile,
        on=['source_factory', 'target_factory'],
        how='left',
        validate='many_to_one',
    )
    processing_windows = pd.DataFrame(
        {
            'window': np.arange(WORKLOAD_WINDOWS, dtype=np.int32),
            'window_weight': np.linspace(1.0, 1.25, WORKLOAD_WINDOWS, dtype=np.float64),
        }
    )
    workload = enriched_events.merge(processing_windows, how='cross', validate='many_to_many')
    workload = workload.merge(
        source_summary[['source_factory', 'payment_chains']],
        on='source_factory',
        how='left',
        validate='many_to_one',
    )
    workload['weighted_work_units'] = (
        workload['route_transitions']
        * workload['factory_successes']
        * workload['payment_chains']
        * workload['window_weight']
    )
    factory_workload = (
        workload.groupby('source_factory', as_index=False)['weighted_work_units']
        .sum()
        .rename(columns={'weighted_work_units': 'estimated_work_units'})
    )
    source_summary = source_summary.merge(factory_workload, on='source_factory', how='left', validate='one_to_one')
    source_summary['estimated_work_units'] = source_summary['estimated_work_units'].round(2)

    # NumPy is used for percentile computation over per-chain elapsed times.
    duration_values = durations['duration_ms'].to_numpy(dtype=float)
    processing_ms = round((time.perf_counter() - started) * 1000, 2)

    return {
        'request': {key: params.get(key) for key in ('msgId', 'workId', 'msgTm')},
        'summary': {
            'payment_chains': int(documents_frame['document_id'].nunique()),
            'processing_events': len(events_frame),
            'successful_events': int(status_counts.get('SUCCESS', 0)),
            'median_chain_duration_ms': round(float(np.median(duration_values)), 2),
            'p95_chain_duration_ms': round(float(np.percentile(duration_values, 95)), 2),
            'processing_time_ms': processing_ms,
        },
        'factories': source_summary.to_dict(orient='records'),
        'transitions': transitions.to_dict(orient='records'),
        'statuses': {str(status): int(count) for status, count in status_counts.items()},
    }


@app.post('/predict')
async def predict(request: PredictRequest) -> dict[str, Any]:
    """Run the synchronous analytics function in the one-thread executor pool."""
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(EXECUTOR, calculate_prediction, request.data, request.params)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
