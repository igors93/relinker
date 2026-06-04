# Examples

This directory contains standalone examples for RetryFlow.

## How to run

Run examples from the **project root directory** using the `-m` flag:

```bash
cd retryflow/   # project root, where pyproject.toml lives

# Install the package first (editable mode)
pip install -e .

# Run any example
python -m examples.basic_retry
python -m examples.retry_with_policy
python -m examples.retry_try_again
python -m examples.retry_http_like
python -m examples.retry_database_like
python -m examples.retry_polling
python -m examples.retry_with_logging
python -m examples.retry_with_diagnostics
python -m examples.retry_with_statistics
python -m examples.retry_with_fallback
python -m examples.retry_with_events
python -m examples.retry_async
python -m examples.retry_context_manager
python -m examples.retry_result_to_json
python -m examples.retry_return_result
python -m examples.retry_production_checklist
python -m examples.retry_without_sleep_in_tests
python -m examples.retry_with_presets
```

## What each example shows

| File | Topic |
|------|-------|
| `basic_retry.py` | Simple `@retry` decorator |
| `retry_with_policy.py` | `RetryPolicy` builder |
| `retry_with_presets.py` | Preset policies (`network`, `database`, etc.) |
| `retry_try_again.py` | `TryAgain` explicit retry signal |
| `retry_http_like.py` | HTTP status-based retry helpers |
| `retry_database_like.py` | Database retry patterns and statistics |
| `retry_polling.py` | Polling with `TryAgain` and `retry_if_result` |
| `retry_with_logging.py` | Built-in logging integration |
| `retry_with_diagnostics.py` | Policy warnings and simulation |
| `retry_production_checklist.py` | Pre-deploy policy review |
| `retry_with_statistics.py` | Per-function retry statistics |
| `retry_with_fallback.py` | Fallback values on exhaustion |
| `retry_with_events.py` | Observability via events |
| `retry_async.py` | Async retry with decorated functions |
| `retry_context_manager.py` | Context manager retry blocks |
| `retry_result_to_json.py` | Serializing results to JSON |
| `retry_return_result.py` | Working with `RetryResult` |
| `retry_without_sleep_in_tests.py` | Testing without real sleep |
| `fake_services.py` | Shared fake services used by other examples |

## No external dependencies

All examples run without any external packages. They use only RetryFlow and
Python's standard library.
