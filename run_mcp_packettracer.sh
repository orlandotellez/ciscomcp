#!/usr/bin/env bash
cd "/home/kenerth/IA redes"
VENV="/home/kenerth/IA redes/.venv"
export PATH="$VENV/bin:$PATH"
export VIRTUAL_ENV="$VENV"
unset PYTHONPATH
unset PYTHONHOME
unset PYTHONSTARTUP
exec "$VENV/bin/python" -s "/home/kenerth/IA redes/server.py"
