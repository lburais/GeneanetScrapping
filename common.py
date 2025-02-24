# common
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
Package with common elements
"""

# -------------------------------------------------------------------------
#
# Used Python Modules
#
# -------------------------------------------------------------------------

import urllib
from pathlib import Path
import babel
import babel.dates

# https://rich.readthedocs.io/en/stable/
# pip3 install rich

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.pretty import pprint
from rich.pretty import Pretty

# -------------------------------------------------------------------------
#
# convert_date
#
# -------------------------------------------------------------------------

def convert_date(datetab):
    """
    Function to convert a french date to GEDCOM date
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
        datetab = [ v.strip() for v in datetab ]

        # Assuming there is just a year and last element is the year

        if len(datetab) == 1 or datetab[0] == 'en':
            # avoid a potential month
            if datetab[-1].isalpha():
                return datetab[-1][0:4]

            # avoid a potential , after the year
            elif datetab[-1].isnumeric():
                return datetab[-1][0:4]

        # Between date

        if datetab[0] == 'entre':
            try:
                index = datetab.index("et")
                return convert[datetab[0]] + " " + convert_date(datetab[1:index]) + " " + convert[datetab[index]] + " " + convert_date(datetab[index+1:])
            except ValueError:
                pass

        # Having prefix

        if datetab[0] in convert:
            return convert[datetab[0]] + " " + convert_date(datetab[1:])

        # Skip 'le' prefix

        if datetab[0] == 'le':
            idx = 1

        # In case of french language remove the 'er' prefix

        if datetab[idx] == "1er":
            datetab[idx] = "1"

        months = dict(babel.dates.get_month_names(width='wide', locale='fr'))

        # Just month and year
        if datetab[idx].lower() in months.values():
            bd1 = "1" + " " + str(list(months.keys())[list(months.values()).index(datetab[idx])]) + " " + datetab[idx+1][0:4]
            bd2 = babel.dates.parse_date(bd1, locale='fr')
            return bd2.strftime("%b %Y").upper()

        try:
            # day month year
            bd1 = datetab[idx] + " " + str(list(months.keys())[list(months.values()).index(datetab[idx+1])]) + " " + datetab[idx+2][0:4]
            bd2 = babel.dates.parse_date(bd1, locale='fr')
        except ValueError:
            # day monthnum year
            bd1 = datetab[idx] + " " + datetab[idx+1] + " " + datetab[idx+2][0:4]
            bd2 = babel.dates.parse_date(bd1, locale='fr')
        except Exception as e:
            display( f"Convert date: {type(e).__name__}", error=True )

        return bd2.strftime("%d %b %Y").upper()

    except Exception as e:
        display( f"Date error ({type(e).__name__}): {' '.join(datetab)}", error=True )
        raise ValueError from e

# -------------------------------------------------------------------------
#
# clean_query
#
# -------------------------------------------------------------------------

def clean_query( url ):
    """
    Function to return the query part of an url without unnecessary geneanet queries
    """

    queries = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if len(queries) > 0:
        queries_to_keep = [ 'm', 'v', 'p', 'n', 'oc', 'i' ]

        removed_queries = {k: v for k, v in queries.items() if k not in queries_to_keep + ['lang', 'pz', 'nz', 'iz']}
        if len(removed_queries) > 0:
            display( f"Removed queries: {removed_queries}" )

        if 'n' not in queries:
            queries['n'] = ""

        if 'p' not in queries:
            queries['p'] = ""

        return urllib.parse.urlencode({k: v for k, v in queries.items() if k in queries_to_keep}, doseq=True)
    else:
        return url

# -------------------------------------------------------------------------
#
# get_folder
#
# -------------------------------------------------------------------------

def get_folder():
    """
    Function to get the home folder for output files
    """

    folder = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "GeneanetScrap"
    folder.mkdir(exist_ok=True)
    return folder

# -------------------------------------------------------------------------
#
# convert_to_rtf
#
# -------------------------------------------------------------------------

def convert_to_rtf( text ):
    """
    Function to convert text to rtf 
    """

    def ansi_to_rtf( text ):
        """Convert ANSI text to RTF-safe format."""
        converted_text = ''.join(f"\\u{ord(c)}?" if ord(c) > 127 else c for c in text)
        converted_text = converted_text.replace( "\n", "\\par ")

        return converted_text

    rtf_content = r"""{\rtf1\ansi\deff0
{\fonttbl{\f0\fnil\fcharset0 Courier New;}}
\viewkind4\uc1\pard\f0\fs24 %s \par
}""" % ansi_to_rtf( text )

    return rtf_content

# -------------------------------------------------------------------------
#
# Rich console
#
# -------------------------------------------------------------------------
console = Console(record=True, width=132)

HEADER1 = 1
HEADER2 = 2
HEADER3 = 3

NL = '\n'

def display( what=None, title=None, level=0, error=False, exception=False ):
    """
    Function to print with Rich console
    """

    try:
        if exception:
            console.print_exception(show_locals=False, max_frames=1)

        elif isinstance( what, list ):
            pprint( what )

        elif isinstance( what, dict ):

            console.print( Panel( Pretty(what), title=title, title_align='left' ) )

        elif isinstance( what, str ):
            if error:
                console.print( Text( what, style="white on red" ), NL)

            elif level == 1:
                console.print( Panel( Text(what.upper(), style="white"), style="white on cyan" ), NL)

            elif level > 1:
                console.print( Panel( Text(what), style="cyan" ), NL)

            elif title:
                console.print( Panel( Text(what), title=title ))

            else:
                console.print( Text(what) )

        elif isinstance( what, Markdown ):

            console.print( what )

        elif what:
            pprint( what )

    except Exception as e:
        display( f"Display: {type(e).__name__}", error=True )
        console.print_exception(show_locals=False, max_frames=1)

def console_clear():
    """
    Function to clear the Rich console
    """
    console.clear()


def console_flush():
    """
    Function to flush the Rich console
    """
    console._record_buffer = []


def console_text():
    """
    Function to retrieve text from Rich console
    """
    return console.export_text()
