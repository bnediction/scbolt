FROM pinellolab/stream
# ARG PYTHON_VERSION=3.11.2
RUN apt-get --allow-releaseinfo-change update
RUN apt-get install -y software-properties-common
RUN apt-get install -y --no-install-recommends --fix-missing python3.11
RUN python3 -m venv /venv
RUN apt-get install -y vim
RUN pip install 'networkx==2.3' 'pandas==1.0' 'numpy==1.16.5' --force-reinstall
RUN pip install pip scanpy anndata --upgrade
ENV PATH=/venv/bin:$PATH
