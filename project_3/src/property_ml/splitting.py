"""Stable group splits shared by exploration and batch training."""
import hashlib
from decimal import Decimal, InvalidOperation
import pandas as pd


def split_for_property(item, row_id):
    street = item.get('street')
    if pd.isna(street) or str(street).strip().casefold() in ('', 'missing', 'none', 'nan'):
        key = f'row:{row_id}'
    else:
        street = str(street).strip()
        try:
            street = format(Decimal(street).normalize(), 'f')
        except InvalidOperation:
            pass
        key = '|'.join([street, *(str(item.get(k)).strip().casefold() for k in ('city', 'state'))])
    bucket = int(hashlib.sha256(key.encode()).hexdigest()[:12], 16) % 100
    return key, 'train' if bucket < 60 else 'validation' if bucket < 80 else 'test'


def assign_splits(frame):
    values = [split_for_property({'street': street, 'city': city, 'state': state}, row_id)[1]
              for row_id, street, city, state in frame[['street', 'city', 'state']].itertuples()]
    return pd.Series(values, index=frame.index, name='split')
