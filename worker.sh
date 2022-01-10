#!/bin/bash

while nc -z postgres 5432 1> /dev/null 2>&1; do
  sleep 1;
done;

huey_consumer.py tasks.huey -w $(expr $(nproc) \* 2)
