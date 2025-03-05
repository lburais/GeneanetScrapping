# objects
#
# Copyright (C) 2025  Laurent Burais
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the Affero GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#

"""
Package with genealogy objects
"""

# pylint: disable=C0112,C0116

import requests

# https://pypi.org/project/babel/
# pip3 install babel
import babel
import babel.dates

# https://pypi.org/project/pycountry/
# pip3 install pycountry
import pycountry

from common import display

# --------------------------------------------------------------------------------------------------
#
# _object class
#
# --------------------------------------------------------------------------------------------------


class _object(dict):

    def __init__(self, defaults, *args, **kwargs):
        super().__init__(defaults, *args, **kwargs)

    def __setitem__(self, key, value):
        if key not in self.keys():
            display(f"Object new key [{key}] with value [{value}]", error=True)
        super().__setitem__(key, value)

    def __setattr__(self, key, value):
        self[key] = value

    def __getattr__(self, key):
        return self.get(key, None)

    def __contains__(self, item):
        return hasattr(self, item) and not getattr(self, item, None) is None

# --------------------------------------------------------------------------------------------------
#
# Informations class
#
# --------------------------------------------------------------------------------------------------


class Informations(_object):
    """
    Informations
    """

    def __init__(self, *args, **kwargs):
        defaults = {
            'url': None,
            'author': None,
            'nbindividuals': 0,
            'lastchange': None,
            'source': None
        }

        super().__init__(defaults, *args, **kwargs)

# --------------------------------------------------------------------------------------------------
#
# Place class
#
# --------------------------------------------------------------------------------------------------


class Place(_object):
    """
    Place
    """

    def __init__(self, where, *args, **kwargs):
        defaults = {
            'name': where,
            'search': None,
            'fullname': where,
        }

        try:
            # Nomatim
            # https://nominatim.org
            # https://nominatim.org/release-docs/develop/api/Search/
            nominatim_url = "https://nominatim.openstreetmap.org/search"

            defaults_search = {
                'format': 'json',
                'limit': 10,
                'addressdetails': 1,
                'extratags': 1,
                'layer': 'address',
            }

            # try first structured query

            # if last element is a country (ISO code exist)
            if pycountry.countries.get(name=where.split(',')[-1].strip()):
                defaults_search['country'] = where.split(',')[-1].strip()

                # first one is the city (if not a country)
                if where.split(',')[0].strip() != defaults_search['country']:
                    defaults_search['city'] = where.split(',')[0].strip()
            else:
                defaults_search['q'] = where

            defaults['search'] = defaults_search

            headers = {
                'User-Agent': 'genealogy-scapper/1.0',
                'Accept-Language': 'fr',
            }

            response = requests.get(nominatim_url, headers=headers, params=defaults['search'], timeout=10)

            if response.status_code == 200:
                if len(response.json()) > 0:

                    for loc in response.json():
                        display(f"[{response.json().index(loc):2d}] {loc['addresstype']}: {loc['type']}: {loc['display_name']}")

                    defaults['fullname'] = response.json()[0]['display_name']
                    defaults['latitude'] = response.json()[0]['lat']
                    defaults['longitude'] = response.json()[0]['lon']
                    defaults['addresstype'] = response.json()[0]['addresstype']
                    defaults['address'] = response.json()[0]['address']
                    if 'wikidata' in response.json()[0]['extratags']:
                        defaults['wikidata'] = f"https://www.wikidata.org/wiki/{response.json()[0]['extratags']['wikidata']}"
                    if 'wikipedia' in response.json()[0]['extratags']:
                        defaults['wikipedia'] = f"https://fr.wikipedia.org/wiki/{response.json()[0]['extratags']['wikipedia']}"
                    if 'website' in response.json()[0]['extratags']:
                        defaults['website'] = response.json()[0]['extratags']['website']

            else:
                display(f'!! Nominatim cannot fetch data for ({where}) [{response.status_code}]: {response.text}')

            # place.featureType = 'suburb'
        except Exception as e:
            display(f"get place - {where}: {type(e).__name__}", error=True)

        super().__init__(defaults, *args, **kwargs)

# --------------------------------------------------------------------------------------------------
#
# Data class
#
# --------------------------------------------------------------------------------------------------


class Data(_object):
    """
    Data
    """

    def __init__(self, family, *args, **kwargs):
        if family:
            defaults = {
                'gedcomid': None,
                'spousesid': [],
                'childsid': []
            }
            events = ['marriage', 'divorce']

        else:
            defaults = {
                'gedcomid': None,
                'url': None,
                'firstname': None,
                'lastname': None,
                'sex': None,
                'occupation': None,
                'notes': [],
                'familyid': None,
                'parentsid': [],
                'siblingsid': [],
                'familiesid': []
            }
            events = ['birth', 'death', 'baptem', 'burial']

        for event in events:
            defaults[f"{event}"] = defaults[f"{event}date"] = defaults[f"{event}place"] = None

        super().__init__(defaults, *args, **kwargs)

# --------------------------------------------------------------------------------------------------
#
# Individual class
#
# --------------------------------------------------------------------------------------------------


class Individual(_object):
    """
    Individual
    """

    def __init__(self, *args, **kwargs):
        defaults = {
            'ref': None,
            'data': Data(family=False),
            'parentsref': [],
            'siblingsref': [],
            'familiesref': [],
            'families': [],
        }

        super().__init__(defaults, *args, **kwargs)

# --------------------------------------------------------------------------------------------------
#
# Family class
#
# --------------------------------------------------------------------------------------------------


class Family(_object):
    """
    Family
    """

    def __init__(self, *args, **kwargs):
        defaults = {
            'spousesref': [],
            'data': Data(family=True),
            'childsref': [],
        }

        super().__init__(defaults, *args, **kwargs)

# --------------------------------------------------------------------------------------------------
#
# Date class
#
# --------------------------------------------------------------------------------------------------


class Date(str):
    """
    Date class
    """

    def __new__(cls, value):
        return super().__new__(cls, cls._convert_date(value))

    # -------------------------------------------------------------------------
    # _convert_date
    # -------------------------------------------------------------------------

    @classmethod
    def _convert_date(cls, datetab):
        """
        Function to convert a french date to GEDCOM compliant string date
        """

        convert = {
            'ca': 'ABT',
            'vers': 'ABT',
            'à propos': 'ABT',
            'estimé': 'EST',
            'après': 'AFT',
            'avant': 'BEF',
            'entre': 'BET',
            'et': 'AND'
        }

        try:
            if len(datetab) == 0:
                return None

            idx = 0

            # clean
            datetab = [v.strip() for v in datetab]

            # Assuming there is just a year and last element is the year

            if len(datetab) == 1 or datetab[0] == 'en':
                # avoid a potential month
                # if datetab[-1].isalpha():
                #     return datetab[-1][0:4]

                # avoid a potential , after the year
                # elif datetab[-1].isnumeric():
                if datetab[-1].isnumeric():
                    return datetab[-1][0:4]

            # Between date

            if datetab[0] == 'entre':
                try:
                    index = datetab.index("et")
                    return convert[datetab[0]] + " " + cls._convert_date(datetab[1:index]) + " " + convert[datetab[index]] + " " + cls._convert_date(datetab[index + 1:])
                except ValueError:
                    pass

            # Having prefix

            if datetab[0] in convert:
                return convert[datetab[0]] + " " + cls._convert_date(datetab[1:])

            # Skip 'le' prefix

            if datetab[0] == 'le':
                idx = 1

            # In case of french language remove the 'er' prefix

            if datetab[idx] == "1er":
                datetab[idx] = "1"

            months = dict(babel.dates.get_month_names(width='wide', locale='fr'))

            # Just month and year
            if datetab[idx].lower() in months.values():
                bd1 = "1" + " " + str(list(months.keys())[list(months.values()).index(datetab[idx])]) + " " + datetab[idx + 1][0:4]
                bd2 = babel.dates.parse_date(bd1, locale='fr')
                return bd2.strftime("%b %Y").upper()

            try:
                # day month year
                bd1 = datetab[idx] + " " + str(list(months.keys())[list(months.values()).index(datetab[idx + 1])]) + " " + datetab[idx + 2][0:4]
                bd2 = babel.dates.parse_date(bd1, locale='fr')
            except ValueError:
                # day monthnum year
                bd1 = datetab[idx] + " " + datetab[idx + 1] + " " + datetab[idx + 2][0:4]
                bd2 = babel.dates.parse_date(bd1, locale='fr')
            except IndexError:
                pass
            except Exception as e:
                display(f"Convert date: {type(e).__name__}", error=True)

            return bd2.strftime("%d %b %Y").upper()

        except Exception as e:
            display(f"Date error ({type(e).__name__}): {' '.join(datetab)}", error=True)
            raise ValueError from e
