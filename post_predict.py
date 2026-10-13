"""Send the bundled sample data to the local prediction service."""

from __future__ import annotations

import json
from argparse import ArgumentParser
from pathlib import Path
from time import perf_counter
from urllib.request import Request, urlopen

ROOT = Path(__file__).parent
URL = 'http://localhost:8088/predict'


def load_json(filename: str) -> dict:
    with (ROOT / 'data' / filename).open(encoding='utf-8') as source:
        return json.load(source)


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--out', action='store_true', help='print the prediction JSON response')
    arguments = parser.parse_args()
    payload = json.dumps(
        {
            'data': load_json('data2k.json'),
            'params': load_json('params.json'),
        }
    ).encode('utf-8')
    request = Request(URL, data=payload, headers={'Content-Type': 'application/json'}, method='POST')

    request_started = perf_counter()
    with urlopen(request) as response:
        result = json.load(response)
    elapsed_ms = (perf_counter() - request_started) * 1000

    print(f'POST result received in {elapsed_ms:.2f} ms')
    if arguments.out:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
