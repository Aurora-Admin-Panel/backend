#!/bin/bash

while nc -z postgres 5432 1> /dev/null 2>&1; do
  sleep 1;
done;

celery -A tasks worker -n worker0 --loglevel=INFO -Ofair -Q high-queue &
WORKER0=$!
celery -A tasks worker -B -n worker1 --loglevel=INFO -Ofair -Q low-queue,high-queue &
WORKER1=$!

wait $WORKER0 $WORKER1