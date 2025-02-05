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
import random
import argparse
import urllib
from lxml import html, etree
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

#-------------------------------------------------------------------------
#
# GBase class
#
#-------------------------------------------------------------------------

class GBase:

    def __init__(self):
        pass

#-------------------------------------------------------------------------
#
# GFamily class
#
#-------------------------------------------------------------------------
# title
#
# marriagedate
# marriageplace
# marriageplacecode
#
# gid
#
# family
#
# childref
#
# url
#
# father
# mother

class GFamily(GBase):
    '''
    Family as seen by Geneanet
    '''
    def __init__(self, father, mother):

        display(_("GFamily::Creating family: %s %s - %s %s")%(father.firstname, father.lastname, mother.firstname, mother.lastname), level=2, verbose=1 )

        # The 2 GPersons parents in this family should exist
        # and properties filled before we create the family

        self.title = ""

        self.marriagedate = None
        self.marriageplace = None
        self.marriageplacecode = None
        
        self.gid = None

        self.family = None

        self.childref = []

        self.url = father.url
        if self.url == "":
            self.url = mother.url
        # TODO: what if father or mother is None
        self.father = father
        self.mother = mother

#----------------------------------------------------------------------------------------------------------------------------------
#
# GPerson class
#
#----------------------------------------------------------------------------------------------------------------------------------

class GPerson(GBase):
    '''
    Person  
    '''
    def __init__(self,level):

        display(_("Person::Initialize Person at level %d")%(level), level=2, verbose=1 )

        # Counter
        self.level = level

        # Father and Mother and Spouses GPersons
        self.father = None
        self.mother = None
        self.spouse = []
        self.child = []

        # GFamilies
        self.family = []

        # Geneanet
        self.url = ""
        self.ref = ""
        
        self.sosa = None
        self.firstname = ""
        self.lastname = ""
        self.sex = 'U'
        self.birthdate = None
        self.birthplace = None
        self.deathdate = None
        self.deathplace = None

        self.fatherref = None
        self.motherref = None

        self.unions = []

    # -------------------------------------------------------------------------
    # _clean_ref
    # -------------------------------------------------------------------------

    def _clean_ref( self, ref ):

        queries = urllib.parse.parse_qs(urllib.parse.urlparse(ref).query)
        queries_to_keep = [ 'nz', 'pz', 'm', 'v', 'p', 'n', 'oc' ]

        removed_queries = {k: v for k, v in queries.items() if k not in queries_to_keep + ['lang']}
        if len(removed_queries) > 0:
            display( "Removed queries: %s"%(removed_queries) )

        return re.sub( r'^/', '', urllib.parse.urlparse(ref).path ) + "?" + urllib.parse.urlencode({k: v for k, v in queries.items() if k != 'lang'}, doseq=True)
        return re.sub( r'^/', '', urllib.parse.urlparse(ref).path ) + "?" + urllib.parse.urlencode({k: v for k, v in queries.items() if k in queries_to_keep}, doseq=True)

    # -------------------------------------------------------------------------
    # read_geneanet
    # -------------------------------------------------------------------------

    def read_geneanet( self, page ):

        import selenium
        from selenium import webdriver

        # force fr language

        queries = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(page).query))
        if 'lang' in queries:
            if queries['lang'] != 'fr':
                page = page.replace( "&", "&lang=fr" )
        else:
            page = page.replace( "lang=" + queries['lang'], "lang=fr" )

        # contents is an array of tuples
        # each tuple is the name of the bloc and content of the bloc

        contents = []
        medias = []

        Section = namedtuple("Section", "name content")

        browser = webdriver.Safari()
        browser.get(page)

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

    def scrap_geneanet(self, purl):

        if not purl:
            return()

        display("Person::scrap_geneanet: %s"%(purl), level=2, verbose=1 )

        # read web page
        
        perso, medias, sections = self.read_geneanet( purl )

        tree = html.fromstring(perso.prettify())

        self.url = purl
        # self.title = tree.xpath('//title/text()')[0]

        # -----------------------------------------------------------------
        # ref
        # -----------------------------------------------------------------
        
        self.ref = self._clean_ref( purl )

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
                    if len(death) < 1:
                        pass
                    else:
                        self.deathplace = str(uuid.uuid3(uuid.NAMESPACE_URL, self.url))

            # -------------------------------------------------------------
            # Parents section
            # -------------------------------------------------------------
            elif 'parents' in section.name.lower():
                
                try:
                    parents = [item for item in section.content.find_all("a") if len( item.find_all("img", {"alt" : "sosa"}) ) == 0]
                except:
                    parents = []

                try:
                    self.fatherref = self._clean_ref( parents[0]['href'] )
                except:
                    self.fatherref = None

                try:
                    self.motherref = self._clean_ref( parents[1]['href'] )
                except:
                    self.motherref = None

            # -------------------------------------------------------------
            # Union section
            # -------------------------------------------------------------
            elif 'union' in section.name.lower():
                Union = namedtuple("Marriage", "spouseref date place divorce childs")

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
                            spouseref = self._clean_ref( union.find("a")['href'] )
                        except:
                            spouseref = None

                        # divorce date
                        divorcedate = None
                        display("Add divorce processing")

                        # childs
                        childs = []
                        try:
                            for item in union.find("ul").find_all( "li", recursive=False ):
                                tags_a = item.find_all('a')
                                childs = childs + [ tags_a[1]['href'] if tags_a[0].find("img") else tags_a[0]['href'] ]
                        except:
                            childs = []

                        self.unions = self.unions + [Union( spouseref, marriagedate, marriageplace, divorcedate, childs)]

                except:
                    pass

            # -------------------------------------------------------------
            # Union section
            # -------------------------------------------------------------
            elif 'union evolue' in section.name.lower():
                pass

            # -------------------------------------------------------------
            # Union section
            # -------------------------------------------------------------
            elif 'freres et soeurs complet' in section.name.lower():
                display("Add processing for section: %s"%(section.name))

            # -------------------------------------------------------------
            # Union section
            # -------------------------------------------------------------
            elif 'related' in section.name.lower():
                display("Add processing for section: %s"%(section.name))

            elif 'relation' in section.name.lower():
                display("Add processing for section: %s"%(section.name))

            elif 'notes' in section.name.lower():
                if 'timeline' in section.name.lower():
                    display("Add processing for section: %s"%(section.name))
                else:
                    display("Add processing for section: %s"%(section.name))

            elif 'sources' in section.name.lower():
                display("Add processing for section: %s"%(section.name))

            else:
                display("Unprocessed section: %s"%(section.name))

    # -------------------------------------------------------------------------
    # add_spouses
    # -------------------------------------------------------------------------

    def add_spouses(self,level):
        '''
        Add all spouses for this person, with corresponding families
        returns all the families created in a list
        '''

        display("GPerson::add_spouses", level=2, verbose=1 )

        i = 0
        ret = []
        while i < len(self.spouseref):
            spouse = None
            # Avoid handling already processed spouses
            for s in self.spouse:
                if s.url == self.spouseref[i]:
                    spouse = s
                    break

            if not spouse:
                spouse = geneanet_to_gedcom(None, level, None, ROOTURL+self.spouseref[i])

                if spouse:
                    self.spouse.append(spouse)
                    spouse.spouse.append(self)

                    # Create a GFamily 
                    display("=> Initialize Family of %s %s - %s %s"%(self.firstname,self.lastname,spouse.firstname,spouse.lastname), verbose=1)

                if self.sex == 'M':
                    f = GFamily(self, spouse)
                elif self.sex == 'F':
                    f = GFamily(spouse, self)
                else:
                    display("Unable to Initialize Family of "+self.firstname+" "+self.lastname+" sex unknown", verbose=1)
                    break

                # f.from_geneanet()
                # f.from_gedcom(f.gid)
                # f.to_gedcom()

                self.family.append(f)
                if spouse:
                    spouse.family.append(f)
                ret.append(f)
            i = i + 1
        return(ret)

    # -------------------------------------------------------------------------
    # recurse_parents
    # -------------------------------------------------------------------------

    def recurse_parents(self,level):
        '''
        analyze the parents of the person passed in parameter recursively
        '''

        display("GPerson::recurse_parents", level=2, verbose=1 )

        loop = False
        # Recurse while we have parents urls and level not reached
        if level <= LEVEL and (self.fatherref != "" or self.motherref != ""):
            loop = True
            level = level + 1

            if self.father:
                geneanet_to_gedcom(self.father, level, self.father.gid, self.fatherref)
                if self.mother:
                    self.mother.spouse.append(self.father)

                if verbosity >= 2:
                    print("=> Recursing on the parents of "+self.father.firstname+" "+self.father.lastname)
                self.father.recurse_parents(level)

                if verbosity >= 2:
                    print("=> End of recursion on the parents of "+self.father.firstname+" "+self.father.lastname)

            if self.mother:
                geneanet_to_gedcom(self.mother, level, self.mother.gid, self.motherref)
                if self.father:
                    self.father.spouse.append(self.mother)
                if verbosity >= 2:
                    print("=> Recursing on the mother of "+self.mother.firstname+" "+self.mother.lastname)
                self.mother.recurse_parents(level)

                if verbosity >= 2:
                    print("=> End of recursing on the mother of "+self.mother.firstname+" "+self.mother.lastname)

            # Create a GFamily
            if verbosity >= 2:
                print("=> Initialize Parents Family of "+self.firstname+" "+self.lastname)

            f = GFamily(self.father, self.mother)
            # f.from_geneanet()
            # f.from_gedcom(f.gid)
            # f.to_gedcom()

            if self.father:
                self.father.family.append(f)
            if self.mother:
                self.mother.family.append(f)

            # Deal with other spouses
            if spouses:
                fam = self.father.add_spouses(level)
                if ascendants:
                    for ff in fam:
                        if ff.gid != f.gid:
                            ff.mother.recurse_parents(level)
                if descendants:
                    for ff in fam:
                        if ff.gid != f.gid:
                            ff.recurse_children(level)
                fam = self.mother.add_spouses(level)
                if ascendants:
                    for mf in fam:
                        if mf.gid != f.gid:
                            mf.father.recurse_parents(level)
                if descendants:
                    for mf in fam:
                        if mf.gid != f.gid:
                            mf.recurse_children(level)


            # Now do what is needed depending on options
            if descendants:
                f.recurse_children(level)
            else:
                f.add_child(self)

        if not loop:
            if level > LEVEL:
                if verbosity >= 2:
                    print("Stopping exploration as we reached level "+str(level))
            else:
                if verbosity >= 1:
                    print("Stopping exploration as there are no more parents")
        return

###################################################################################################################################
# geneanet_to_gedcom
###################################################################################################################################

def geneanet_to_gedcom(p, level, gid, url):
    '''
    Function to create a person from Geneanet into GEDCOM
    '''

    display("geneanet_to_gedcom - Person: %s, Level: %d, GID: %s, url: %s"%(p, level, gid, url), level=2, verbose=1 )

    # Create the Person coming from Geneanet
    if not p:
        p = GPerson(level)

    p.scrap_geneanet(url)

    display( vars(p), title="geneanet_to_gedcom - Person %s"%(p.ref) )

    return(p)

    # Filling the Person from GEDCOM
    # Done after so we can try to find it in Gramps with the Geneanet data
    # p.from_gedcom(gid)

    # Check we point to the same person
    gid = None
    if gid != None:
        if (p.firstname != p.g_firstname or p.lastname != p.g_lastname) and (not force):
            print(_("GEDCOM person  : %s %s")%(p.firstname,p.lastname))
            print(_("Geneanet person: %s %s")%(p.g_firstname,p.g_lastname))
            sys.exit(_("Do not continue without force"))

        # Fix potential empty dates
        if p.g_birthdate == "":
            p.g_birthdate = None
        if p.birthdate == "":
            p.birthdate = None
        if p.g_deathdate == "":
            p.g_deathdate = None
        if p.deathdate == "":
            p.deathdate = None

        if p.birthdate == p.g_birthdate or p.deathdate == p.g_deathdate or force:
            pass
        else:
            print(_("GEDCOM person birth/death  : %s / %s")%(p.birthdate,p.deathdate))
            print(_("Geneanet person birth/death: %s / %s")%(p.g_birthdate,p.g_deathdate))
            sys.exit(_("Do not continue without force"))

    # Copy from Geneanet into GEDCOM and commit
    p.to_gedcom()

    display( vars(p), title="geneanet_to_gedcom - Person [ %s ] %s"%(p.gid, p.ref) )

    return(p)

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

    gp = geneanet_to_gedcom(None, 0, None, purl)

    exit(0)

    if gp != None:
        if ascendants:
            gp.recurse_parents(0)

        fam = []
        if spouses:
            fam = gp.add_spouses(0)
        else:
            # TODO: If we don't ask for spouses, we won't get children at all
            pass

        if descendants:
            for f in fam:
                f.recurse_children(0)

    # Write GEDCOM file
    # gedcom.save(gname)

    sys.exit(0)


if __name__ == '__main__':
    main()

