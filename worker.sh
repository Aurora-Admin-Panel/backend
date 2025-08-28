#!/usr/bin/env bash
set -euo pipefail

exec huey_consumer.py tasks.huey -k process -w $(nproc)