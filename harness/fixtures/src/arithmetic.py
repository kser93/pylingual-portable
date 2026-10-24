"""Small arithmetic and branch fixture."""


def classify(a, b):
    if a > b and a % 2 == 0:
        return a - b
    if a == b:
        return 0
    if b > a:
        return b - a
    return a + b


def choose(flag, left, right):
    value = left if flag else right
    return value * 2


def main():
    print(classify(8, 3))
    print(choose(True, 4, 9))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
