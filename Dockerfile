FROM pinellolab/stream
# ARG PYTHON_VERSION=3.11.2
RUN apt-get --allow-releaseinfo-change update
RUN apt-get install -y software-properties-common
RUN apt-get install -y --no-install-recommends --fix-missing python3.11
RUN python3 -m venv /venv
RUN apt-get install -y vim
RUN pip install 'networkx==2.3' --force-reinstall
# networkx==2.3 => avoid AttributeError: 'Graph' object has no attribute 'node'
RUN pip install 'h5py==3.8.0'
#RUN pip install 'anndata==0.8.0'
# scanpy
#RUN pip install 'anndata==0.6.0' --force-reinstal
RUN pip install 'pandas==1.0.5' --force-reinstall
# Problem persists when using 1.1.1 pandas version
# pandas==1.0.0 => avoid ValueError: Must have equal len keys and value when setting with an ndarray when calling st.plot_stream()
# pandas>=1.0.5 => avoid TypeError: Cannot interpret '<attribute 'dtype' of 'numpy.generic' objects>' as a data type when calling st.seed_elastic_principal_graph()
ENV PATH=/venv/bin:$PATH
