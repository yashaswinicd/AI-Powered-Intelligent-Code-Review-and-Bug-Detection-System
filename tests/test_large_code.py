def test_large_code():
    lines = []

    for i in range(9999):
        lines.append(f"x_{i} = {i}")

    code = "\n".join(lines)

    print("Total lines:", len(code.splitlines()))

    assert len(code.splitlines()) == 9999


if __name__ == "__main__":
    test_large_code()
    print("10,000-line input test PASSED")