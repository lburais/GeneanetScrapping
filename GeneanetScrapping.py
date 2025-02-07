# GeneanetScrapping
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
# forked file: https://github.com/romjerome/GeneanetForGramps/blob/master/GeneanetForGramps.py

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
import urllib
#from lxml import html, etree
import babel, babel.dates
from collections import namedtuple

#-------------------------------------------------------------------------
#
# Global variables
#
#-------------------------------------------------------------------------

verbosity = 0
force = False
ascendants = False
descendants = False
spouses = False
LEVEL = 2

ROOTURL = 'https://gw.geneanet.org/'

persons = {}

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

console = Console()

HEADER1 = 1
HEADER2 = 2
HEADER3 = 3

NL = '\n'

def display( what=None, title=None, level=0, verbose=0, error=False, exception=False ):
    """
    My function to display various type of objects
    """

    global verbosity

    try:
        if isinstance( what, list ):
            pprint( what )

        elif isinstance( what, dict ):

            console.print( Panel( Pretty(what), title=title, title_align='left' ) )
                
        elif isinstance( what, str ):
            if exception:
                console.print_exception(show_locals=False, max_frames=1)

            elif error:
                if verbose <= verbosity:
                    console.print( Text( what, style="white on red" ), NL)

            elif level == 1:
                console.print( Panel( Text(what.upper(), style="white"), style="white on cyan" ), NL)

            elif level > 1:
                console.print( Panel( Text(what), style="cyan" ), NL)

            elif verbose <= verbosity:
                console.print( Text(what) )

        elif what:
            pprint( what )

    except:
        console.print_exception(show_locals=False, max_frames=1)

#-------------------------------------------------------------------------
#
# Translations
#
#-------------------------------------------------------------------------
# pip3 install Babel
# pip3 install potranslator
# pip3 install googletrans==3.1.0a0
"""
pybabel extract GeneanetScrapping.py -o locales/base.pot
rm locales/*/*/base.po
potranslator build -l fr
"""

import gettext
locale = 'fr'
translation = gettext.translation('base', localedir='locales', languages=[locale])
translation.install()
_ = translation.gettext


#-------------------------------------------------------------------------
#
# Web Scrapping
#
#-------------------------------------------------------------------------

from bs4 import BeautifulSoup
from bs4 import Comment, NavigableString

#-------------------------------------------------------------------------
#
# Other Python Modules
#
#-------------------------------------------------------------------------

import gedcom

#-------------------------------------------------------------------------
#
# Generic functions
#
#-------------------------------------------------------------------------

def format_ca(date):
    """
    Change the 'ca' chain into the 'vers' chain for now in Geneanet analysis
    """
    # If ca for an about date, replace with vers (for now)
    if date[0:2] == "ca":
        date = _("about")+date[2:]
    return(date)

def format_year(date):
    """
    Remove potential empty month/day coming from Gramps (00)
    """
    if not date:
        return(date)
    if (date[-6:] == "-00-00"):
        return(date[0:-6])
    else:
        return(date)

def format_iso(date_tuple):
    """
    Format an iso date.
    """
    year, month, day = date_tuple
    # Format with a leading 0 if needed
    month = str(month).zfill(2)
    day = str(day).zfill(2)
    if year == None or year == 0:
       iso_date = ''
    elif month == None or month == 0:
       iso_date = str(year)
    elif day == None or day == 0:
        iso_date = '%s-%s' % (year, month)
    else:
        iso_date = '%s-%s-%s' % (year, month, day)
    return iso_date

def format_noniso(date_tuple):
    """
    Format an non-iso tuple into an iso date
    """
    day, month, year = date_tuple
    return(format_iso(year, month, day))

def convert_date(datetab):
    ''' Convert the Geneanet date format for birth/death/married lines
    into an ISO date format
    '''

    if verbosity >= 3:
        print("datetab reçu :",datetab)

    if len(datetab) == 0:
        return(None)

    idx = 0
    if datetab[0] == 'en':
        # avoid a potential month
        if datetab[1].isalpha():
            return(datetab[2][0:4])

        # avoid a potential , after the year
        elif datetab[1].isnumeric():
            return(datetab[1][0:4])

    if (datetab[0][0:2] == "à propos"[0:2] or datetab[0][0:2] ==  "après"[0:2] or datetab[0][0:2] ==  "avant"[0:2]) and (len(datetab) == 2):
        return(datetab[0]+" "+datetab[1][0:4])

    # In case of french language remove the 'le' prefix
    if datetab[0] == 'le':
        idx = 1

    # In case of french language remove the 'er' prefix
    if datetab[idx] == "1er":
        datetab[idx] = "1"

    months = dict(babel.dates.get_month_names(width='wide', locale=locale))

    try:
        # day month year
        bd1 = datetab[idx]+" "+str(list(months.keys())[list(months.values()).index(datetab[idx+1])])+" "+datetab[idx+2][0:4]
        bd2 = babel.dates.parse_date(bd1, locale=locale)
    except:
        # month day, year
        bd1 = str(list(months.keys())[list(months.values()).index(datetab[idx])])+" "+datetab[idx+1]+" "+datetab[idx+2][0:4]
        bd2 = babel.dates.parse_date(bd1, locale=locale)
    return(bd2.strftime("%Y-%m-%d"))

def clean_ref( ref ):

    queries = urllib.parse.parse_qs(urllib.parse.urlparse(ref).query)
    queries_to_keep = [ 'nz', 'pz', 'm', 'v', 'p', 'n', 'oc' ]

    removed_queries = {k: v for k, v in queries.items() if k not in queries_to_keep + ['lang']}
    if len(removed_queries) > 0:
        display( "Removed queries: %s"%(removed_queries) )

    return re.sub( r'^/', '', urllib.parse.urlparse(ref).path ) + "?" + urllib.parse.urlencode({k: v for k, v in queries.items() if k != 'lang'}, doseq=True)
    return re.sub( r'^/', '', urllib.parse.urlparse(ref).path ) + "?" + urllib.parse.urlencode({k: v for k, v in queries.items() if k in queries_to_keep}, doseq=True)

def clean_text( html, md = True, links = False, images = False, emphasis = False ):
    import html2text
    import markdown

    converter = html2text.HTML2Text()
    converter.ignore_links = links
    converter.ignore_images = images
    converter.ignore_emphasis = emphasis
    if md:
        return converter.handle( html )
    else:
        return markdown.markdown( converter.handle( html ) )

#-------------------------------------------------------------------------
#
# GBase class
#
#-------------------------------------------------------------------------

class GBase:

    def __init__(self):
        pass

#----------------------------------------------------------------------------------------------------------------------------------
#
# GPerson class
#
#----------------------------------------------------------------------------------------------------------------------------------

class GPerson(GBase):

    # -------------------------------------------------------------------------
    # __init__
    # -------------------------------------------------------------------------
    # url : geneanet url
    # person : calling GPerson

    def __init__(self, url):

        display(_("Person %s")%(url), level=2 )

        # Father and Mother and Spouses GPersons
        self.father = None
        self.mother = None
        self.spouse = []
        self.child = []

        # GFamilies
        self.family = []

        # Geneanet
        self.ref = clean_ref( url )
        self.path = urllib.parse.urljoin(url, '..')
        self.url = url
        
        self.sosa = None
        self.firstname = ""
        self.lastname = ""
        self.sex = 'U'
        self.birthdate = None
        self.birthplace = None
        self.deathdate = None
        self.deathplace = None

        self.parents = []

        self.unions = []

        self.siblings = []

        self.related = ""
        self.relation = ""
        self.notes = ""
        self.sources = ""

        self.scrap_geneanet()

    # -------------------------------------------------------------------------
    # _read_geneanet
    # -------------------------------------------------------------------------

    def _read_geneanet( self, page ):

        import selenium
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.action_chains import ActionChains

        # force fr language

        queries = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(page).query))
        if 'lang' in queries:
            if queries['lang'] != 'fr':
                page = page.replace( "lang=" + queries['lang'], "lang=fr" )
        else:
            page = page.replace( "?", "?lang=fr&" )

        # contents is an array of tuples
        # each tuple is the name of the bloc and content of the bloc

        contents = []
        medias = []

        Section = namedtuple("Section", "name content")

        browser = webdriver.Safari()
        browser.get(page)
        browser.maximize_window()
        
        try:
            WebDriverWait(browser, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, '//*[@id="tarteaucitronAllAllowed" or @id="tarteaucitronPersonalize2"]'))
            )

            try:
                actions = ActionChains(browser)
                button = browser.find_element(By.ID, 'tarteaucitronAllAllowed')
                actions.move_to_element(button).click().perform()
                print("Button 1 clicked successfully!")
            except:
                pass

            try:
                actions = ActionChains(browser)
                button = browser.find_element(By.ID, 'tarteaucitronPersonalize2')
                actions.move_to_element(button).click().perform()
                print("Button 2 clicked successfully!")
            except:
                pass
        except:
            pass

        screenshot_path = "screenshots/" + clean_ref( page ).replace('?','.').replace('=','_').replace('&','.') + ".png"
        browser.get_screenshot_as_file(screenshot_path)

        try:
            # Focus on perso bloc

            soup = BeautifulSoup(browser.page_source, 'html.parser')
            perso = soup.find("div", {"id": "perso"})

            # extract the medias

            medias = perso.find_all("img", attrs={"ng-src": re.compile(r".*")} )

            # extract the geneanet sections

            comments = perso.find_all(string=lambda text: isinstance(text, Comment))

            for comment in comments:
                if ' ng' in comment or 'Arbre' in comment:
                    continue

                extracted_content = []
                for sibling in comment.next_siblings:
                    if isinstance( sibling, Comment ):
                        break
                    extracted_content.append(str(sibling))

                contents = contents + [Section( comment.strip(), BeautifulSoup( ''.join([i for i in extracted_content if i != '\n']), 'html.parser' ) )]

                comment.extract()

        except:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            message = f'Exception [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
            print( message )
            pass

        browser.quit()

        return perso, medias, contents

    # -------------------------------------------------------------------------
    # scrap_geneanet
    # -------------------------------------------------------------------------

    def scrap_geneanet(self):

        # read web page
        
        perso, medias, sections = self._read_geneanet( self.url )

        for section in sections:

            # -------------------------------------------------------------
            # Portrait section
            # -------------------------------------------------------------
            if 'portrait' in section.name.lower():

                # sosa
                try:
                    sosa = section.content.find("em", {"class" : "sosa"}).find_all("a")

                    self.sosa = int(sosa[0].get_text().replace('\xa0', ''))
                except:
                    pass

                # first and last names
                try:
                    names = section.content.find("div", {"id" : "person-title"}).find_all_next("a")

                    self.firstname = names[0].get_text().title()
                    self.lastname = names[1].get_text().title()
                except:
                    pass

                # sex: should return M or F
                try:
                    sex = section.content.find("div", {"id" : "person-title"}).find_all_next("img", alt=True)

                    self.sex = sex[0]['alt']
                    if sex[0] == 'H':
                        self.sex = 'M'
                except:
                    self.sex = 'U'

                # birth
                try:
                    birth = section.content.find_all('li', string=lambda text: "Né" in text if text else False)[0].get_text()
                except:
                    birth = ""

                try:
                    self.birthdate = format_ca( convert_date(birth.split('-')[0].split()[1:]) )
                except:
                    self.birthdate = None

                try:
                    self.birthplace = str(birth.split(' - ')[1])
                except:
                    if len(birth) < 1:
                        pass
                    else:
                        self.birthplace = str(uuid.uuid3(uuid.NAMESPACE_URL, self.url))

                # death
                try:
                    death = section.content.find_all('li', string=lambda text: "Décédé" in text if text else False)[0].get_text()
                except:
                    death = ""

                try:
                    self.deathdate = format_ca( convert_date(death.split('-')[0].split()[1:]) )
                except:
                    self.deathdate = None

                try:
                    self.deathplace = re.split(f"{re.escape(",\nà l'âge")}|{re.escape(", à l'âge")}", str(death.split(' - ')[1]))[0]
                except:
                    if len(death ) < 1:
                        pass
                    else:
                        self.deathplace = str(uuid.uuid3(uuid.NAMESPACE_URL, self.url))

            # -------------------------------------------------------------
            # Parents section
            # -------------------------------------------------------------
            elif 'parents' in section.name.lower():
                
                try:
                    self.parents = [clean_ref( item['href'] ) for item in section.content.find_all("a") if len( item.find_all("img", {"alt" : "sosa"}) ) == 0]
                except:
                    pass

            # -------------------------------------------------------------
            # Union section
            # -------------------------------------------------------------
            elif 'union' in section.name.lower():
                Union = namedtuple("Marriage", "spouseref date place divorce childsref")

                try:
                    unions = section.content.find('ul', class_=re.compile('.*fiche_union.*') ).find_all( "li", recursive=False )

                    for union in unions:
                        try:
                            marriage = union.find("em").get_text()
                        except:
                            marriage = None
                            
                        # marriage date
                        try:
                            marriagedate = format_ca( convert_date(marriage.split(',')[0].split()[1:]) )
                        except:
                            marriagedate = None

                        # marriage place
                        try:
                            marriageplace = ', '.join([x for x in marriage.strip().split(',')[1:] if x]).strip()                           
                        except:
                            marriageplace = None

                        # spouse ref
                        try:
                            # first <a> can be a ref to sosa
                            spouseref = clean_ref( [a for a in union.find_all('a') if a.get_text(strip=True)][0]['href'] )
                            
                        except:
                            spouseref = None

                        # divorce date
                        divorcedate = None
                        display("Add divorce processing")

                        # childs
                        childsref = []
                        try:
                            for item in union.find("ul").find_all( "li", recursive=False ):
                                # first <a> can be a ref to sosa
                                childsref = childsref + [ clean_ref( [a for a in item.find_all('a') if a.get_text(strip=True)][0]['href'] ) ]
                        except:
                            childsref = []

                        self.unions = self.unions + [Union( spouseref, marriagedate, marriageplace, divorcedate, childsref)]

                except:
                    pass

            # -------------------------------------------------------------
            # Freres et Soeurs section
            # -------------------------------------------------------------
            elif 'freres et soeurs complet' in section.name.lower():
                try:
                    for item in section.content.find("ul").find_all( "li", recursive=False ):
                        tag_a = item.find('a')
                        if tag_a.get_text(strip=True): 
                            # first <a> can be a ref to sosa
                            self.siblings = self.siblings + [ clean_ref( tag_a['href'] ) ]
                except:
                    pass

            # -------------------------------------------------------------
            # Relation section
            # -------------------------------------------------------------
            elif 'relation' in section.name.lower():
                if len(section.content) > 0:
                    display("Add processing for section: %s"%(section.name))
                    self.relation = clean_text( str(section.content) )

            # -------------------------------------------------------------
            # Related section
            # -------------------------------------------------------------
            elif 'related' in section.name.lower():
                if len(section.content) > 0:
                    display("Add processing for section: %s"%(section.name))
                    self.related = clean_text( str(section.content) )

            # -------------------------------------------------------------
            # Notes section
            # -------------------------------------------------------------
            elif 'notes' in section.name.lower():
                if 'timeline' in section.name.lower():
                    if len(section.content) > 0:
                        display("Add processing for section: %s"%(section.name))
                        self.notes = self.notes + clean_text( str(section.content) )
                else:
                    if len(section.content) > 0:
                        display("Add processing for section: %s"%(section.name))
                        self.notes = self.notes + clean_text( str(section.content) )

            # -------------------------------------------------------------
            # Sources section
            # -------------------------------------------------------------
            elif 'sources' in section.name.lower():
                if len(section.content) > 0:
                    display("Add processing for section: %s"%(section.name))
                    self.sources = clean_text( str(section.content) )

            # -------------------------------------------------------------
            # Unprocess section
            # -------------------------------------------------------------
            else:
                if len(section.content) > 0:
                    display("Add processing for section: %s"%(section.name))

    # -------------------------------------------------------------------------
    # get_parents
    # -------------------------------------------------------------------------
    def get_parents( self ):
        return self.parents

    # -------------------------------------------------------------------------
    # get_spouses
    # -------------------------------------------------------------------------
    def get_spouses( self ):
        return[ union.spouseref for union in self.unions ]

    # -------------------------------------------------------------------------
    # get_childs
    # -------------------------------------------------------------------------
    def get_childs( self ):
        return[ union.childsref for union in self.unions ]

    # -------------------------------------------------------------------------
    # get_siblings
    # -------------------------------------------------------------------------
    def get_siblings( self ):
        return self.siblings

    # -------------------------------------------------------------------------
    # get_refs
    # -------------------------------------------------------------------------
    def get_refs( self ):
        return self.get_parents() + self.get_spouses() + self.get_childs()

class GPersons(GBase):

    # -------------------------------------------------------------------------
    # __init__
    # -------------------------------------------------------------------------

    def __init__(self):

        display(_("Persons"), level=2 )

        self.persons = {}

    # -------------------------------------------------------------------------
    # add_person
    # -------------------------------------------------------------------------


    def add_person( self, url ):

        ref = clean_ref( url )
        if ref not in self.persons:
            self.persons[ref] = GPerson( url )

            display( vars(self.persons[ref]), title=ref )


###################################################################################################################################
# add_persons
###################################################################################################################################

def add_persons( level, url ):
    global persons
    global ROOTURL
    global LEVEL

    ref = clean_ref( url )
    if ref not in persons:
        new_person = GPerson( urllib.parse.urljoin(ROOTURL, ref), None)
        persons[new_person.ref] = new_person
        related = new_person.get_refs()
        for ref in related:
            if isinstance( ref, list):
                print(ref)
            if level < LEVEL:
                add_persons( level + 1, ref )

###################################################################################################################################
# main
###################################################################################################################################

def main():

    # global allow local modification of these global variables
    global gedcom
    global gname
    global verbosity
    global force
    global ascendants
    global descendants
    global spouses
    global LEVEL
    global ROOTURL
    global translation
    global locale
    global _

    display( "GeneanetScrapping", level=1 )

    parser = argparse.ArgumentParser(description=_("Export Geneanet subtrees into GEDCOM file"))
    parser.add_argument("-v", "--verbosity", action="count", default=0, help=_("Increase verbosity"))
    parser.add_argument("-a", "--ascendants", default=False, action='store_true', help=_("Includes ascendants (off by default)"))
    parser.add_argument("-d", "--descendants", default=False, action='store_true', help=_("Includes descendants (off by default)"))
    parser.add_argument("-s", "--spouses", default=True, action='store_true', help=_("Includes all spouses (off by default)"))
    parser.add_argument("-l", "--level", default=2, type=int, help=_("Number of level to explore (2 by default)"))
    parser.add_argument("-g", "--gedcomfile", type=str, help=_("Full path of the out GEDCOM"))
    parser.add_argument("-f", "--force", default=False, action='store_true', help=_("Force processing"))
    parser.add_argument("searchedperson", type=str, nargs='?', help=_("Url of the person to search in Geneanet"))
    args = parser.parse_args()

    if args.searchedperson == None:
        print("Veuillez indiquer une personne à rechercher")
        return -1
    else:
        purl = args.searchedperson

    gname = args.gedcomfile
    verbosity = args.verbosity
    force = args.force
    ascendants = args.ascendants
    descendants = args.descendants
    spouses = args.spouses
    LEVEL = args.level

    if gname == None:
        print("Veuillez indiquer le nom du fichier GEDCOM à produire")
        sys.exit(-1)

    header_gedcom_text = """
        0 HEAD
        1 GEDC
        2 VERS 5.5
        2 FORM LINEAGE-LINKED
        1 CHAR UTF-8
        0 TRLR
    """
    gedcom = gedcom.parse_string(header_gedcom_text)

    if verbosity >= 1 and force:
        print("ATTENTION: mode forcer activé")
        time.sleep(TIMEOUT)

    # Create the first Person

    ROOTURL = urllib.parse.urljoin(purl, '..')
    LEVEL = 3

    persons = GPersons()
    persons.add_person( purl )

    persons.persons
    key, value = next(iter(persons.persons.items()))
    display( vars(value), title=key )

    display( persons, title="Persons" )

    exit()

    if souche != None:
        if ascendants:
            souche.recurse_parents(0)

    display( Persons, title="Persons" )

    if souche != None:
        if ascendants:
            souche.recurse_parents(0)

        fam = []
        if spouses:
            fam = souche.add_spouses(0)
        else:
            # TODO: If we don't ask for spouses, we won't get children at all
            pass

        if descendants:
            for f in fam:
                f.recurse_children(0)

    sys.exit(0)


if __name__ == '__main__':
    main()

