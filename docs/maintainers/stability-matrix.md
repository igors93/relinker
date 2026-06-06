# Stability matrix

This table is a map of automated contracts. It is not evidence of production
adoption or real-world operational usage.

| Capability | Sync run | Async run | Sync decorator | Async decorator | Sync context | Async context | Primary contract |
|---|---|---|---|---|---|---|---|
| Exception retry | Yes | Yes | Yes | Yes | Yes | Yes | `tests/contracts/test_exception_retry_contract.py` |
| Result retry | Yes | Yes | Yes | Yes | Yes | Yes | `tests/contracts/test_result_retry_contract.py` |
| Explicit None result | Yes | Yes | Yes | Yes | Yes | Yes | `tests/unit/test_none_result.py` |
| TryAgain | Yes | Yes | Yes | Yes | Yes | Yes | `tests/integration/test_try_again.py` |
| Attempt limit | Yes | Yes | Yes | Yes | Yes | Yes | `tests/contracts/test_exhaustion_contract.py` |
| max_time budget | Yes | Yes | Yes | Yes | Yes | Yes | `tests/unit/test_max_time_budget.py` |
| Fixed and exponential delay | Yes | Yes | Yes | Yes | N/A | N/A | `tests/integration/test_policy_delays.py` |
| Fallback | Yes | Yes | Yes | Yes | Yes | Yes | `tests/contracts/test_exhaustion_contract.py` |
| Custom exhaustion exception | Yes | Yes | Yes | Yes | Yes | Yes | `tests/contracts/test_exhaustion_contract.py` |
| return_result | Yes | Yes | Yes | Yes | Yes | Yes | `tests/contracts/test_exhaustion_contract.py` |
| Event ordering | Yes | Yes | Yes | Yes | Yes | Yes | `tests/contracts/test_event_contract.py` |
| Bounded history | Yes | Yes | Yes | Yes | Yes | Yes | `tests/contracts/test_history_contract.py` |
| Retry Budget | Yes | Yes | Yes | Yes | Yes | Yes | `tests/contracts/test_retry_budget_contract.py` |
| Cancellation | N/A | Yes | N/A | Yes | N/A | Yes | `tests/contracts/test_execution_parity_contract.py` |

## Interpretation

`Yes` means the capability is covered by an automated contract. `N/A` means the
capability is not applicable to that execution shape.

This matrix does not mean the capability has been adopted in production. Failures
found during real use should become focused regression tests.
