# Security Policy

Relinker is a retry library and does not process secrets by itself.

## Reporting a vulnerability

Please open a private security advisory on GitHub if you discover a security
issue.

Do not publish sensitive details publicly before the issue is reviewed.

## Security philosophy

Relinker should not hide application failures or silently change application
data. When possible, Relinker exposes behavior through explicit results,
events, statistics, and diagnostics.

## Input validation

Relinker validates all numeric configuration values at construction time.
`NaN`, `inf`, and boolean arguments are rejected for any field that expects a
real number (delays, time limits, Retry-After values). Empty composite
strategies and conditions are rejected immediately rather than failing silently
at runtime.

## HTTP Retry-After header safety

`parse_retry_after()` caps parsed delay values at `MAX_RETRY_AFTER_SECONDS`
(86 400 s / 24 hours) by default. This prevents a malformed or adversarial
`Retry-After` header from causing an arbitrarily long sleep. Pass a custom
`maximum` argument to tighten the cap for your use case.

## History and memory

Policies created with `.forever()` or very high attempt limits accumulate
`AttemptRecord` objects over time. The default `history_limit` of 1000 bounds
this growth. Call `.keep_history(n)` to lower it or `.keep_history(None)` to
disable the limit explicitly. Disabling the limit in a truly unbounded retry
loop will grow memory without bound.
