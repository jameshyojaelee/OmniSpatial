# syntax=docker/dockerfile:1

FROM python:3.11-slim AS wheels
ENV PIP_NO_CACHE_DIR=1
RUN pip install --upgrade pip build
WORKDIR /src
COPY omnispatial ./omnispatial
COPY plugins ./plugins
RUN python -m build ./omnispatial --wheel --outdir /dist
RUN python -m build ./plugins/omnispatial-adapter-cosmx-public --wheel --outdir /dist
RUN python -m build ./plugins/omnispatial-adapter-visium-hd --wheel --outdir /dist


FROM python:3.11-slim AS docs
ENV PIP_NO_CACHE_DIR=1
RUN pip install --upgrade pip mkdocs mkdocs-material
WORKDIR /src
COPY mkdocs.yml ./
COPY docs ./docs
RUN mkdocs build --strict --config-file mkdocs.yml --site-dir /site


FROM python:3.11-slim AS runtime
LABEL org.opencontainers.image.source="https://github.com/omnispatial/omnispatial"
LABEL org.opencontainers.image.description="OmniSpatial CLI, Napari plugin, and docs packaged for container deployments."
LABEL org.opencontainers.image.licenses="MIT"
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    OMNISPATIAL_DOCS=/opt/omnispatial/docs
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/omnispatial
COPY --from=wheels /dist /tmp/dist
RUN pip install --upgrade pip && pip install /tmp/dist/*.whl
COPY --from=docs /site /opt/omnispatial/docs
COPY examples /opt/omnispatial/examples
ENTRYPOINT ["omnispatial"]
CMD ["--help"]
