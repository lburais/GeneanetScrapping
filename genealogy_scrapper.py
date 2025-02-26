# GenealogyScrapping
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
Genealogy Scrapping
"""

# -------------------------------------------------------------------------
#
# Standard Python Modules
#
# -------------------------------------------------------------------------

import os
import sys
import re
import argparse
import subprocess
import urllib

import pygedcom

# -------------------------------------------------------------------------
#
# Internal Python Modules
#
# -------------------------------------------------------------------------

from common import display, console_save, get_folder
from genealogy import Genealogy

# -------------------------------------------------------------------------
#
# genealogy_scrapping
#
# -------------------------------------------------------------------------

def genealogy_scrapping( individuals, ascendants=False, descendants=False, spouses=False, max_levels= 0, force=False, one=False):
    """
    Main function to start processing of genealogy
    """

    genealogy = None

    # Create data folder

    root_folder = get_folder()

    # Process individuals

    for individual in individuals:

        if one:
            userid = None

            if  individual is individuals[0]:
                # first of all
                genealogy = Genealogy( max_levels, ascendants, spouses, descendants )

            elif individual is individuals[-1]:
                # last of all
                userid = 'geneanet'
        else:
            # each
            userid = re.sub( r'^/', '', urllib.parse.urlparse(individual).path )
            genealogy = Genealogy( max_levels, ascendants, spouses, descendants )

        # disable screenlock

        process = subprocess.Popen(["caffeinate", "-d"])

        # Scrap geneanet

        try:

            if genealogy:
                genealogy.add_individual( individual, force )

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            message = f'{e} with scrapping [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
            display( message, error=True )

        # enable screenlock

        process.terminate()


        if userid:

            # Process GEDCOM output

            gedcom = root_folder / "gedcom" / f"{userid}.ged"
            gedcom.parent.mkdir(parents=True, exist_ok=True)
            gedcom.unlink(missing_ok=True)

            gedcom.write_text( genealogy.gedcom( force ) )

            # Validate GEDCOM output

            parser = pygedcom.GedcomParser( str(gedcom) )
            parser.parse()
            check = parser.verify()

            display("")
            if check['status'] == 'ok':
                display( parser.get_stats(), title=f"Your {str(gedcom)} file is valid" )
            else:
                display( check['message'], title=f"Your {str(gedcom)} file is not valid" )

            # Save Rich output

            display( "" )

            console_save( root_folder / "output" / f"{userid}" )

            # Save outcome

            genealogy.print()

            display( genealogy.gedcom(), title="GEDCOM" )

            if len(individuals) == 1:
                display( genealogy.html(individuals[0]), title="HTML" )

            console_save( root_folder / "output" / f"{userid}_tree" )

###################################################################################################################################
# main
###################################################################################################################################

def main():
    """
    Main function to go by command line arguments and default setup
    """

    display( "Genealogy Scrapper", level=1 )

    # Process parameters

    parser = argparse.ArgumentParser(description="Export genealogy subtrees into GEDCOM file")
    parser.add_argument("-a", "--ascendants", default=False, action='store_true', help="Includes ascendants (off by default)")
    parser.add_argument("-d", "--descendants", default=False, action='store_true', help="Includes descendants (off by default)")
    parser.add_argument("-s", "--spouses", default=False, action='store_true', help="Includes all spouses (off by default)")
    parser.add_argument("-l", "--level", default=0, type=int, help="Number of level to explore (0 by default)")
    parser.add_argument("-f", "--force", default=False, action='store_true', help="Force preloading web page (off by default)")
    parser.add_argument("-o", "--one", default=False, action='store_true', help="All in one file (off by default)")
    parser.add_argument("searchedindividual", type=str, nargs='?', help="Url of the individual to search in Geneanet")
    args = parser.parse_args()

    force = args.force
    ascendants = args.ascendants
    descendants = args.descendants
    spouses = args.spouses
    max_levels = args.level
    one = args.one

    if max_levels is None:
        max_levels = 0

    if args.searchedindividual is None:

        searchedindividuals = [
            'https://gw.geneanet.org/lipari?p=leon+desire+louis&n=bessey',              # lipari - Léon Désiré Louis Bessey
            'https://gw.geneanet.org/asempey?n=jantieu&p=margueritte&oc=0',             # asempey - Marguerite Jantieu
            'https://gw.geneanet.org/iraird?p=nicholas&n=le+teuton',                    # iraird - Nicholas le Teuton
            'https://gw.geneanet.org/plongeur?p=charlotte+marie&n=postel',              # plongeur - Charlotte Marie Postel
            'https://gw.geneanet.org/sarahls?p=marcel+marius&n=lhomme',                 # sarahls - Marcel Marius Lhomme
            'https://gw.geneanet.org/balcaraz?n=stefani&oc=1&p=leonard',                # balcaraz - Léonard Stéphani
            'https://gw.geneanet.org/zeking?iz=2&p=6+2+leonard&n=stefani',              # zeking - Léonard Stéphani
            'https://gw.geneanet.org/sanso2b?p=romain+jean+michel&n=burais',            # sanso2b - Romain Jean Michel Burais
            'https://gw.geneanet.org/zlc061?p=marie+rose&n=cler&oc=1',                  # zlc061 - Marie Rose Cler
            'https://gw.geneanet.org/comrade28?iz=0&p=nicholas&n=de+bacqueville',       # comrade28 - Nicholas de Bacqueville
            'https://gw.geneanet.org/12marcel?p=marie+rose&n=cler',                     # 12marcel - Marie Rose Cler
            'https://gw.geneanet.org/pierreb0142?p=desire+antonin&n=bessey',            # pierre0142 - Désiré Antonin Bessey
            'https://gw.geneanet.org/lburais_w?p=milo&n=x&oc=1125',                       # lburais - Milo
            # 'https://gw.geneanet.org/alandur',                                        # alandur
            # 'https://gw.geneanet.org/domale',                                         # domale
            # 'https://gw.geneanet.org/malugi',                                         # malugi
        ]

    else:
        searchedindividuals = [ args.searchedindividual ]

    params = {
        'one' : one,
        'force' : force,
        'ascendants' : ascendants,
        'descendants' : descendants,
        'spouses' : spouses,
        'max_levels' : max_levels,
        'searchedindividuals' : searchedindividuals
    }
    display( params, title="Parameters")

    genealogy_scrapping( searchedindividuals, ascendants, descendants, spouses, max_levels, force, one )

if __name__ == '__main__':
    main()
