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

from common import *
from geneanet import Geneanet

#-------------------------------------------------------------------------
#
# Used Python Modules
#
#-------------------------------------------------------------------------

import re

#----------------------------------------------------------------------------------------------------------------------------------
#
# GFamily class
#
#----------------------------------------------------------------------------------------------------------------------------------

class GFamily():

    # -------------------------------------------------------------------------
    # __init__
    # -------------------------------------------------------------------------

    def __init__(self, family ):

        for key, value in family.items():
            setattr(self, "_"+key, value)

    # -------------------------------------------------------------------------
    # setids
    # -------------------------------------------------------------------------
    def setids(self, persons_table, families_table):
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
                self._spousesid = self._spousesid + [ persons_table[spouse] ]
            except:
                self._spousesid = self._spousesid + [ None ]

        if hasattr(self, '_childsref'):
            self._childsid = []
            for child in self._childsref:
                try:
                    self._childsid = self._childsid + [ persons_table[child] ]
                except:
                    self._childsid = self._childsid + [ None ]

    # -------------------------------------------------------------------------
    # spousesref
    # -------------------------------------------------------------------------
    @property
    def spousesref(self):
        return tuple( self._spousesref )

    # -------------------------------------------------------------------------
    # childsref
    # -------------------------------------------------------------------------
    @property
    def childsref(self):
        return self._childsref

    # -------------------------------------------------------------------------
    # gedcom
    # -------------------------------------------------------------------------
    @property
    def gedcom(self):

        text = ""
        if hasattr(self, "_gedcomid"):
            text = text + "0 @%s@ FAM\n"%(self._gedcomid)

        if hasattr(self, "_spousesid"):
            if self._spousesid[0]:
                text = text + "1 HUSB @%s@\n"%(self._spousesid[0])
            
            if self._spousesid[1]:
                text = text + "1 WIFE @%s@\n"%(self._spousesid[1])

        if hasattr(self, "_childsid"):
            for childid in self._childsid:
                if childid:
                    text = text + "1 CHIL @%s@\n"%(childid)
        
        events = {
            'MARR': ( 'marriagedate', 'marriageplace'),
            'DIV': ( 'divorcedate', 'divorceplace')
        }
        text = text + ''.join( [ event( self, tag, values[0], values[1] ) for tag, values in events.items() ])

        text = text + "\n"

        return text

#----------------------------------------------------------------------------------------------------------------------------------
#
# GPerson class
#
#----------------------------------------------------------------------------------------------------------------------------------

class GPerson():

    # -------------------------------------------------------------------------
    # __init__
    # -------------------------------------------------------------------------
    # url : genealogy url

    def __init__(self, url, force = False):

        display( "" )
        display("Person: %s"%(url), level=2 )

        self._url = url

        self._portrait = {}

        self._parentsref = []

        self._siblingsref = []

        self._families = []

        if 'geneanet' in url:
            # scrap geneanet page
            geneanet = Geneanet()
            person = geneanet.scrap( url, force )

            if 'portrait' in person:
                self._portrait = person['portrait']

            if 'parentsref' in person:
                self._parentsref = person['parentsref']

            if 'siblingsref' in person:
                self._siblingsref = person['siblingsref']

            if 'families' in person:
                self._families = [ GFamily( family ) for family in person['families'] ]

        else:
            display( "Add processing for %"%(url), error=True )

    # -------------------------------------------------------------------------
    # setids
    # -------------------------------------------------------------------------
    def setids(self, persons_table, families_table):

        try:
            self._gedcomid = persons_table[self._ref]
        except:
            pass

        self._parentsid = []
        for parent in self._parentsref:
            try:
                self._parentsid = self._parentsid + [ persons_table[parent] ]
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
                self._siblingsid = self._siblingsid + [ persons_table[sibling] ]
            except:
                self._siblingsid = self._siblingsid + [ None ]

        self._familiesid = []
        for family in self._families:
            try:
                self._familiesid = self._familiesid + [ families_table[tuple(family._spousesref)] ]
            except:
                try:
                    self._familiesid = self._familiesid + [ families_table[tuple(family._spousesref)[::-1]] ]
                except:
                    self._familiesid = self._familiesid + [ None ]

    # -------------------------------------------------------------------------
    # url
    # -------------------------------------------------------------------------
    @property
    def url(self):
        return self._url

    # -------------------------------------------------------------------------
    # notes
    # -------------------------------------------------------------------------
    @property
    def notes(self):
        return self._notes if len(self._notes) > 0 else None

    # -------------------------------------------------------------------------
    # portrait
    # -------------------------------------------------------------------------
    @property
    def portrait(self):
        return self._portrait

    # -------------------------------------------------------------------------
    # parentsref
    # -------------------------------------------------------------------------
    @property
    def parentsref(self):
        return self._parentsref

    # -------------------------------------------------------------------------
    # spousesref
    # -------------------------------------------------------------------------
    @property
    def spousesref(self):
        return [item for sublist in [ family.spousesref for family in self._families ] for item in sublist]

    # -------------------------------------------------------------------------
    # childsref
    # -------------------------------------------------------------------------
    @property
    def childsref(self):
        return [item for sublist in [ family.childsref for family in self._families ] for item in sublist]

    # -------------------------------------------------------------------------
    # siblingsref
    # -------------------------------------------------------------------------
    @property
    def siblingsref(self):
        return self._siblingsref

    # -------------------------------------------------------------------------
    # families
    # -------------------------------------------------------------------------
    @property
    def families(self):
        return self._families

    # -------------------------------------------------------------------------
    # gedcom
    # -------------------------------------------------------------------------
    @property
    def gedcom(self):

        text = ""
        if hasattr(self, "_gedcomid"):
            text = text + "0 @%s@ INDI\n"%(self._gedcomid)
        
        names = { 'name': "", "first": "", "last": ""}
        if 'firstname' in self._portrait:
            names['name'] = self._portrait['firstname']
            names["first"] = "2 GIVN %s\n"%(self._portrait['firstname'])
        if 'lastname' in self._portrait:
            names['name'] = names['name'] + " /%s/"%(self._portrait['lastname'])
            names["last"] = "2 SURN %s\n"%(self._portrait['lastname'])
        if len(names['name']) > 0:
            names['name'] = "1 NAME %s\n"%(names['name'].strip())
        text = text + ''.join([name for key, name in names.items() if len(name) >0])

        if 'sex' in self._portrait:
            text = text + "1 SEX %s\n"%(self._portrait['sex'])

        events = {
            'BIRT': ( 'birthdate', 'birthplace'),
            'DEAT': ( 'deathdate', 'deathplace'),
            'BURI': ( 'burialdate', 'burialplace')
        }
        text = text + ''.join( [ event( self._portrait, tag, values[0], values[1] ) for tag, values in events.items() ])

        for family in self._familiesid:
            if family:
                text = text + "1 FAMS @%s@\n"%(family)

        if hasattr(self, "_familyid"):
            text = text + "1 FAMC @%s@\n"%(self._familyid)
        
        if hasattr(self, "_notes"):
            notes = self._notes.splitlines()
            if len(notes) > 0:
                text = text + "1 NOTE %s\n"%(notes[0])
                notes.pop(0)
                for note in notes:
                    text = text + "2 CONT %s\n"%(note)
            
        if hasattr(self, "_url"):
            text = text + "1 SOUR %s\n"%(self._url)
            
        text = text + "\n"

        return text

#----------------------------------------------------------------------------------------------------------------------------------
#
# GPersons class
#
#----------------------------------------------------------------------------------------------------------------------------------

class GPersons():

    # -------------------------------------------------------------------------
    # __init__
    # -------------------------------------------------------------------------

    def __init__(self, max_level, ascendants, spouses, descendants ):

        self._persons = {}
        self._max_level = max_level
        self._ascendants = ascendants
        self._spouses = spouses
        self._descendants = descendants

        self._families = {}

    # -------------------------------------------------------------------------
    # add_person
    # -------------------------------------------------------------------------

    def add_person( self, url, force = False, level = 0 ):

        if not hasattr(self, '_parse'):
            self._parse = urllib.parse.urlparse(url)

        if not hasattr(self, '_user'):
            self._user = re.sub( r'^/', '', self._parse.path )

        if urllib.parse.urlparse(url).scheme == "":
            url = urllib.parse.urlunparse((self._parse.scheme, self._parse.netloc, self._parse.path, '', url, ''))

        ref = clean_query( url )
        if ref not in self._persons:
            self._persons[ref] = GPerson( url, force )
            try:
                new_families = self._persons[ref].families
                for family in new_families:
                    if tuple(family.spousesref) not in self._families and tuple(family.spousesref)[::-1] not in self._families:
                        self._families[ tuple(family.spousesref) ] = family
            except:
                pass

            if level < self._max_level:

                if self._ascendants:
                    for parent in self._persons[ref].parentsref:
                        self.add_person( parent, force, level+1 )

                if self._spouses:
                    for spouse in self._persons[ref].spousesref:
                        self.add_person( spouse, force, level+1 )

                if self._descendants:
                    for child in self._persons[ref].childsref:
                        self.add_person( child, force, level+1 )

    # -------------------------------------------------------------------------
    # gedcom
    # -------------------------------------------------------------------------
    def gedcom( self, force = False ):

        display( "" )
        display( "GEDCOM", level=2 )

        # set gedcom id
        persons_table = {key: "I%05d"%(index+1) for index, key in enumerate(self._persons)}
        families_table = {key: "F%05d"%(index+1) for index, key in enumerate(self._families)}

        for ref, person in self._persons.items():
            person.setids( persons_table, families_table )

        for ref, family in self._families.items():
            family.setids( persons_table, families_table )

        # Author

        if len(self._persons) > 0:
            geneanet = Geneanet()
            informations = geneanet.informations( next(iter(self._persons.values())).url, force )

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
        gedcom = gedcom + "2 DATE %s\n"%(convert_date([str(datetime.today().day), str(datetime.today().month), str(datetime.today().year)]))
        gedcom = gedcom + "\n"

        # REPO

        if hasattr(self, '_parse') and 'informations' in locals():
            gedcom = gedcom + "0 @R00000@ REPO\n"
            if 'author' in informations:
                gedcom = gedcom + "1 NAME %s\n"%(informations['author'])
            if 'lastchange' in informations:
                gedcom = gedcom + "1 CHAN\n"
                gedcom = gedcom + "2 DATE %s\n"%(informations['lastchange'])
            gedcom = gedcom + "1 WWW %s\n"%(urllib.parse.urlunparse((self._parse.scheme, self._parse.netloc, self._parse.path, '', '', '')))
            gedcom = gedcom + "1 REPO_TYPE Geneanet\n"
            gedcom = gedcom + "\n"

        # INDI with SOUR and NOTE

        for ref, person in self._persons.items():
            gedcom = gedcom + person.gedcom

        # FAM

        for ref, family in self._families.items():
            gedcom = gedcom + family.gedcom

        # TAILER

        gedcom = gedcom + "0 TRLR"

        return gedcom

    # -------------------------------------------------------------------------
    # print
    # -------------------------------------------------------------------------

    def print( self ):
        display( self._persons, title="%d Persons"%(len(self._persons)) )

        display( self._families, title="%d Families"%(len(self._families)) )

        for key, person in self._persons.items():
            p = vars(person).copy()
            # del p['_notes']
            display( p, title="Person: %s"%(key) )
            # if person.notes != "":
            #    display( person.notes, title="" )

        for key, family in self._families.items():
            display( vars(family), title="Family: %s"%(str(key)) )

