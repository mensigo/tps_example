FROM python:3.12-slim

WORKDIR /work

COPY loadtest/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY data /work/data
COPY loadtest/locustfile.py /work/loadtest/locustfile.py

EXPOSE 8089

ENTRYPOINT ["locust"]
