# Tools image for hubbo-profiles: the validator, the index and release builds, migrations and the
# Harmony import. Built and run by the bin/ scripts (tagged by this file's hash); nothing is
# installed on the host. git is for validate --since and release.
FROM python:3.12.8-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/* \
 && git config --system --add safe.directory '*'
RUN pip install --no-cache-dir jsonschema==4.23.0
WORKDIR /repo
