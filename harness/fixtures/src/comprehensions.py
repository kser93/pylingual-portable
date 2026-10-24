"""Comprehension, generator, and lambda fixture."""


def transform(rows):
    return {
        name: [value * 2 for value in values if value % 2 == 0]
        for name, values in rows
        if values
    }


def flatten(matrix):
    return [item for row in matrix for item in row if item is not None]


def unique_sorted(values):
    return sorted({value.lower() for value in values})


def running_total(values):
    total = 0
    for value in values:
        total += value
        yield total


def main():
    rows = [("a", [1, 2, 3, 4]), ("b", []), ("c", [6, 8])]
    print(transform(rows))
    print(flatten([[1, None], [2, 3]]))
    print(unique_sorted(["B", "a", "b", "A"]))
    print(list(running_total([1, 2, 3])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
