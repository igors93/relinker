# Delays

Delays control how long Relinker waits before the next attempt.

Relinker keeps delay names simple and predictable.

## Choosing the right delay

| Delay | Best for |
|---|---|
| `no_delay()` | Tests, local-only operations, immediate retry loops controlled elsewhere |
| `fixed_delay()` | Simple and predictable retry behavior |
| `linear_delay()` | Slow growth without becoming aggressive too quickly |
| `exponential_delay()` | External services and transient infrastructure failures |
| `random_exponential_delay()` | Many clients retrying at the same time |
| `chain_delay()` | Full control over each retry wait |
| `.jitter()` | Reducing retry spikes and thundering herd behavior |

## No delay

```python
policy = RetryPolicy().no_delay()
```

## Fixed delay

```python
policy = RetryPolicy().fixed_delay(1)
```

## Linear delay

```python
policy = RetryPolicy().linear_delay(start=1, step=2, maximum=10)
```

Timeline:

```text
1s, 3s, 5s, 7s, 9s, 10s...
```

## Exponential delay

```python
policy = RetryPolicy().exponential_delay(base=1, factor=2, maximum=30)
```

Timeline:

```text
1s, 2s, 4s, 8s, 16s, 30s...
```

## Random exponential delay

```python
policy = RetryPolicy().random_exponential_delay(
    base=1,
    factor=2,
    minimum=0,
    maximum=30,
)
```

This is useful when many clients may retry at the same time.

## Chain delay

```python
policy = RetryPolicy().chain_delay([0.1, 0.5, 1, 2, 5])
```

Timeline:

```text
0.1s, 0.5s, 1s, 2s, 5s, 5s, 5s...
```

## Add jitter to any delay

```python
policy = (
    RetryPolicy()
    .exponential_delay(base=1, maximum=30)
    .jitter(maximum=0.5)
)
```

This means:

```text
exponential delay + random delay between 0 and 0.5 seconds
```

## Custom delay

```python
policy = RetryPolicy().custom_delay(lambda attempt: attempt * 0.25)
```

Custom delays must return a number greater than or equal to zero.
