FROM condaforge/miniforge3:24.11.3-0

SHELL ["/bin/bash", "-lc"]

ARG SCBOLT_ENV_FILES="system align bonesis cellrank core cotan fastq potency scboolseq stream velocity velocyto"
ARG BONESIS_HASH="d70736781f88faee334ef79622e144216837f4c5"

ENV PYTHONUNBUFFERED=1
ENV PATH=/opt/conda/bin:${PATH}

COPY envs/ /tmp/scbolt-envs/

RUN conda install -y -n base -c conda-forge git \
    && for env_file in ${SCBOLT_ENV_FILES}; do \
        conda env create -f "/tmp/scbolt-envs/${env_file}.yml"; \
    done \
    && conda run --no-capture-output -n scbolt-bonesis python -m pip install \
        --force-reinstall \
        --no-deps \
        "git+https://github.com/bnediction/bonesis.git@${BONESIS_HASH}" \
    && conda clean -afy \
    && rm -rf /tmp/scbolt-envs

CMD ["bash"]
