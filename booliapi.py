#!/usr/bin/env python
# -*- coding: utf-8 -*-

import itertools
import json
import operator
import random
import re
import string
import urllib2
from datetime import datetime
from hashlib import sha1
from urllib import urlencode

__version__ = "0.0"

_fields = {
    "id": "booliId", "created": "created",
    "type": "objectType", "agency": "agent.name",
    "address": "location.address.streetAddress",
    "neighborhood": "location.namedAreas.namedArea",
    "city": "location.address.city",
    "municipality": "location.region.municipalityName",
    "county": "location.region.countyName",
    "rooms": "nRooms", "size": "areaLiving", "lot_size": "areaLot",
    "price": "priceForSale", "fee": "fees.fee.amount",
    "lat": "location.address.position.latitude",
    "lon": "location.address.position.longitude",
    "url": "listingUrl", "image_url": "images.image.url",
    }

_int = lambda x: int(x or 0)
_float = lambda x: float(x or 0)
_field_types = {
    "size": _float, "lot_size": _float, "rooms": _float,
    "lat": _float, "lon": _float,
    "id": _int, "fee": _int, "price": _int,
    "created": lambda x: datetime.strptime(x, "%Y-%m-%d %H:%M:%S"),
   }

filterops = {
    "gt": operator.gt, "gte": operator.ge, "lt": operator.lt, "lte": operator.le,
    "exact": operator.eq, "iexact": lambda a, b: a.lower() == b.lower(),
    "in": lambda a, b: a in b,
    "contains": lambda a, b: b in a,
    "icontains": lambda a, b: b.lower() in a.lower(),
    "startswith": lambda a, b: a.startswith(b),
    "istartswith": lambda a, b: a.lower().startswith(b.lower()),
    "endswith": lambda a, b: a.endswith(b),
    "iendswith": lambda a, b: a.lower().endswith(b.lower()),
    "range": lambda a, b: b[0] <= a <= b[1],
    }

def html_decode(s):
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

def flatten(d, p=()):
    return itertools.chain(*(flatten(v, p+(k,)) if isinstance(v, dict)
                             else [(".".join(p+(k,)), v)]
                             for (k, v) in d.items()))

def urlify_value(value):
    if isinstance(value, unicode):
        return value.encode("utf-8")
    elif isinstance(value, int):
        return str(int(value))
    elif isinstance(value, list):
        return ",".join(urlify_value(x) for x in value)
    return str(value)

def smart_urlencode(params):
    return urlencode(dict((key, urlify_value(value))
                          for key, value in params.items()))

def cmp_attr(key):
    """Return an comparator function that uses the "key" attribute."""
    if key.startswith("-"):
        key = key[1:]
        return lambda a, b: -cmp(getattr(a, key), getattr(b, key))
    else:
        return lambda a, b: cmp(getattr(a, key), getattr(b, key))

def cmp_multi(keys):
    """Return a compound attribute comparator function based on a
    sequence of keys.

    Example: use ["firstname", "-lastname"] to sort first by the
    "firstname" attribute (ascending), then by "lastname"
    (descending)."""
    cmps = [cmp_attr(key) for key in keys]
    def func(a, b):
        comparators, result = cmps[:], 0
        while comparators and not result:
            result = comparators.pop(0)(a, b)
        return result
    return func

def ensure_callable(obj):
    """'F-ify' an object - if obj is callable return it as is;
    otherwise, return a function that takes one argument and returns
    obj. (For internal use. You don't need to understand it.)"""
    return obj if callable(obj) else lambda *a,**k: obj

def make_filter(**kwargs):
    """Return a function that can be used to filter a list according
    to the given parameters."""
    params = [((k + "__exact").split("__")[:2], v) for k, v in kwargs.items()]
    return lambda item: all(filterops[op](getattr(item, attr),
                                          ensure_callable(val)(item))
                            for ((attr, op), val) in params)

class Q(object):
    def __init__(self, *tests, **kwargs):
        self.test = reduce(lambda a, b: lambda x: a(x) and b(x),
                           [x.test if hasattr(x, "test") else x for x in tests]
                           + [make_filter(**kwargs)])
    def __and__(self, other):
        return Q(lambda x: self(x) and other(x))
    def __or__(self, other):
        return Q(lambda x: self(x) or other(x))
    def __invert__(self):
        return Q(lambda x: not self(x))
    def __call__(self, obj):
        return self.test(obj)


class F(object):
    def __init__(self, key):
        self.key = key if callable(key) else operator.attrgetter(key)
    def __add__(self, other):
        return F(lambda x: self(x) + ensure_callable(other)(x))
    def __sub__(self, other):
        return F(lambda x: self(x) - ensure_callable(other)(x))
    def __mul__(self, other):
        return F(lambda x: self(x) * ensure_callable(other)(x))
    def __div__(self, other):
        return F(lambda x: self(x) / ensure_callable(other)(x))
    def __call__(self, obj):
        return self.key(obj)


class ResultSet(list):
    def __init__(self, *args, **kwargs):
        super(ResultSet, self).__init__(*args, **kwargs)
    def filter(self, *args, **kwargs):
        return ResultSet(filter(Q(*args, **kwargs), self))
    def exclude(self, *args, **kwargs):
        return ResultSet(filter(~Q(*args, **kwargs), self))
    def order_by(self, *args):
        return ResultSet(sorted(self, cmp_multi(args)))
    def group_by(self, key, count_only=False):
        return [(key, len(list(group)) if count_only else ResultSet(group))
                for key, group in itertools.groupby(self, key=F(key))]

class BooliAPI(object):
    base_url = "http://api.booli.se/listing/"

    def __init__(self, caller_id, key):
        self.caller_id = caller_id
        self.key = key
        
    def search(self, area="", **params):
        url = self._build_url(area, params)
        response = urllib2.urlopen(url)
        data = json.load(response)
        content = data["booli"]["content"]
        resultset = ResultSet([Listing(item) for item in content["listings"]])
        resultset.total_count = content["totalListingCount"]
        return resultset

    def _build_url(self, area, params):
        """Return a complete API request URL for the given search
        parameters, including the required authentication bits."""
        time = datetime.now().replace(microsecond=0).isoformat()
        unique = "".join(random.choice(string.letters + string.digits)
                         for _ in range(16))
        hash = sha1(self.caller_id + time + self.key + unique).hexdigest()
        params.update(callerId=self.caller_id, time=time, unique=unique,
                      hash=hash, format="json")
        return self.base_url + area + "?" + smart_urlencode(params)


class Listing(object):
    def __init__(self, data):
        self._json_data, data = data, dict(flatten(data))
        for attr, data_key in _fields.items():
            convert = _field_types.get(attr, html_decode)
            setattr(self, attr, convert(data.get(data_key, "")))

    @property
    def rooms_as_text(self):
        return ("%d" if self.rooms.is_integer() else "%.1f") % (self.rooms,)

    def __repr__(self):
        return "<%s.%s #%r>" % (__name__, self.__class__.__name__, self.id,)

