from collections.abc import Iterator

import pytest
from testcontainers.community.redis import RedisContainer


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    with RedisContainer() as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"
