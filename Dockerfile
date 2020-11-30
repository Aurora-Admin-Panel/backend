  
FROM python:3.8

ARG BACKEND_APP_VERSION=dev
ENV BACKEND_VERSION=$BACKEND_APP_VERSION

RUN mkdir /app
WORKDIR /app

RUN apt update && \
    apt install -y openssh-client sshpass

COPY . ./
RUN pip install --no-cache-dir -r requirements.txt
