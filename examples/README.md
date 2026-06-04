# Relinker Examples

This directory contains standalone examples that show how to use Relinker in real situations.

Run examples from the project root directory using `python -m`:

```bash
cd relinker
python -m examples.basic_retry
```

## Recommended order

| Order | Example | What it teaches |
|---:|---|---|
| 1 | `basic_retry.py` | The smallest useful retry decorator |
| 2 | `retry_with_policy.py` | The fluent `RetryPolicy` builder |
| 3 | `retry_with_presets.py` | Ready-to-use presets |
| 4 | `retry_preview_and_explain.py` | Understanding a policy before running it |
| 5 | `retry_policy_doctor.py` | Detecting risky retry policies |
| 6 | `retry_with_fallback.py` | Returning fallback values when retries fail |
| 7 | `retry_return_result.py` | Inspecting `RetryResult` |
| 8 | `retry_result_to_json.py` | Serializing retry results |
| 9 | `retry_with_statistics.py` | Per-function retry statistics |
| 10 | `retry_with_events.py` | Event hooks for observability |
| 11 | `retry_with_logging.py` | Standard logging integration |
| 12 | `retry_structured_logging.py` | JSON structured retry logs |
| 13 | `retry_http_like.py` | HTTP status retry without external packages |
| 14 | `retry_http_retry_after.py` | Respecting the `Retry-After` header |
| 15 | `retry_database_like.py` | Database-like retry patterns |
| 16 | `retry_polling.py` | Polling until a result is ready |
| 17 | `retry_try_again.py` | Explicit retry with `TryAgain` |
| 18 | `retry_async.py` | Async retry |
| 19 | `retry_context_manager.py` | Retrying inline blocks |
| 20 | `retry_without_sleep_in_tests.py` | Testing retry behavior without waiting |
| 21 | `retry_production_checklist.py` | Pre-production policy review |

## No external dependencies

Examples use only Python's standard library and Relinker.
