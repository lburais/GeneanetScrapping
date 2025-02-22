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

from common import display, convert_to_rtf, console_clear, console_flush, console_text, get_folder
from genealogy import Genealogy

# -------------------------------------------------------------------------
#
# genealogy_scrapping
#
# -------------------------------------------------------------------------

def genealogy_scrapping( individual, ascendants=False, descendants=False, spouses=False, max_levels= 0, force=False, gedcom_file=None):
    """
    Main function to start processing of genealogy
    """

    try:
        genealogy = Genealogy( max_levels, ascendants, spouses, descendants )
        genealogy.add_individual( individual, force )

        if gedcom_file:
            gedcom_file.write_text( genealogy.gedcom( force ) )

        parser = pygedcom.GedcomParser( str(gedcom_file) )
        parser.parse()
        check = parser.verify()

        display("")
        if check['status'] == 'ok':
            display( parser.get_stats(), title=f"Your {str(gedcom_file)} file is valid" )
        else:
            display( check['message'], title=f"Your {str(gedcom_file)} file is not valid" )

    except Exception:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        message = f'Something went wrong with scrapping [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
        display( message, error=True )

    return genealogy

###################################################################################################################################
# main
###################################################################################################################################

def main():
    """
    Main function to go by command line arguments and default setup
    """

    console_clear()

    display( "Genealogy Scrapper", level=1 )

    # Create data folder

    root_folder = get_folder()

    # Process parameters

    parser = argparse.ArgumentParser(description="Export genealogy subtrees into GEDCOM file")
    parser.add_argument("-a", "--ascendants", default=False, action='store_true', help="Includes ascendants (off by default)")
    parser.add_argument("-d", "--descendants", default=False, action='store_true', help="Includes descendants (off by default)")
    parser.add_argument("-s", "--spouses", default=False, action='store_true', help="Includes all spouses (off by default)")
    parser.add_argument("-l", "--level", default=0, type=int, help="Number of level to explore (0 by default)")
    parser.add_argument("-f", "--force", default=False, action='store_true', help="Force preloading web page (off by default)")
    parser.add_argument("searchedindividual", type=str, nargs='?', help="Url of the individual to search in Geneanet")
    args = parser.parse_args()

    force = args.force
    ascendants = args.ascendants
    descendants = args.descendants
    spouses = args.spouses
    max_levels = args.level

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
        'force' : force,
        'ascendants' : ascendants,
        'descendants' : descendants,
        'spouses' : spouses,
        'max_levels' : max_levels,
        'searchedindividuals' : searchedindividuals
    }
    display( params, title="Paramùeters")

    # Process searched genealogy

    for searchedindividual in searchedindividuals:

        userid = re.sub( r'^/', '', urllib.parse.urlparse(searchedindividual).path )

        # disable screenlock

        process = subprocess.Popen(["caffeinate", "-d"])

        # Scrap geneanet

        gedcom = root_folder / "gedcom" / f"{userid}.ged"
        gedcom.parent.mkdir(parents=True, exist_ok=True)
        gedcom.unlink(missing_ok=True)

        genealogy = genealogy_scrapping( searchedindividual, ascendants, descendants, spouses, max_levels, force, gedcom )

        # enable screenlock

        process.terminate()

        # Save logs

        display( "" )

        output_file = root_folder / "output" / f"{userid}_logs.rtf"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.unlink(missing_ok=True)
        output_file.write_text(convert_to_rtf(console_text()))  # Saves formatted text output

        # Save outcome

        console_flush()

        genealogy.print()

        display( genealogy.gedcom(), title="GEDCOM" )

        if len(searchedindividuals) == 1:
            display( genealogy.html(searchedindividuals[0]), title="HTML" )

        # display( f"python3 genealogy_scrapper.py -l 0", title="COMMAND")

        output_file = root_folder / "output" / f"{userid}_console.rtf"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.unlink(missing_ok=True)
        output_file.write_text(convert_to_rtf(console_text()))

if __name__ == '__main__':
    main()
