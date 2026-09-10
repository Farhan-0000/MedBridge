"""
Forwarding wrapper for MedBridge-AQ Benchmark Runner.

Provides backward compatibility for medbridge/tests/evaluation/benchmark_runner.py
forwarding to tests/benchmark/benchmark_runner.py.
"""
import sys
from pathlib import Path

# Ensure root directory is in sys.path
root_dir = Path(__file__).resolve().parent.parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from tests.benchmark.benchmark_runner import main

if __name__ == "__main__":
    main()
