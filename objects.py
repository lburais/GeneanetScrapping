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

from common import display

class _object(dict):

    def __init__(self, defaults, *args, **kwargs):
        super().__init__( defaults, *args, **kwargs)

    def __setitem__(self, key, value):
        if not key in self.keys():
            display( f"Object new key [{key}] with value [{value}]", error=True)
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
    Object 
    """

    def __init__(self, *args, **kwargs):
        defaults = {
            'url': None,
            'author': None,
            'nbindividuals': 0,
            'lastchange': None,
            'source': None
        }

        super().__init__( defaults, *args, **kwargs)

# --------------------------------------------------------------------------------------------------
#
# Place class
#
# --------------------------------------------------------------------------------------------------

class Place(_object):
    """
    Object 
    """

    def __init__(self, *args, **kwargs):
        defaults = {
            'name': None,
            'latitude': None,
            'longitude': None,
        }

        super().__init__( defaults, *args, **kwargs)

# --------------------------------------------------------------------------------------------------
#
# Data class
#
# --------------------------------------------------------------------------------------------------

class Data(_object):
    """
    Object 
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
            defaults[ f"{event}" ] = defaults[ f"{event}date" ] = defaults[ f"{event}place" ] = None

        super().__init__( defaults, *args, **kwargs)

# --------------------------------------------------------------------------------------------------
#
# Individual class
#
# --------------------------------------------------------------------------------------------------

class Individual(_object):
    """
    Object 
    """

    def __init__(self, *args, **kwargs):
        defaults = {
            'ref': None,
            'data': Data( family=False ),
            'parentsref': [],
            'siblingsref': [],
            'familiesref': [],
            'families': [],
        }

        super().__init__( defaults, *args, **kwargs)

# --------------------------------------------------------------------------------------------------
#
# Family class
#
# --------------------------------------------------------------------------------------------------

class Family(_object):
    """
    Object 
    """

    def __init__(self, *args, **kwargs):
        defaults = {
            'spousesref': [],
            'data': Data( family=True ),
            'childsref': [],
        }

        super().__init__( defaults, *args, **kwargs)
