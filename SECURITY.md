# Security Policy

Relinker is a retry library. It does not process secrets, credentials, or
user-submitted data by itself. Security concerns are most likely to involve
unintended long sleeps, memory growth in unbounded retry loops, or sensitive
data leaking into logs.

---

## Reporting a vulnerability

**Please use GitHub's private security advisory feature** to report security
issues. Do not publish sensitive details in a public issue before the report
has been reviewed and a fix is available.

To open a private advisory: go to the repository → **Security** tab →
**Advisories** → **Report a vulnerability**.

---

## What Relinker protects against

### Input validation

All numeric configuration values (`delays`, `time limits`, `attempt counts`,
`Retry-After` values) are validated at construction time. `NaN`, `inf`, and
boolean arguments are rejected immediately with `InvalidRetryConfigError`.
Empty composite strategies and conditions are also rejected at build time
rather than failing silently at runtime.

### Retry-After header safety

`parse_retry_after()` caps parsed delay values at `MAX_RETRY_AFTER_SECONDS`
(86 400 s / 24 hours) by default. This prevents a malformed or adversarial
`Retry-After` header from causing an unexpectedly long sleep. Pass a `maximum`
argument to tighten the cap for your use case.

### Structured logging

`.with_structured_logging()` excludes exception messages by default. Exception
messages from external services can contain API keys, tokens, user identifiers,
or other sensitive data. Enable `include_error_message=True` only in
environments where log output is controlled.

### RetryResult output

`RetryResult.summary()` excludes exception messages and is the preferred compact
representation for logs. Detailed representations preserve exception messages by
default for compatibility. When output may reach an untrusted log or telemetry
sink, disable message rendering explicitly:

```python
result.to_dict(include_error_message=False)
result.to_json(include_error_message=False)
result.story(include_error_message=False)
```

Redaction affects only the generated representation. The original exception
objects remain available through `RetryResult` and retained `AttemptRecord`
objects for explicit inspection.

### Memory in long-running loops

Policies created with `.forever()` or very high attempt limits accumulate
`AttemptRecord` objects over time. The default `history_limit` of 1000 bounds
this growth. Call `.keep_history(n)` to lower it, or `.keep_history(None)` to
disable the limit explicitly. Disabling the limit in an unbounded retry loop
will grow memory without bound. `doctor()` reports `unbounded_history` when an
effectively infinite policy has no history limit.

### GitHub Actions supply chain

GitHub Actions used by CI and PyPI publishing are pinned to full commit SHAs.
Adjacent comments preserve the human-readable upstream version, and Dependabot
keeps the pinned references updateable through reviewed pull requests. Checkout
steps disable persisted Git credentials, and every job has an explicit timeout.

The PyPI trusted-publishing permission (`id-token: write`) is isolated to the
publish job. Build and validation jobs keep read-only repository permissions and
cannot request a publishing identity token.

---

## Out of scope

- Distributed coordination between processes or machines — `RetryBudget` is
  process-local and does not synchronise across hosts.
- Hard timeouts for running operations — `max_time()` controls when a new retry
  is allowed; it does not interrupt a blocking call already in progress.
