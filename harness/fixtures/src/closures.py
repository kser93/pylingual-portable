"""Closure, nonlocal, and decorator fixture."""


def make_counter(start=0, step=1):
    count = start

    def advance():
        nonlocal count
        count += step
        return count

    return advance


def make_multiplier(factor):
    def multiply(value):
        return value * factor

    return multiply


def trace(function):
    def wrapper(*args, **kwargs):
        result = function(*args, **kwargs)
        return ("traced", result)

    return wrapper


@trace
def add(left, right):
    return left + right


def main():
    counter = make_counter(10, 2)
    print(counter(), counter())
    times_three = make_multiplier(3)
    print(times_three(7))
    print(add(2, 5))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
