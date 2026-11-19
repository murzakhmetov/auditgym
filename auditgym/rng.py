"""Portable deterministic PRNG (SplitMix64), independent of the `random` module.

Python only guarantees `random.random()` sequences across versions; helpers
such as `choice`, `sample` or `gauss` may change. This class uses 64-bit
integer arithmetic and IEEE double operations without transcendental
functions, so the same seed yields the same stream on every platform.
"""

from __future__ import annotations

import hashlib

_MASK = (1 << 64) - 1


def seed_from_text(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


class Rng:
    def __init__(self, seed: int | str):
        self.state = seed_from_text(seed) if isinstance(seed, str) else int(seed) & _MASK

    def fork(self, label: str) -> "Rng":
        return Rng(f"{self.state}:{label}")

    def next_u64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & _MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
        return z ^ (z >> 31)

    def random(self) -> float:
        return (self.next_u64() >> 11) / float(1 << 53)

    def randbelow(self, n: int) -> int:
        if n <= 0:
            raise ValueError("n must be positive")
        limit = ((1 << 64) // n) * n
        while True:
            x = self.next_u64()
            if x < limit:
                return x % n

    def randint(self, a: int, b: int) -> int:
        if b < a:
            raise ValueError("empty range")
        return a + self.randbelow(b - a + 1)

    def randrange(self, n: int) -> int:
        return self.randbelow(n)

    def choice(self, seq):
        if not seq:
            raise IndexError("choice from empty sequence")
        return seq[self.randbelow(len(seq))]

    def shuffle(self, items: list) -> None:
        for i in range(len(items) - 1, 0, -1):
            j = self.randbelow(i + 1)
            items[i], items[j] = items[j], items[i]

    def sample(self, population, k: int) -> list:
        pool = list(population)
        if k > len(pool):
            raise ValueError("sample larger than population")
        for i in range(k):
            j = i + self.randbelow(len(pool) - i)
            pool[i], pool[j] = pool[j], pool[i]
        return pool[:k]

    def uniform(self, a: float, b: float) -> float:
        return a + (b - a) * self.random()

    def gauss(self, mu: float, sigma: float) -> float:
        """Irwin-Hall approximation (sum of 12 uniforms): additions only."""
        s = 0.0
        for _ in range(12):
            s += self.random()
        return mu + sigma * (s - 6.0)
