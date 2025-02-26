# genealogy
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
Package to manage Individuals and Families
"""

# -------------------------------------------------------------------------
#
# Standard Python Modules
#
# -------------------------------------------------------------------------

import re
from datetime import datetime
import urllib

# -------------------------------------------------------------------------
#
# Internal Python Modules
#
# -------------------------------------------------------------------------

from common import display, clean_query, convert_date
from geneanet import Geneanet

# --------------------------------------------------------------------------------------------------
#
# GBase class
#
# --------------------------------------------------------------------------------------------------

class GBase():
    """
    Class of common functions
    """

    # -------------------------------------------------------------------------
    #
    # _event
    #
    # -------------------------------------------------------------------------

    def _event( self, data, events ):
        """
        Function to get GEDCOM for one event made of TAG, DATE and PLACE
        """

        text = ""
        for event in events:
            if event[1] in data and data[event[1]]:
                text = f"1 {event[0]}\n"
                if f"{event[1]}date" in data and data[f"{event[1]}date"]:
                    text = text + f"2 DATE {data[f"{event[1]}date"]}\n"
                if f"{event[1]}place" in data and data[f"{event[1]}place"]:
                    text = text + f"2 PLAC {data[f"{event[1]}place"]}\n"


        return text

# --------------------------------------------------------------------------------------------------
#
# GFamily class
#
# --------------------------------------------------------------------------------------------------

class GFamily(GBase):
    """
    Class of one family
    """

    # -------------------------------------------------------------------------
    # __init__
    # -------------------------------------------------------------------------

    def __init__(self, family ):

        self._gedcomid = None

        self._marriage = self._marriagedate = self._marriageplace = None
        self._divorce = self._divorcedate = self._divorceplace = None

        self._spousesref = []
        self._spousesid = []

        self._childsref = []
        self._childsid = []

        for key, value in family.items():
            setattr(self, "_"+key, value)

    # -------------------------------------------------------------------------
    # setids
    # -------------------------------------------------------------------------

    def setids( self, individuals_table, families_table ):
        """
        Function to set GEDCOM ids
        """

        try:
            self._gedcomid = families_table[tuple(self._spousesref)]
        except Exception as e:
            display( f"Family gedcom (1): {type(e).__name__}", error=True )
            try:
                self._gedcomid = families_table[tuple(self._spousesref)[::-1]]
            except Exception as e2:
                display( f"Family gedcom (2): {type(e2).__name__}", error=True )

        self._spousesid = []
        for spouse in self._spousesref:
            try:
                self._spousesid = self._spousesid + [ individuals_table[spouse] ]
            except KeyError:
                self._spousesid = self._spousesid + [ None ]
            except Exception as e:
                display( f"Family spousesid: {type(e).__name__}", error=True )

        self._childsid = []
        for child in self._childsref:
            try:
                self._childsid = self._childsid + [ individuals_table[child] ]
            except KeyError:
                self._childsid = self._childsid + [ None ]
            except Exception as e:
                display( f"Family childid: {type(e).__name__}", error=True )

    # -------------------------------------------------------------------------
    # spousesref
    # -------------------------------------------------------------------------
    @property
    def spousesref(self):
        """
        Property to get the tuple of the spouses' reference of the family
        """
        return tuple( self._spousesref )

    # -------------------------------------------------------------------------
    # childsref
    # -------------------------------------------------------------------------
    @property
    def childsref(self):
        """
        Property to get the list of childs' reference of the family
        """
        return self._childsref

    # -------------------------------------------------------------------------
    # gedcom
    # -------------------------------------------------------------------------
    @property
    def gedcom(self):
        """
        Property to get the GEDCOM of the family
        """

        text = ""
        if hasattr(self, "_gedcomid"):
            text = text + f"0 @{self._gedcomid}@ FAM\n"

        if hasattr(self, "_spousesid"):
            if self._spousesid[0]:
                text = text + f"1 HUSB @{self._spousesid[0]}@\n"

            if self._spousesid[1]:
                text = text + f"1 WIFE @{self._spousesid[1]}@\n"

        if hasattr(self, "_childsid"):
            for childid in self._childsid:
                if childid:
                    text = text + f"1 CHIL @{childid}@\n"

        events = [ ( 'MARR', 'marriage'), ( 'DIV', 'divorce' )]
        text = text + self._event( vars(self), events )

        text = text + "\n"

        return text

    # -------------------------------------------------------------------------
    # print
    # -------------------------------------------------------------------------

    def print( self, short=False ):
        """
        Function to print the family
        """

        p = vars(self).copy()

        if short:
            removed_keys = []

            p = { key: value for key, value in p.items() if not key in removed_keys }

            p = { key: value for key, value in p.items() if not value is None }
            
            p = { key: value for key, value in p.items() if not ( isinstance( value, list) and len(value) == 0 ) }

        display( p, title=f"Family: {self._spousesref}" )

# --------------------------------------------------------------------------------------------------
#
# GIndividual class
#
# --------------------------------------------------------------------------------------------------

class GIndividual(GBase):
    """
    Class of one individual
    """

    # -------------------------------------------------------------------------
    # __init__
    # -------------------------------------------------------------------------

    def __init__(self, url, force = False):

        display( "" )
        display( f"Individual: {url}", level=2 )

        self._url = url
        self._ref = None

        self._gedcomid = None

        self._portrait = {}

        self._familyid = None
        self._parentsref = []
        self._parentsid = []


        self._siblingsref = []
        self._siblingsid = []

        self._families = []
        self._familiesid = []

        if 'geneanet' in url:
            # scrap geneanet page
            self._geneanet = Geneanet()
            individual = self._geneanet.scrap( url, force )

            if 'ref' in individual:
                self._ref = individual['ref']

            if 'portrait' in individual:
                self._portrait = individual['portrait']

            if 'parentsref' in individual:
                self._parentsref = individual['parentsref']

            if 'siblingsref' in individual:
                self._siblingsref = individual['siblingsref']

            if 'families' in individual:
                self._families = [ GFamily( family ) for family in individual['families'] ]

        else:
            display( f"Add processing for {url}", error=True )

        self.print(True)

        for family in self._families:
            family.print(True)

    # -------------------------------------------------------------------------
    # setids
    # -------------------------------------------------------------------------
    def setids(self, individuals_table, families_table):
        """
        Function to set GEDCOM ids
        """

        # INDI id

        self._gedcomid = None
        try:
            self._gedcomid = individuals_table[self._ref]
        except KeyError:
            pass
        except Exception as e:
            display( f"Gedcom individual: {type(e).__name__}", error=True )

        # Parents INDI id

        self._parentsid = []
        for parent in self._parentsref:
            try:
                self._parentsid = self._parentsid + [ individuals_table[parent] ]
            except KeyError:
                pass
            except Exception as e:
                display( f"Parentsid: {type(e).__name__}", error=True )
                self._parentsid = self._parentsid + [ None ]

        # Siblings INDI id

        self._siblingsid = []
        for sibling in self._siblingsref:
            try:
                self._siblingsid = self._siblingsid + [ individuals_table[sibling] ]
            except KeyError:
                self._siblingsid = self._siblingsid + [ None ]
            except Exception as e:
                display( f"Siblingsid: {type(e).__name__}", error=True )
                self._siblingsid = self._siblingsid + [ None ]

        # Parents FAM id

        self._familyid = None
        try:
            self._familyid = families_table[tuple(self._parentsref)]
        except KeyError:
            try:
                self._familyid = families_table[tuple(self._parentsref)[::-1]]
            except KeyError:
                pass
            except Exception as e2:
                display( f"Familyid (2): {type(e2).__name__}", error=True )
        except Exception as e:
            display( f"Familyid (1): {type(e).__name__}", error=True )

        # FAM id

        self._familiesid = []
        for family in self._families:
            try:
                self._familiesid = self._familiesid + [ families_table[tuple(family.spousesref)] ]
            except KeyError:
                try:
                    self._familiesid = self._familiesid + [ families_table[tuple(family.spousesref)[::-1]] ]
                except Exception as e2:
                    display( f"Familiesid (2): {type(e2).__name__}", error=True )
                    self._familiesid = self._familiesid + [ None ]
            except Exception as e:
                display( f"Familiesid (1): {type(e).__name__}", error=True )
                self._familiesid = self._familiesid + [ None ]

    # -------------------------------------------------------------------------
    # url
    # -------------------------------------------------------------------------
    @property
    def url(self):
        """
        Property to get the url of the individual
        """
        return self._url

    # -------------------------------------------------------------------------
    # notes
    # -------------------------------------------------------------------------
    @property
    def notes(self):
        """
        Property to get the list of notes of the individual
        """
        return self._portrait['notes'] if 'notes' in self._portrait else None

    # -------------------------------------------------------------------------
    # portrait
    # -------------------------------------------------------------------------
    @property
    def portrait(self):
        """
        Property to get the data of the individual
        """
        return self._portrait

    # -------------------------------------------------------------------------
    # parentsref
    # -------------------------------------------------------------------------
    @property
    def parentsref(self):
        """
        Property to get the list of parents' reference of the individual
        """
        return self._parentsref

    # -------------------------------------------------------------------------
    # spousesref
    # -------------------------------------------------------------------------
    @property
    def spousesref(self):
        """
        Property to get the list of spouses' reference of the individual
        """
        return [ item for sublist in [ family.spousesref for family in self._families ] for item in sublist ]

    # -------------------------------------------------------------------------
    # childsref
    # -------------------------------------------------------------------------
    @property
    def childsref(self):
        """
        Property to get the list of childs' reference of the individual
        """
        return [ item for sublist in [ family.childsref for family in self._families ] for item in sublist ]

    # -------------------------------------------------------------------------
    # siblingsref
    # -------------------------------------------------------------------------
    @property
    def siblingsref(self):
        """
        Property to get the list of siblings' reference of the individual
        """
        return self._siblingsref

    # -------------------------------------------------------------------------
    # families
    # -------------------------------------------------------------------------
    @property
    def families(self):
        """
        Property to get the list of families of the individual
        """
        return self._families

    # -------------------------------------------------------------------------
    # html
    # -------------------------------------------------------------------------
    @property
    def html(self):
        """
        Property to get the html of the individual
        """
        if hasattr( self, '_geneanet'):
            return self._geneanet.html
        else:
            return ""

    # -------------------------------------------------------------------------
    # gedcom
    # -------------------------------------------------------------------------
    @property
    def gedcom(self):
        """
        Property to get the GEDCOM of the individual
        """

        # portrait

        text = ""
        if hasattr(self, "_gedcomid"):
            text = text + f"0 @{self._gedcomid}@ INDI\n"

        names = { 'name': "", "first": "", "last": ""}
        if 'firstname' in self._portrait:
            names['name'] = self._portrait['firstname']
            names["first"] = f"2 GIVN {self._portrait['firstname']}\n"
        if 'lastname' in self._portrait:
            names['name'] = names['name'] + f" /{self._portrait['lastname']}/"
            names["last"] = f"2 SURN {self._portrait['lastname']}\n"
        if len(names['name']) > 0:
            names['name'] = f"1 NAME {names['name'].strip()}\n"
        text = text + ''.join([name for key, name in names.items() if len(name) >0])

        if 'sex' in self._portrait:
            text = text + f"1 SEX {self._portrait['sex']}\n"

        events = [ ( 'BIRT', 'birth'), ( 'DEAT', 'death'), ( 'BURI', 'burial' ) ]
        text = text + self._event( self._portrait, events )

        # family

        for family in self._familiesid:
            if family:
                text = text + f"1 FAMS @{family}@\n"

        if hasattr(self, "_familyid") and not self._familyid is None:
            text = text + f"1 FAMC @{self._familyid}@\n"

        # notes

        if hasattr(self._portrait, "_notes"):
            for note in self._portrait['notes']:
                note = note.splitlines()
                if len(note) > 0:
                    text = text + f"1 NOTE {note[0]}\n"
                    note.pop(0)
                    for line in note:
                        text = text + f"2 CONT {line}\n"

        if hasattr(self, "_url") and not self._url is None:
            text = text + f"1 SOUR {self._url}\n"

        # sources

        text = text + "\n"

        return text

    # -------------------------------------------------------------------------
    # print
    # -------------------------------------------------------------------------

    def print( self, short=False ):
        """
        Function to print the individual
        """

        p = vars(self).copy()

        if short:
            removed_keys = ['_gedcom', '_parentsid', '_siblingsref', '_siblingsid', '_familyid', '_geneanet', '_families', '_familiesid']

            p = { key: value for key, value in p.items() if not key in removed_keys }

            p = { key: value for key, value in p.items() if not value is None }
            
            p = { key: value for key, value in p.items() if not ( isinstance( value, list) and len(value) == 0 ) }

            if '_notes' in p['_portrait']:
                del p['_portrait']['_notes']
        
        display( p, title=f"Individual: {self._ref}" )

# --------------------------------------------------------------------------------------------------
#
# Genealogy class
#
# --------------------------------------------------------------------------------------------------

class Genealogy(GBase):
    """
    Class for the complete genealogy
    """

    # -------------------------------------------------------------------------
    # __init__
    # -------------------------------------------------------------------------

    def __init__(self, max_level, ascendants, spouses, descendants ):

        self._parse = None
        self._user = None

        self._individuals = {}
        self._max_level = max_level
        self._ascendants = ascendants
        self._spouses = spouses
        self._descendants = descendants

        self._families = {}

    # -------------------------------------------------------------------------
    # add_individual
    # -------------------------------------------------------------------------

    def add_individual( self, url, force = False, level = 0 ):
        """
        Function to add one individual to the genealogy
        """

        if urllib.parse.urlparse(url).scheme == "":
            url = urllib.parse.urlunparse((self._parse.scheme, self._parse.netloc, self._parse.path, '', url, ''))
        else:
            self._parse = urllib.parse.urlparse(url)

        self._user = re.sub( r'^/', '', self._parse.path )

        ref = clean_query( url )
        if ref not in self._individuals:
            self._individuals[ref] = GIndividual( url, force )
            try:
                new_families = self._individuals[ref].families
                for family in new_families:
                    if tuple(family.spousesref) not in self._families and tuple(family.spousesref)[::-1] not in self._families:
                        self._families[ tuple(family.spousesref) ] = family
            except Exception as e:
                display( f"Add individual: {type(e).__name__}", error=True )

            if level < self._max_level:

                if self._ascendants:
                    for parent in self._individuals[ref].parentsref:
                        self.add_individual( parent, force, level+1 )

                if self._spouses:
                    for spouse in self._individuals[ref].spousesref:
                        self.add_individual( spouse, force, level+1 )

                if self._descendants:
                    for child in self._individuals[ref].childsref:
                        self.add_individual( child, force, level+1 )

    # -------------------------------------------------------------------------
    # gedcom
    # -------------------------------------------------------------------------

    def gedcom( self, force = False ):
        """
        Function to get the GEDCOM of the genealogy
        """

        display( "" )
        display( "GEDCOM", level=2 )

        # set gedcom id
        individuals_table = {key: f"I{index+1:05d}" for index, key in enumerate(self._individuals)}
        families_table = {key: f"F{index+1:05d}" for index, key in enumerate(self._families)}

        for individual in self._individuals.values():
            individual.setids( individuals_table, families_table )

        for family in self._families.values():
            family.setids( individuals_table, families_table )

        # Author

        if len(self._individuals) > 0:
            geneanet = Geneanet()
            informations = geneanet.informations( next(iter(self._individuals.values())).url, force )

        # HEADER

        gedcom = "0 HEAD\n"
        gedcom = gedcom + "1 SOUR GenealogyScrapping\n"
        gedcom = gedcom + "2 VERS 1.0\n"
        gedcom = gedcom + "2 NAME Genealogy Scrapping\n"
        gedcom = gedcom + "1 GEDC\n"
        gedcom = gedcom + "2 VERS 5.5.1\n"
        gedcom = gedcom + "2 FORM LINEAGE-LINKED\n"
        gedcom = gedcom + "1 CHAR UTF-8\n"
        gedcom = gedcom + "1 SUBM @B00000@\n"
        gedcom = gedcom + "\n"

        # SUBM

        gedcom = gedcom + "0 @B00000@ SUBM\n"
        gedcom = gedcom + "1 NAME Laurent Burais\n"
        gedcom = gedcom + "1 CHAN\n"
        gedcom = gedcom + f"2 DATE {(convert_date([str(datetime.today().day), str(datetime.today().month), str(datetime.today().year)]))}\n"
        gedcom = gedcom + "\n"

        # REPO

        if hasattr(self, '_parse') and 'informations' in locals():
            gedcom = gedcom + "0 @R00000@ REPO\n"
            if 'author' in informations:
                gedcom = gedcom + f"1 NAME {informations['author']}\n"
            if 'lastchange' in informations:
                gedcom = gedcom + "1 CHAN\n"
                gedcom = gedcom + f"2 DATE {informations['lastchange']}\n"
            gedcom = gedcom + f"1 WWW {urllib.parse.urlunparse((self._parse.scheme, self._parse.netloc, self._parse.path, '', '', ''))}\n"
            gedcom = gedcom + "1 REPO_TYPE Geneanet\n"
            gedcom = gedcom + "\n"

        # INDI with SOUR and NOTE

        for individual in self._individuals.values():
            gedcom = gedcom + individual.gedcom

        # FAM

        for family in self._families.values():
            gedcom = gedcom + family.gedcom

        # TAILER

        gedcom = gedcom + "0 TRLR"

        return gedcom

    # -------------------------------------------------------------------------
    # print
    # -------------------------------------------------------------------------

    def print( self, all_details=False ):
        """
        Function to print the genealogy
        """

        if all_details:
            display( self._individuals, title=f"{len(self._individuals)} Individuals" )

            display( self._families, title=f"{len(self._families)} Families" )

        for individual in self._individuals.values():
            individual.print(short=False)

        for family in self._families.values():
            family.print(short=False)

    # -------------------------------------------------------------------------
    # html
    # -------------------------------------------------------------------------

    def html( self, url ):
        """
        Function to retrieve html for one individual
        """

        try:
            return [v.html for v in self._individuals.values() if v.url == url][0]
        except Exception as e:
            display( f"Genealogy html: {type(e).__name__}", error=True )
            return ""
