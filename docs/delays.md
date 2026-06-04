# Delays

Delays control how long RetryFlow waits before the next attempt.

RetryFlow keeps delay names simple and predictable.

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

## Random exponential delay

Use exponential growth with random jitter.

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

Use an explicit sequence. When the sequence ends, RetryFlow reuses the last value.

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

## Custom delay

```python
policy = RetryPolicy().custom_delay(lambda attempt: attempt * 0.25)
```

Custom delays must return a number greater than or equal to zero.
