# Benchmarks

This directory contains manual performance diagnostics for Relinker.

These scripts are not CI gates and do not enforce machine-dependent timing
thresholds.

## Smoke Benchmark

```bash
python benchmarks/smoke.py --iterations 1000
```

Use this for a quick local check across common retry paths.

## RetryBudget Benchmark

```bash
python benchmarks/retry_budget.py --quick
python benchmarks/retry_budget.py
```

The quick mode is suitable for local smoke checks. The full mode measures more
reservation counts and capacities.
