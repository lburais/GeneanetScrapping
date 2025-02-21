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

from common import *
# from geneanet import Geneanet
from genealogy import GFamily, GPerson, GPersons

#-------------------------------------------------------------------------
#
# Used Python Modules
#
#-------------------------------------------------------------------------

import os
import time
import io
import sys
import re
import uuid
import random
import argparse
import json
from datetime import datetime
from pathlib import Path
import subprocess
import base64


#-------------------------------------------------------------------------
#
# Global variables
#
#-------------------------------------------------------------------------

ICLOUD_PATH = "."

#-------------------------------------------------------------------------
#
# Web Scrapping
#
#-------------------------------------------------------------------------


###################################################################################################################################
# genealogyscrapping
###################################################################################################################################

def genealogyscrapping( person, ascendants=False, descendants=False, spouses=False, max_levels= 0, force=False, gedcom_file=None):

    try:
        persons = GPersons( max_levels, ascendants, spouses, descendants )
        persons.add_person( person, force )

        if gedcom_file:
            gedcom_file.write_text( persons.gedcom( force ) )

            try:
                import pygedcom

                parser = pygedcom.GedcomParser( str(gedcom_file) )
                parser.parse()
                check = parser.verify()

                display("")
                if check['status'] == 'ok':
                    display(parser.get_stats(), title="Your %s file is valid"%(str(gedcom_file)))
                else:
                    display( check['message'], title="Your %s file is not valid"%(str(gedcom_file)))

            except:
                pass

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        message = f'Something went wrong with scrapping [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
        display( message, error=True )

    return persons

###################################################################################################################################
# main
###################################################################################################################################

def main():

    console_clear()

    display( "GenealogyScrapping", level=1 )

    # Create data folder

    ICLOUD_PATH = get_folder()

    # Process parameters

    parser = argparse.ArgumentParser(description="Export genealogy subtrees into GEDCOM file")
    parser.add_argument("-a", "--ascendants", default=False, action='store_true', help="Includes ascendants (off by default)")
    parser.add_argument("-d", "--descendants", default=False, action='store_true', help="Includes descendants (off by default)")
    parser.add_argument("-s", "--spouses", default=False, action='store_true', help="Includes all spouses (off by default)")
    parser.add_argument("-l", "--level", default=0, type=int, help="Number of level to explore (0 by default)")
    parser.add_argument("-f", "--force", default=False, action='store_true', help="Force preloading web page (off by default)")
    parser.add_argument("searchedperson", type=str, nargs='?', help="Url of the person to search in Geneanet")
    args = parser.parse_args()

    force = args.force
    ascendants = args.ascendants
    descendants = args.descendants
    spouses = args.spouses
    max_levels = args.level

    if max_levels == None:
        max_levels = 0

    if args.searchedperson == None:

        searchedpersons = [
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
        searchedpersons = [ args.searchedperson ]

    params = {
        'force' : force,
        'ascendants' : ascendants,
        'descendants' : descendants,
        'spouses' : spouses,
        'max_levels' : max_levels,
        'searchedpersons' : searchedpersons
    }
    display( params, title="Paramùeters")

    # Process searched persons

    for searchedperson in searchedpersons:

        userid = re.sub( r'^/', '', urllib.parse.urlparse(searchedperson).path )

        # disable screenlock

        process= subprocess.Popen(["caffeinate", "-d"])

        # Scrap geneanet

        gedcom = ICLOUD_PATH / "gedcom" / f"{userid}.ged"
        gedcom.parent.mkdir(parents=True, exist_ok=True)
        gedcom.unlink(missing_ok=True)

        persons = genealogyscrapping( searchedperson, ascendants, descendants, spouses, max_levels, force, gedcom )

        # enable screenlock

        process.terminate()

        # Save logs

        display( "" )

        #output_file = ICLOUD_PATH / "output" / f"{userid}_logs_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.txt"
        output_file = ICLOUD_PATH / "output" / f"{userid}_logs.txt"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.unlink(missing_ok=True)
        output_file.write_text(console.export_text())  # Saves formatted text output

        # Save outcome
        
        console_flush()

        persons.print()

        output_file = ICLOUD_PATH / "output" / f"{userid}_console.txt"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.unlink(missing_ok=True)
        output_file.write_text(console_text())

if __name__ == '__main__':
    main()

