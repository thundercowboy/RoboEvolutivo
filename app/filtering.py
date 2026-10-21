from datetime import datetime, time


def date_period(start, end):
    def parse(value, upper):
        value = value.strip()
        if not value:
            return None
        try:
            if len(value) == 10:
                day = datetime.strptime(value, '%d/%m/%Y').date()
                return datetime.combine(day, time.max if upper else time.min)
            result = datetime.strptime(value, '%d/%m/%Y %H:%M')
            return result.replace(second=59, microsecond=999999) if upper else result
        except ValueError:
            raise ValueError('Use DD/MM/AAAA ou DD/MM/AAAA HH:mm.') from None
    lower, upper = parse(start, False), parse(end, True)
    if lower and upper and lower > upper:
        raise ValueError('A data inicial precisa ser anterior ou igual à final.')
    return lower, upper


def within_period(value, period):
    current = datetime.strptime(value, '%d/%m/%Y %H:%M:%S')
    lower, upper = period
    # A minute entered as the upper bound includes that whole minute.
    return (lower is None or current >= lower) and (upper is None or current <= upper)
