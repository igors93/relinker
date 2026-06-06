# Presets

Presets are ready-to-use `RetryPolicy` objects for common situations.

They are not special classes. They return normal policies, so users can keep
customizing them.

```python
from relinker import network

policy = network().attempts(10)
```

## Available presets

| Preset | Best for |
|---|---|
| `fast()` | local operations and quick transient failures |
| `network()` | HTTP clients and external APIs |
| `database()` | database-like transient failures |
| `patient()` | slow services or eventual consistency |
| `background_job()` | workers, queue consumers, and scheduled jobs |

## fast

```python
from relinker import fast

@fast()
def task() -> str:
    return "ok"
```

Default:

- 3 attempts
- fixed delay of 0.1 seconds
- retries `Exception`

## network

```python
from relinker import network

@network()
def call_api() -> str:
    return "response"
```

Default:

- 5 attempts
- random exponential delay
- retries `TimeoutError`, `ConnectionError`, and `OSError`

## database

```python
from relinker import database

@database()
def query() -> str:
    return "row"
```

Default:

- 4 attempts
- exponential delay with jitter
- retries `TimeoutError`, `ConnectionError`, and `OSError`

## patient

```python
from relinker import patient

@patient()
def synchronize() -> str:
    return "done"
```

Default:

- 8 attempts
- slower exponential delay with jitter
- retries `TimeoutError`, `ConnectionError`, and `OSError`

## background_job

```python
from relinker import background_job

@background_job()
def process_job() -> None:
    ...
```

Default:

- 10 attempts
- exponential delay with jitter
- retries `Exception`

This preset intentionally retries broad exceptions because background jobs often
centralize error handling. Relinker will still expose this through
`policy.warnings()`.

## Custom exception types

All presets accept exception types:

```python
@network(TimeoutError)
def call_api() -> str:
    return "response"
```

## Presets are still policies

```python
policy = (
    network()
    .attempts(8)
    .fallback_value({"status": "unavailable"})
)
```
