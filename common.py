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

#-------------------------------------------------------------------------
#
# Used Python Modules
#
#-------------------------------------------------------------------------

import urllib
from pathlib import Path
import babel, babel.dates

#-------------------------------------------------------------------------
#
# Date functions
#
#-------------------------------------------------------------------------

def convert_date(datetab):
    ''' Convert the french date format for birth/death/married lines
    into an ISO date format
    '''

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
            return(None)

        idx = 0

        # Assuming there is just a year and last element is the year

        if len(datetab) == 1 or datetab[0] == 'en':
            # avoid a potential month
            if datetab[-1].isalpha():
                return(datetab[-1][0:4])

            # avoid a potential , after the year
            elif datetab[-1].isnumeric():
                return(datetab[-1][0:4])

        # Between date

        if datetab[0] == 'entre':
            try:
                index = datetab.index("et")
                return(convert[datetab[0]]+" "+convert_date(datetab[1:index])+" "+convert[datetab[index]]+" "+convert_date(datetab[index+1:]))
            except ValueError:
                pass

        # Having prefix

        if datetab[0] in list(convert.keys()):
            return(convert[datetab[0]]+" "+convert_date(datetab[1:]))

        # Skip 'le' prefix

        if datetab[0] == 'le':
            idx = 1

        # In case of french language remove the 'er' prefix

        if datetab[idx] == "1er":
            datetab[idx] = "1"

        months = dict(babel.dates.get_month_names(width='wide', locale='fr'))

        try:
            # day month year
            bd1 = datetab[idx]+" "+str(list(months.keys())[list(months.values()).index(datetab[idx+1])])+" "+datetab[idx+2][0:4]
            bd2 = babel.dates.parse_date(bd1, locale='fr')
        except:
            # day monthnum year 
            bd1 = datetab[idx]+" "+datetab[idx+1]+" "+datetab[idx+2][0:4]
            bd2 = babel.dates.parse_date(bd1, locale='fr')

        return(bd2.strftime("%d %b %Y").upper())
    except:
        display( "Date error: %s"%(' '.join(datetab)), error=True )
        return(None)

#-------------------------------------------------------------------------
#
# Generic functions
#
#-------------------------------------------------------------------------

def clean_query( url ):
    queries = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if len(queries) > 0:
        queries_to_keep = [ 'm', 'v', 'p', 'n', 'oc', 'i' ]

        removed_queries = {k: v for k, v in queries.items() if k not in queries_to_keep + ['lang', 'pz', 'nz', 'iz']}
        if len(removed_queries) > 0:
            display( "Removed queries: %s"%(removed_queries) )

        if 'n' not in queries:
            queries['n'] = ""

        if 'p' not in queries:
            queries['p'] = ""

        return urllib.parse.urlencode({k: v for k, v in queries.items() if k in queries_to_keep}, doseq=True)
    else:
        return url

def event( obj, tag, date, place ): 
    text = ""
    if isinstance( obj, dict ):
        data = obj
    else:
        data = vars(obj)
    if date in data or place in data: # date in vars(obj)
        text = text + "1 %s\n"%(tag)
        if date in data:
            text = text + "2 DATE %s\n"%(data[date])
        if place in data:
            text = text + "2 PLAC %s\n"%(data[place])
    return text

def get_folder():
    folder = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "GeneanetScrap"
    folder.mkdir(exist_ok=True)
    return folder

#-------------------------------------------------------------------------
#
# Rich console
#
#-------------------------------------------------------------------------
# https://rich.readthedocs.io/en/stable/
# pip3 install rich

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.pretty import pprint
from rich.table import Table
from rich.prompt import Prompt
from rich.traceback import install
from rich.pretty import Pretty
from rich.theme import Theme

console = Console(record=True, width=132)

HEADER1 = 1
HEADER2 = 2
HEADER3 = 3

NL = '\n'

def display( what=None, title=None, level=0, error=False, exception=False ):
    """
    My function to display various type of objects
    """

    try:
        if isinstance( what, list ):
            pprint( what )

        elif isinstance( what, dict ):

            console.print( Panel( Pretty(what), title=title, title_align='left' ) )
                
        elif isinstance( what, str ):
            if exception:
                console.print_exception(show_locals=False, max_frames=1)

            elif error:
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

            #console.print( what.markup )
            console.print( what )
                
        elif what:
            pprint( what )

    except:
        console.print_exception(show_locals=False, max_frames=1)

def console_clear():
    console.clear()

def console_flush():
    console._record_buffer = []

def console_text():
    return console.export_text()