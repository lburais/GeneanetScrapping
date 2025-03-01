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

# pylint: disable=C0112,C0116

from common import display

"""
Package with genealogy objects
"""

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
# Portrait class
#
# --------------------------------------------------------------------------------------------------

class Portrait(_object):
    """
    Object 
    """

    def __init__(self, *args, **kwargs):
        defaults = {
            'firstname': None,
            'lastname': None,
            'sex': None,
            'occupation': None,
            'notes': [],
        }

        events = ['birth', 'death', 'baptesm', 'burial']
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
            'gedcomid': None,
            'ref': None,
            'portrait': Portrait(),
            'familyid': None,
            'parentsref': [],
            'parentsid': [],
            'siblingsref': [],
            'siblingsid': [],
            'families': [],
            'familiesid': []
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
            'gedcomid': None,
            'spousesref': [],
            'spousesid': [],
            'childsref': [],
            'childsid': []
        }

        events = ['marriage', 'divorce']
        for event in events:
            defaults[ f"{event}" ] = defaults[ f"{event}date" ] = defaults[ f"{event}place" ] = None

        super().__init__( defaults, *args, **kwargs)
