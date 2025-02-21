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

from common import display, event, clean_query, convert_date
from geneanet import Geneanet

# --------------------------------------------------------------------------------------------------
#
# GFamily class
#
# --------------------------------------------------------------------------------------------------

class GFamily():
    """
    Class of one family
    """

    # -------------------------------------------------------------------------
    # __init__
    # -------------------------------------------------------------------------

    def __init__(self, family ):

        self._gedcomid = None

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
        except:
            try:
                self._gedcomid = families_table[tuple(self._spousesref)[::-1]]
            except:
                pass

        self._spousesid = []
        for spouse in self._spousesref:
            try:
                self._spousesid = self._spousesid + [ individuals_table[spouse] ]
            except:
                self._spousesid = self._spousesid + [ None ]

        self._childsid = []
        for child in self._childsref:
            try:
                self._childsid = self._childsid + [ individuals_table[child] ]
            except:
                self._childsid = self._childsid + [ None ]

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

        events = {
            'MARR': ( 'marriagedate', 'marriageplace'),
            'DIV': ( 'divorcedate', 'divorceplace')
        }
        text = text + ''.join( [ event( self, tag, values[0], values[1] ) for tag, values in events.items() ])

        text = text + "\n"

        return text

    # -------------------------------------------------------------------------
    # print
    # -------------------------------------------------------------------------

    def print( self ):
        """
        Function to print the family
        """

        display( vars(self), title=f"Family [{self._gedcomid}]: {self._spousesref}" )

# --------------------------------------------------------------------------------------------------
#
# GIndividual class
#
# --------------------------------------------------------------------------------------------------

class GIndividual():
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

        self._parentsref = []
        self._parentsid = []
        self._familyid = None


        self._siblingsref = []
        self._siblingsid = []

        self._families = []
        self._familiesid = []

        if 'geneanet' in url:
            # scrap geneanet page
            geneanet = Geneanet()
            individual = geneanet.scrap( url, force )

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

    # -------------------------------------------------------------------------
    # setids
    # -------------------------------------------------------------------------
    def setids(self, individuals_table, families_table):
        """
        Function to set GEDCOM ids
        """

        try:
            self._gedcomid = individuals_table[self._ref]
        except:
            pass

        self._parentsid = []
        for parent in self._parentsref:
            try:
                self._parentsid = self._parentsid + [ individuals_table[parent] ]
            except:
                self._parentsid = self._parentsid + [ None ]

        try:
            self._familyid = families_table[tuple(self._parentsref)]
        except:
            try:
                self._familyid = families_table[tuple(self._parentsref)[::-1]]
            except:
                pass

        self._siblingsid = []
        for sibling in self._siblingsref:
            try:
                self._siblingsid = self._siblingsid + [ individuals_table[sibling] ]
            except:
                self._siblingsid = self._siblingsid + [ None ]

        self._familiesid = []
        for family in self._families:
            try:
                self._familiesid = self._familiesid + [ families_table[tuple(family.spousesref)] ]
            except:
                try:
                    self._familiesid = self._familiesid + [ families_table[tuple(family.spousesref)[::-1]] ]
                except:
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
    # gedcom
    # -------------------------------------------------------------------------
    @property
    def gedcom(self):
        """
        Property to get the GEDCOM of the individual
        """

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

        events = {
            'BIRT': ( 'birthdate', 'birthplace'),
            'DEAT': ( 'deathdate', 'deathplace'),
            'BURI': ( 'burialdate', 'burialplace')
        }
        text = text + ''.join( [ event( self._portrait, tag, values[0], values[1] ) for tag, values in events.items() ])

        for family in self._familiesid:
            if family:
                text = text + f"1 FAMS @{family}@\n"

        if hasattr(self, "_familyid"):
            text = text + f"1 FAMC @{self._familyid}@\n"

        if hasattr(self, "_notes"):
            notes = self._notes.splitlines()
            if len(notes) > 0:
                text = text + f"1 NOTE {notes[0]}\n"
                notes.pop(0)
                for note in notes:
                    text = text + f"2 CONT {note}\n"

        if hasattr(self, "_url"):
            text = text + f"1 SOUR {self._url}\n"

        text = text + "\n"

        return text

    # -------------------------------------------------------------------------
    # print
    # -------------------------------------------------------------------------

    def print( self ):
        """
        Function to print the individual
        """

        p = vars(self).copy()
        # del p['_notes']
        display( p, title=f"Individual [{self._gedcomid}]: {self._ref}" )
        # if individual.notes != "":
        #    display( individual.notes, title="" )

# --------------------------------------------------------------------------------------------------
#
# Genealogy class
#
# --------------------------------------------------------------------------------------------------

class Genealogy():
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

        if not self._parse:
            self._parse = urllib.parse.urlparse(url)

        if not self._user:
            self._user = re.sub( r'^/', '', self._parse.path )

        if urllib.parse.urlparse(url).scheme == "":
            url = urllib.parse.urlunparse((self._parse.scheme, self._parse.netloc, self._parse.path, '', url, ''))

        ref = clean_query( url )
        if ref not in self._individuals:
            self._individuals[ref] = GIndividual( url, force )
            try:
                new_families = self._individuals[ref].families
                for family in new_families:
                    if tuple(family.spousesref) not in self._families and tuple(family.spousesref)[::-1] not in self._families:
                        self._families[ tuple(family.spousesref) ] = family
            except:
                pass

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
        gedcom = gedcom + "2 VERS 5.5\n"
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

    def print( self ):
        """
        Function to print the genealogy
        """

        display( self._individuals, title=f"{len(self._individuals)} Individuals" )

        display( self._families, title=f"{len(self._families)} Families" )

        for individual in self._individuals.values():
            individual.print()

        for family in self._families.values():
            family.print()
