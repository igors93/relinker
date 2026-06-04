# When Not to Retry

Retry is not always the right answer.

## Do not retry validation errors

Examples:

- invalid email
- missing required field
- malformed payload

These are usually permanent until the input changes.

## Do not retry authentication or authorization errors by default

Examples:

- invalid token
- permission denied
- forbidden

Retrying these can hide configuration or security problems.

## Be careful with payments and side effects

Do not retry payment creation, order creation, or email sending unless the
operation is idempotent or protected by application-level safeguards.

## Do not retry without observability

If retry is hiding failures, users may not know a dependency is unhealthy.

Use:

- `RetryResult`
- events
- `retry_stats`
- logs
- metrics

## Do not retry forever without a shutdown strategy

Retry forever can be useful, but it should be paired with cancellation,
monitoring, and operational controls.
