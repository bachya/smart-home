FROM jupyter/minimal-notebook:latest

USER root

RUN apt-get update \
  && apt-get install --no-install-recommends -y \
      libmariadbclient-dev \
  && python3 -m pip install \
    beautifulsoup4==4.6.3 \
    bokeh==1.0.2 \
    geopy==1.18.1 \
    HASS-data-detective==1.0 \
    influxdb==5.2.1 \
    ipywidgets==7.4.2 \
    jupyterlab_github==0.7.0 \
    jupyterlab==0.35.4 \
    matplotlib==3.0.2 \
    mysqlclient==1.3.14 \
    nbconvert==5.4.0 \
    numpy==1.15.4 \
    pandas-datareader==0.7.0 \
    pandas==0.23.4 \
    psycopg2==2.7.6.1 \
    python-dateutil==2.7.5 \
    scrapy==1.5.1 \
    SQLAlchemy==1.2.15 \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

USER $NB_UID
