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
            'search': where.split(',')[0].strip() + f", {where.split(',')[-1].strip()}" if len(where.split(',')) > 1 else '',
            'fullname': where,
        }

        try:
            nominatim_url = "https://nominatim.openstreetmap.org/search"

            params = {
                # 'q': defaults['search'],
                'country': where.split(',')[-1].strip(),
                'format': 'json',
                'limit': 10,
                'addressdetails': 1,
                'extratags': 1,
                'layer': 'address',
            }
            if len(where.split(',')) > 1:
                params['city'] = where.split(',')[0].strip()
            headers = {
                'User-Agent': 'genealogy-scapper/1.0',
                'Accept-Language': 'fr',
            }

            response = requests.get(nominatim_url, headers=headers, params=params, timeout=10)

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
