  
FROM python:3.8

RUN mkdir /app
WORKDIR /app

RUN apt update && \
    apt install -y openssh-client sshpass

COPY . ./
RUN pip install --no-cache-dir -r requirements.txt
