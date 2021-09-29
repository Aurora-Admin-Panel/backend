#!/bin/bash

while nc -z postgres 5432 1> /dev/null 2>&1; do
  sleep 1;
done;

celery -A tasks worker -n worker0 --loglevel=WARNING  -Ofair -Q high-queue -c 1 --pool=solo &
WORKER0=$!
celery -A tasks worker -B -n worker1 --loglevel=WARNING -Ofair -Q low-queue,high-queue -c 1 --pool=solo &
WORKER1=$!

wait $WORKER0 $WORKER1