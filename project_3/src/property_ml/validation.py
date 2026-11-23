"""Minimal schema and value validation before preprocessing."""
import math

REQUIRED = {'price', 'bed', 'bath', 'acre_lot', 'house_size', 'brokered_by',
            'street', 'city', 'state', 'zip_code', 'status', 'prev_sold_date'}
NUMERIC = ('bed', 'bath', 'acre_lot', 'house_size')
CATEGORICAL = ('brokered_by', 'street', 'city', 'state', 'zip_code', 'status')


def validate(item):
    if not isinstance(item, dict) or not REQUIRED.issubset(item):
        return False, 'schema'
    try:
        price = float(item['price'])
        if not math.isfinite(price) or price <= 0:
            return False, 'target'
        for key in NUMERIC:
            value = item[key]
            if value is None:
                continue
            number = float(value)
            if not math.isfinite(number) or number < 0 or (key == 'house_size' and number == 0):
                return False, 'numeric'
        if any(isinstance(item[key], (dict, list)) for key in CATEGORICAL):
            return False, 'category'
    except (TypeError, ValueError):
        return False, 'type'
    return True, 'valid'


def possible_extreme(item):
    """Flags for review, never automatically deletes an outlier."""
    checks = {'price': lambda x: x <= 1, 'bed': lambda x: x > 20,
              'bath': lambda x: x > 20, 'acre_lot': lambda x: x > 1000,
              'house_size': lambda x: x > 50000}
    return any(item.get(k) is not None and fn(float(item[k])) for k, fn in checks.items())
