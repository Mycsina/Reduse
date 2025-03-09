#!/usr/bin/env python
# This script can be run from within the backend/ directory

import os
import sys

# Add the parent directory to sys.path to make 'backend' importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pydantic2ts import generate_typescript_defs

generate_typescript_defs(
    module="backend.routers.all_defs", output="../frontend/src/types/api.ts", json2ts_cmd="npx json2ts"
)
