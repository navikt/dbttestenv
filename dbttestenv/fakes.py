from hashlib import sha256

from faker import Faker


class FakerFactory:
    """Generates faker instances seeded by a sequence name, for reproducibility."""
    _cache: dict[str, Faker]

    def __init__(self):
        self._cache = {}

    def _seed(self, sequence_name: str) -> int:
        """Generate a seed based on the sequence name."""
        return int.from_bytes(sha256(sequence_name.encode("utf8")).digest())

    def get(self, sequence_name: str) -> Faker:
        """Return the faker t."""
        if sequence_name not in self._cache:
            faker = Faker()
            faker.seed_instance(self._seed(sequence_name))
            self._cache[sequence_name] = faker

        return self._cache[sequence_name]
