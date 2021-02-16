#!/usr/bin/env python3

import sys
import re
from decimal import Decimal

import bs4
import requests

# Storing some constants to improve readability in the code
BASE_URL = "https://money.cnn.com/quote/forecast/forecast.html?symb="

# re.compile isn't necessary for any performance reasons, since it's only being run once,
#  but this will also improve readability in the code
PATTERN = re.compile(
    pattern=r"The \d.* analysts offering 12-month price forecasts for .* have a median target of (?P<median>\d*\.\d{2})"
    r" with a high estimate of (?P<high>\d*\.\d{2}) and a low estimate of (?P<low>\d*\.\d{2}). The median estimate"
    r" represents a .*% (?:in|de)crease from the last price of (?P<current>\d*\.\d{2})\."
)


class InvalidSymbolError(Exception):
    """An exception that the supplied symbol is invalid."""

    pass


class NetworkError(Exception):
    """An exception that the network request could not be completed, due to not finding the page, timeout, etc."""

    pass


class ParsingError(Exception):
    """An exception for when the page cannot be parsed, due to the page layout changing, data missing, etc."""

    pass


def fetch(symbol: str, url: str = BASE_URL) -> str:
    """Fetch the website, using the `BASE_URL` and supplied `symbol` and check for a successful status code.
    Otherwise error out.

    >>> type(fetch(symbol="AAPL"))
    <class 'str'>

    >>> len(fetch(symbol="GME")) > 0
    True

    >>> fetch(symbol="")
    Traceback (most recent call last):
        ...
    InvalidSymbolError: The symbol must contain at least one character

    >>> fetch(symbol="TSLA", url="https://httpstat.us/500?")
    Traceback (most recent call last):
        ...
    NetworkError: The page could not be loaded. (Error: 500 - Reason: Internal Server Error)

    >>> fetch(symbol="T", url="https://money.cnn.com/quote/THISPAGEDOESNOTEXIST/forecast.html?symb=")
    Traceback (most recent call last):
        ...
    NetworkError: The page could not be loaded. (Error: 404 - Reason: Not Found)

    """
    if symbol == "":
        raise InvalidSymbolError(f"The symbol must contain at least one character")

    webpage = requests.get(url=f"{url}{symbol}")

    if webpage.status_code == 200:
        return webpage.text

    else:
        raise NetworkError(f"The page could not be loaded. (Error: {webpage.status_code} - Reason: {webpage.reason})")


def parse(page: str) -> tuple:
    """Load the webpage into a BeautifulSoup object and look for headings. If the heading is not 'symbol not found', it
    appears to be a company name, so look for all the paragraphs in the Forecasts tab.

    The first time the `get_prices` function returns a non-`False` result is when the prices have been matched;
    return those. Otherwise error out.


    >>> valid_page = fetch(symbol="T") # Load the AT&T stock symbol
    >>> type(parse(page = valid_page))
    <class 'tuple'>

    >>> len(parse(page = valid_page)) > 0
    True

    >>> symbol_not_found = fetch(symbol="1") # A single integer is not a valid stock symbol
    >>> parse(page = symbol_not_found)
    Traceback (most recent call last):
        ...
    InvalidSymbolError: The symbol could not be found

    >>> completely_invalid_page = fetch(symbol="T", url="https://www.cnn.com?")
    >>> parse(page = completely_invalid_page)
    Traceback (most recent call last):
        ...
    ParsingError: An error occurred while attempting to parse this page.

    """
    soup = bs4.BeautifulSoup(markup=page, features="html.parser")

    headings = (h1.text.lower() for h1 in soup.find_all("h1"))

    if "symbol not found" in headings:
        raise InvalidSymbolError(f"The symbol could not be found")

    else:
        tab = soup.find(id="wsod_forecasts")

        if tab != None:
            elements = tab.find_all("p")

            return tuple(elements)

    raise ParsingError("An error occurred while attempting to parse this page.")


def get_prices(items: tuple) -> dict:
    """Use regex to match the paragraphs to the expected format. The string replacement is used to remove commas,
    used as thousands delimiters.

    Some pages will have "no forecast data available", so raise the invalid symbol for that instance. If no results
    can be matched in the paragraph, return `False`. Otherwise, return a dictionary with the prices (as Decimals)

    >>> valid_page = fetch(symbol="T"); elements = parse(page = valid_page) # Load AT&T and extract paragraph elements
    >>> type(get_prices(items=elements))
    <class 'dict'>
    >>> type(get_prices(items=elements)["current"])
    <class 'decimal.Decimal'>

    >>> no_forecast = fetch(symbol="ATC"); elements = parse(page = no_forecast) # ATC loads, but has no forecasts
    >>> get_prices(items=elements)
    Traceback (most recent call last):
        ...
    InvalidSymbolError: This symbol does not have any forecast data
    """
    for item in items:
        paragraph = item.text.replace(",", "")

        match = re.match(pattern=PATTERN, string=paragraph)

        if match != None and set((quotes := match.groupdict()).keys()) == {"current", "high", "median", "low"}:
            return {key: Decimal(value) for key, value in quotes.items()}

        elif paragraph.lower() == "there is no forecast data available.":
            raise InvalidSymbolError("This symbol does not have any forecast data")

        else:
            return False


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("RUNNING TESTS")

        import doctest

        doctest.testmod()

        symbol = "gme"

    else:
        symbol = sys.argv[1]

    print(f"Getting {symbol.upper()} stock forecast")

    webpage = fetch(symbol=symbol)
    elements = parse(page=webpage)
    prices = get_prices(items=elements)

    print(prices)
