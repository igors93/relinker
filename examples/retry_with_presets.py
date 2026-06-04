from retryflow import network


@network()
def call_external_api() -> str:
    return "response"


if __name__ == "__main__":
    print(call_external_api())
    print(call_external_api.retry_stats.to_dict())
