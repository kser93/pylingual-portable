"""Loop, break/continue, and accumulator fixture."""


def find_pair(values, target):
    seen = set()
    for value in values:
        needed = target - value
        if needed in seen:
            return (needed, value)
        seen.add(value)
    return None


def sum_positive(values):
    total = 0
    for value in values:
        if value <= 0:
            continue
        total += value
        if total > 100:
            break
    else:
        total += 1
    return total


def countdown(start):
    result = []
    while start > 0:
        result.append(start)
        start -= 1
    return result


def main():
    print(find_pair([1, 4, 6, 9], 10))
    print(sum_positive([5, -1, 20, 80, 2]))
    print(countdown(4))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
