A simple and powerful python wrapper for the Booli.se API

# Setting up

    from booliapi import BooliAPI
    Booli = BooliAPI("your username", "your api key")

# Searching

`Booli.search()` performs a search and returns a list of `Listing`s.
Here's how you specify your search parameters:

## Searching by city and/or neighborhood

To search for listings in a given city or neighborhood, pass a string
as the first argument to `.search()`.

    Booli.search("Uppsala") # city

    Booli.search("Uppsala/Luthagen") # city + neighborhood

### Example: Printing a nice list of apartments in Uppsala's "Fålhagen" neighborhood.
    
    for listing in Booli.search("Uppsala/Fålhagen", typ=u"lägenhet"):
        print "%s, %s" % (listing.address, listing.neighborhood)
        print "  %s rum; %d kr, %d kr/mån" % (listing.rooms_as_text,
                                              listing.price,
                                              listing.fee)
    
Result:

    Hjalmar Brantingsgatan 9B, Fålhagen
      2 rum; 1490000 kr, 2710 kr/mån
    Torkelsgatan 8C, Fålhagen
      1 rum; 1075000 kr, 2563 kr/mån
    Petterslundsgatan 33, Fålhagen
      1 rum; 1050000 kr, 2032 kr/mån
    ...

## Listings within distance of a point

    # Listings within 1 km from Booli's Uppsala office
    listings = Booli.search(centerLat=59.8569131, centerLong=17.6359056, radius=1)

## More specific searching

Any keyword arguments you pass to `.search()` will simply be used as URL
parameters in the API query. Unicode strings, integers and floats are
converted to utf-8 strings first. Lists are joined into
comma-separated strings.

This means that any parameters you find in the [API documentation] are
also valid keyword arguments here.

[API Documentation]: http://www.booli.se/api/docs/

    Booli.search("Uppsala", pris="0-1500000", typ="lägenhet")
    Booli.search("Stockholm/Södermalm", rum=[1,2])
    Booli.search("Stockholm", typ=["villa", "radhus"], rum=4)

It also means that the names of these parameters are all Swedish. But
then again, so are you, probably. Puss på dig.


# Listings

The objects we're dealing with are called `Listing`s. The data about
each listing is stored as attributes.

**Basic data**

- `type` - what type of property this listing is for. "lägenhet", "villa", etc.
- `address` - the street address of the listed property
- `neighborhood` and `city` - exactly what you think
- `rooms` - number of rooms
- `size` - square meterage
- `lot_size` - size of the lot
- `price` - the listed sales price
- `fee` - monthly fee

*Note:* The number of rooms is actually a float, since some listings
 are specified as having for example 2.5 rooms. There is a special
 property called `rooms_as_text` that gives you a nicer string
 representation.

**Additional geographic data**

- `latitude` and `longitude`
- `municipality`
- `county`

**Metadata**

- `url` - the url to this listing on booli.se
- `image_url` - the url to a thumbnail image, if available
- `agency` - the name of the real estate agency representing the seller
- `created` - when this listing was created
- `id` - internal Booli ID


# Filtering, sorting and grouping

It's super-easy to filter and sort the listings.

The list you get from `.search()` is actually a clever subclass of
`list`, called `ResultSet`. If you're familiar with Django's QuerySet
API, you'll like this.

## Filtering

`ResultSet.filter(**kwargs)` and `ResultSet.exclude(**kwargs)`

The `filter()` method takes keyword arguments corresponding to the
attributes of `Listing` objects. It returns a new ResultSet containing
only those listings that match the specified parameters.

`exclude()` is the inverse of `filter()` - it returns a new ResultSet
containing listings that do *not* match the specified parameters.

If you specify multiple parameters, they are combined using boolean `and`.

One way to use these methods is to do more specific filtering than the
API itself supports.

    # Get only listings from a specific agency
    listings = Booli.search("Uppsala").filter(agency=u"Widerlöv & Co")

Another way is to work on different subsets of a search result without
having to make another API call.

    listings = Booli.search("Uppsala", typ=u"lägenhet")

    for listing in listings.filter(neighborhood=u"Fålhagen"):
        # do something

    for listing in listings.filter(neighborhood=u"Luthagen"):
        # do something else

Filtering ResultSets never affects the underlying API calls; it only
creates a filtered copy the results you've already fetched.

## Filter operators

Just as in Django's QuerySets, you can do more than just exact
matching. When you type `.filter(attr=value)`, it's actually
interpreted as `attr__exact=value`. You can use this
`attribute__operator` syntax to do pretty nifty things.

Here are the operators and their plain-python equivalents:

- `attr__exact=value` - `attr == value`
- `attr__lt=value` - `attr < value`
- `attr__lte=value` - `attr >= value`
- `attr__gt=value` - `attr > value`
- `attr__gte=value` - `attr >= value`
- `attr__in=value` - `attr in value`
- `attr__contains=value` - `value in attr`
- `attr__startswith=value` - `attr.startswith(value)`
- `attr__endswith=value`- `attr.endswith(value)`
- `attr__range=(start, end)` - `start <= attr <= end`

There's also `iexact`, `icontains`, `istartswith` and `iendswith`,
which are case-insensitive variants of their i-less buddies.

### Example: Finding all apartments on a specific street in Uppsala

    apts = Booli.search("Uppsala", typ=u"lägenhet")

    apts.filter(address__startswith="Storgatan")

### Example: Getting listings in any of several neighborhoods

    apts.filter(neighborhood__in=[u"Luthagen", u"Centrum"])

### Example: Getting listings from one agency, excluding a neighborhood

    apts.filter(agency=u"Riksmäklaren").exclude(neighborhood=u"Sävja")

### Example: Getting listings published in the last 8 hours

    from datetime import datetime, timedelta
    eight_hours_ago = datetime.now() - timedelta(hours=8)

    for listing in apts.filter(created__gt=eight_hours_ago)
        # do something

## Sorting

`ResultSet.order_by(*attributes)`

`order_by()` takes one or more strings that specify which attributes
to sort by. It returns a new ResultSet.

    # Sort by address
    apts.order_by("address")

    # Sort by price, descending (most expensive first)
    apts.order_by("-price")

    # Sort by neighborhood first, then by price descending
    apts.order_by("neighborhood", "-price")


## Grouping

`ResultSet.group_by(attribute, [count_only=False])`

`group_by()` groups the listings by the provided attribute. It does
not return a ResultSet, but rather a list of (grouper, resultset)
tuples, where `grouper` is the value of the procided attribute for
each group.

If `count_only` is true, the returned list contains the length of each
group's resultset instead of the actual resultset.

In almost all cases, you should sort your resultset before grouping.

### Example: Top 5 Agencies in Södermalm, Stockholm

    results = Booli.search("Stockholm/Södermalm").order_by("broker").group_by("broker")
    results.sort(key=lambda x: len(x[1]), reverse=True)
    for broker, listings in results[:5]:
        print "%s (%d listings)" % (broker, len(listings))
    print
    other = sum(len(listings) for (broker, listings) in results[5:])
    print u"Other: %d listings" % (other,)

Result:

    Fastighetsbyrån (29 listings)
    Svensk Fastighetsförmedling (25 listings)
    Erik Olsson Fastighetsförmedling (17 listings)
    Södermäklarna (13 listings)
    Notar (12 listings)
    
    Other: 90 listings


## Complex filtering - Q and F objects

When you provide more than one parameter to `filter` or `exclude` they
are combined using boolean AND. If that's not good enough for you,
have a look at Q objects.

`Q(**kwargs)`

`Q` objects take the same kind of keyword arguments as `filter()`.
They can be combined using the `&` and `|` operators, and negated
using `~`. These operations yield new Q objects representing the
combined filter condition.

### Example: Finding apartments on any of several streets

    kungsgatan = Q(address__startswith="Kungsgatan")
    storgatan = Q(address__startswith="Storgatan")
    Booli.search("Uppsala").filter(kungsgatan | storgatan)

`F(attribute)`

If you want to use a listing attribute as the right-hand side in a
comparison, you have to use `F` objects.

### Example: Exploring the difference between City and Municipality in the data

    Booli.search("Uppsala").exclude(city=F("municipality"))

 `F` objects are very similar to `operator.attrgetter`, but with the
addition that they can be combined with other `F` objects as well as
with constants.

### Example: For rural living, try listings where the address is neighborhood + " "

(+ number, but we can't search for that)

    Booli.search("Uppsala").filter(address__startswith=F("neighborhood") + " ")

### Example: Grand living - finding a house where the lot is at least fifty times the size of the house

(avoiding those that oddly have size=0)

    Booli.search("Uppsala", typ="villa").exclude(size=0) \
        .filter(lot_size__gte=F("size")*50)

### Example: Filtering apartments that cost less than 25000/sqm

    Booli.search("Uppsala", typ=u"lägenhet").filter(price__lt=F("size")*25000)

