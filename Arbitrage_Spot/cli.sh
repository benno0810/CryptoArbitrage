#!/bin/bash
#  pass all arguments to python entrypoint
export DQUANTENV="dev"
cd dquant && python3 entrypoint.py "$@"
