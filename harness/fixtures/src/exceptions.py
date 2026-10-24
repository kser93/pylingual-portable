"""Exception handling and cleanup fixture."""


def parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
    finally:
        marker = "done"


def divide(left, right):
    try:
        result = left / right
    except ZeroDivisionError:
        result = 0
    else:
        result += 1
    finally:
        result = result * 2
    return result


def safe_get(mapping, key, default=None):
    try:
        return mapping[key]
    except KeyError:
        return default


def main():
    print(parse_int("12"), parse_int("nope"))
    print(divide(10, 2), divide(1, 0))
    print(safe_get({"a": 1}, "b", 7))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
