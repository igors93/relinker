from relinker import RetryPolicy

policy = RetryPolicy().forever().on(Exception).no_delay()

if __name__ == "__main__":
    for warning in policy.warnings():
        print(f"{warning.code}: {warning.message}")
        if warning.hint is not None:
            print(f"  hint: {warning.hint}")

    print()
    print(policy.simulate(attempts=3).describe())
