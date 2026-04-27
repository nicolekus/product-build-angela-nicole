#!/bin/bash
cd "$(dirname "$0")"
export PORT=${PORT:-5000}
python -c "
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath('$0')))
"
python app.py
