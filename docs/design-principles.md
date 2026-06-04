# Design Principles

Relinker is guided by one central idea:

> Simple by default, powerful by composition, safe by guidance.

## 1. Simple things should be simple

A user should be able to add retry behavior with a decorator:

```python
@retry(attempts=3, delay=1)
def task(): ...
```

## 2. Advanced things should be possible

Simple does not mean limited. Users should be able to build complex policies:

```python
RetryPolicy().attempts(5).retry_if_result(...).stateful_delay(...).fallback(...)
```

## 3. Code should be readable and modular

Each module should have a clear responsibility. Public APIs should remain readable. Internal details should be isolated.

## 4. Names should be intuitive

Prefer names like:

- `attempts()`
- `on()`
- `fixed_delay()`
- `fallback_value()`
- `doctor()`
- `preview()`

Avoid names that force users to understand internal implementation details.

## 5. Defaults should be safe

Relinker should avoid surprising defaults that can overload services or hide serious failures.

## 6. Dangerous policies should produce warnings

Relinker should not block valid application-level choices, but it should warn when something looks risky.

## 7. The user stays in control

Relinker gives tools and guidance. It does not take ownership of application semantics.

## 8. Debugging should be built in

Users should be able to inspect:

- attempts
- errors
- values
- timing
- warnings
- policy explanation

## 9. No unnecessary magic

Behavior should be explicit and explainable.

## 10. Production behavior should be explainable

A retry policy should be easy to review before deployment.
