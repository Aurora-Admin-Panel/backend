FROM python:3.8-slim

ARG BACKEND_APP_VERSION=dev
ENV BACKEND_VERSION=$BACKEND_APP_VERSION

RUN mkdir /app
WORKDIR /app
COPY . ./

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openssh-client sshpass && \
    rm -rf /var/lib/apt/lists/*

RUN sed -i '/#   StrictHostKeyChecking /c StrictHostKeyChecking no' /etc/ssh/ssh_config && \
    sed -i 's/^#\s\+UserKnownHostsFile.*/UserKnownHostsFile \/dev\/null/' /etc/ssh/ssh_config

# Reference: https://github.com/docker-library/python/blob/9242c448c7e50d5671e53a393fc2c464683f35dd/3.8/bullseye/slim/Dockerfile
RUN savedAptMark="$(apt-mark showmanual)" && \
    apt-get update && \
    apt-get install -y --no-install-recommends gcc libc6-dev libffi-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    find /usr/local -depth -type d -a \( -name tests -o -name __pycache__ \) -exec rm -rf '{}' + && \
    apt-mark auto '.*' > /dev/null && \
	apt-mark manual $savedAptMark && \
    \
    find /usr/local -type f -executable -not \( -name '*tkinter*' \) -exec ldd '{}' ';' \
		| awk '/=>/ { print $(NF-1) }' \
		| sort -u \
		| xargs -r dpkg-query --search \
		| cut -d: -f1 \
		| sort -u \
		| xargs -r apt-mark manual \
    && \
    apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false && \
    rm -rf /var/lib/apt/lists/*
