FROM python:3.9-slim as base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

FROM base as builder

COPY pyproject.toml poetry.lock /app/
# hadolint ignore=DL4006,DL3042,DL3013
RUN pip install poetry && \
	python3 -m venv .venv && \
	.venv/bin/pip install -U pip setuptools wheel && \
	poetry export -n -f requirements.txt | .venv/bin/pip install -r /dev/stdin
COPY src /app/
RUN poetry build && .venv/bin/pip install dist/*.whl

FROM base as final
RUN useradd --home-dir /app --create-home --shell /bin/bash app && \
	chown app: /app -R
USER app
COPY --chown=app:app --from=builder /app/.venv /app/.venv
ENV XDG_CONFIG_HOME=/etc PATH="/app/.venv/bin:${PATH}"
ENTRYPOINT ["/app/.venv/bin/array-metrics-to-influxdb"] 
