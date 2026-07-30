FROM mambaorg/micromamba:debian12-slim

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG SCBOLT_ENV_FILES="align bonesis cellrank core cotan fastq potency scboolseq stream velocity velocyto"
ARG SCBOLT_GIT_COMMIT=unknown

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
        python3-yaml \
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

COPY --chown=$MAMBA_USER:$MAMBA_USER envs/conda/ /tmp/scbolt-conda-envs/

RUN for env_file in ${SCBOLT_ENV_FILES}; do \
        micromamba env create -y -f "/tmp/scbolt-conda-envs/${env_file}.yml"; \
    done \
    && micromamba clean --all --yes \
    && rm -rf /tmp/scbolt-conda-envs

COPY --chown=$MAMBA_USER:$MAMBA_USER . /opt/scbolt

ENV SCBOLT_HOME=/opt/scbolt \
    SCBOLT_GIT_COMMIT=${SCBOLT_GIT_COMMIT} \
    SCBOLT_IN_DOCKER=true \
    SCBOLT_DEFAULT_BACKEND=docker \
    PATH=/opt/scbolt/bin:${PATH} \
    PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1

WORKDIR /work

ENTRYPOINT ["scbolt"]
