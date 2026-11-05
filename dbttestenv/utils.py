from datetime import datetime, date


def date_to_datetime(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


def truncate_datetime(dt: datetime, granularity: str) -> datetime:
    granularity = granularity.lower()
    if granularity == "second":
        return datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    elif granularity == "minute":
        return datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute)
    elif granularity == "hour":
        return datetime(dt.year, dt.month, dt.day, dt.hour)
    elif granularity == "day":
        return datetime(dt.year, dt.month, dt.day)
    elif granularity == "month":
        return datetime(dt.year, dt.month, 1)
    elif granularity == "year":
        return datetime(dt.year, 1, 1)
    else:
        raise ValueError(
            f"Unsupported granularity: {granularity}. "
            "Supported values are: second, minute, hour, day, month, year."
        )


TODAY = truncate_datetime(datetime.now(), "day")
