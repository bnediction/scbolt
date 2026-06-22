FROM condaforge/miniforge3:24.11.3-0

SHELL ["/bin/bash", "-lc"]

ARG SCBOLT_ENV_FILES="system align bonesis cellrank core cotan fastq potency scboolseq stream velocity velocyto"
ARG BONESIS_HASH="d70736781f88faee334ef79622e144216837f4c5"

ENV PYTHONUNBUFFERED=1
ENV PATH=/opt/conda/bin:${PATH}
ENV DEBIAN_FRONTEND=noninteractive

COPY envs/conda/ /tmp/scbolt-conda-envs/

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        cm-super \
        dvipng \
        texlive \
        texlive-extra-utils \
        texlive-fonts-recommended \
        texlive-latex-extra \
    && rm -rf /var/lib/apt/lists/* \
    && conda install -y -n base -c conda-forge git \
    && for env_file in ${SCBOLT_ENV_FILES}; do \
        conda env create -f "/tmp/scbolt-conda-envs/${env_file}.yml"; \
    done \
    && conda run --no-capture-output -n scbolt-bonesis python -m pip install \
        --force-reinstall \
        --no-deps \
        "git+https://github.com/bnediction/bonesis.git@${BONESIS_HASH}" \
    && conda clean -afy \
    && rm -rf /tmp/scbolt-conda-envs

CMD ["bash"]
