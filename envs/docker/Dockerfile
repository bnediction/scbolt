FROM golang:1.22-bookworm AS launcher

WORKDIR /src

COPY go.mod VERSION ./
COPY launcher/ ./launcher/

ARG SCBOLT_GIT_COMMIT=unknown
ARG SCBOLT_IMAGE=ghcr.io/bnediction/scbolt:latest

RUN version="$(tr -d '[:space:]' < VERSION)" \
    && CGO_ENABLED=0 go build \
        -ldflags "-s -w -X main.launcherVersion=${version} -X main.sourceRevision=${SCBOLT_GIT_COMMIT} -X main.defaultImage=${SCBOLT_IMAGE}" \
        -o /usr/local/bin/scbolt \
        ./launcher/scbolt

FROM mambaorg/micromamba:debian12-slim

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        cm-super \
        coreutils \
        curl \
        dvipng \
        findutils \
        gawk \
        git \
        grep \
        gzip \
        make \
        sed \
        tar \
        texlive \
        texlive-extra-utils \
        texlive-fonts-recommended \
        texlive-latex-extra \
        unzip \
        wget \
    && rm -rf /var/lib/apt/lists/*

USER $MAMBA_USER

ARG SCBOLT_ENV_FILES="system align bonesis cellrank core cotan fastq potency scboolseq stream velocity velocyto"

COPY --chown=$MAMBA_USER:$MAMBA_USER envs/conda/ /tmp/scbolt-conda-envs/

RUN for env_file in ${SCBOLT_ENV_FILES}; do \
        micromamba env create -y -f "/tmp/scbolt-conda-envs/${env_file}.yml"; \
    done \
    && micromamba clean --all --yes \
    && rm -rf /tmp/scbolt-conda-envs

COPY --chown=$MAMBA_USER:$MAMBA_USER . /opt/scbolt
COPY --from=launcher /usr/local/bin/scbolt /usr/local/bin/scbolt

ARG SCBOLT_GIT_COMMIT=unknown

ENV SCBOLT_HOME=/opt/scbolt \
    SCBOLT_ROOT=/opt/scbolt \
    SCBOLT_GIT_COMMIT=${SCBOLT_GIT_COMMIT} \
    SCBOLT_IN_DOCKER=true \
    SCBOLT_DEFAULT_BACKEND=docker \
    PATH=/usr/local/bin:/opt/scbolt/bin:${PATH} \
    PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1

WORKDIR /work

ENTRYPOINT ["/usr/local/bin/scbolt"]
