"""Class, inheritance, property, and classmethod fixture."""


class Accumulator:
    def __init__(self, start=0):
        self.value = start

    def add(self, amount):
        self.value += amount
        return self

    @property
    def doubled(self):
        return self.value * 2

    @staticmethod
    def label():
        return "accumulator"

    @classmethod
    def from_pair(cls, left, right):
        return cls(left + right)


class LimitedAccumulator(Accumulator):
    def __init__(self, limit, start=0):
        super().__init__(start)
        self.limit = limit

    def add(self, amount):
        candidate = self.value + amount
        self.value = min(candidate, self.limit)
        return self


def main():
    acc = LimitedAccumulator(10, 3)
    acc.add(4).add(9)
    print(acc.value, acc.doubled, acc.label())
    other = Accumulator.from_pair(2, 5)
    print(other.value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
