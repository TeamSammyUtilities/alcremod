import re

def parse_duration(text: str) -> int:
    units = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400
    }

    matches = re.findall(r"(\d+(?:\.\d+)?)([smhd])", text.lower())

    if not matches:
        raise ValueError("Invalid duration format")

    total = 0

    for value, unit in matches:
        total += float(value) * units[unit]

    return int(total)

def format_duration(seconds: int) -> str:
    if seconds < 0:
        seconds = abs(seconds)

    units = [
        ("d", 86400),
        ("h", 3600),
        ("m", 60),
        ("s", 1),
    ]

    result = []

    for suffix, size in units:
        value, seconds = divmod(seconds, size)

        if value > 0:
            result.append(f"{int(value)}{suffix}")

    return " ".join(result) if result else "0s"