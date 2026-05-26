"""Tests for the mtime-based agent catalog cache added in v4.6."""

from __future__ import annotations

import time



def _get_agent_catalog():
    import agent_catalog
    return agent_catalog


def test_catalog_load_uses_cache_on_repeat_calls(opc_env):
    agent_catalog = _get_agent_catalog()
    agent_catalog.invalidate_catalog_cache()

    first = agent_catalog.load_agent_catalog(strict=True)
    assert first, "expected at least one agent in the default pack"

    second = agent_catalog.load_agent_catalog(strict=True)
    assert second == first

    # The cache must hold the exact same shape (post hot path); verify by
    # checking the underlying cache map directly.
    assert ("default", True) in agent_catalog._CATALOG_CACHE


def test_catalog_cache_invalidates_on_file_mtime_change(opc_env, tmp_path):
    """Touching any agent file should drop the cache entry."""
    agent_catalog = _get_agent_catalog()
    agent_catalog.invalidate_catalog_cache()

    initial = agent_catalog.load_agent_catalog(strict=True)
    assert ("default", True) in agent_catalog._CATALOG_CACHE
    sig_before = agent_catalog._CATALOG_CACHE[("default", True)][0]

    # Touch one of the agent files so its mtime changes.
    agents_dir = agent_catalog.get_agents_dir("default")
    target = next(agents_dir.glob("*.md"))
    # Sleep one mtime tick to make sure the change is observable.
    time.sleep(0.01)
    target.touch()

    refreshed = agent_catalog.load_agent_catalog(strict=True)
    sig_after = agent_catalog._CATALOG_CACHE[("default", True)][0]
    assert sig_before != sig_after, "signature should differ after touch"
    assert len(refreshed) == len(initial)


def test_invalidate_catalog_cache_clears_entries(opc_env):
    agent_catalog = _get_agent_catalog()
    agent_catalog.load_agent_catalog(strict=True)
    assert agent_catalog._CATALOG_CACHE  # populated

    agent_catalog.invalidate_catalog_cache()
    assert not agent_catalog._CATALOG_CACHE


def test_catalog_cache_speeds_up_repeated_loads(opc_env):
    """End-to-end speed check: the cached path must beat the uncached path.

    Not a strict ops/sec assertion, just a generous lower bound so a future
    regression that drops caching gets caught.
    """
    agent_catalog = _get_agent_catalog()
    agent_catalog.invalidate_catalog_cache()

    # Warm
    agent_catalog.load_agent_catalog(strict=True)

    cached_start = time.perf_counter()
    for _ in range(50):
        agent_catalog.load_agent_catalog(strict=True)
    cached_elapsed = time.perf_counter() - cached_start

    # Cold (invalidate each time → forces full filesystem walk)
    cold_start = time.perf_counter()
    for _ in range(50):
        agent_catalog.invalidate_catalog_cache()
        agent_catalog.load_agent_catalog(strict=True)
    cold_elapsed = time.perf_counter() - cold_start

    assert cached_elapsed < cold_elapsed, (
        f"cache made things slower: cached={cached_elapsed:.3f}s cold={cold_elapsed:.3f}s"
    )
    # Sanity: cold path is at least 3× slower than cached on a real catalog.
    if cold_elapsed > 0.05:
        assert cached_elapsed * 3 < cold_elapsed, (
            f"cache speedup < 3× — possible regression. "
            f"cached={cached_elapsed:.3f}s cold={cold_elapsed:.3f}s"
        )
