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

from datetime import datetime
from urllib.parse import urlunparse, urlparse
import textwrap

# -------------------------------------------------------------------------
#
# Internal Python Modules
#
# -------------------------------------------------------------------------

from common import display
from geneanet import Geneanet

# from objects import Individual, Family

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
    # _event
    # -------------------------------------------------------------------------

    def _event(self, data, events):
        """
        Function to get GEDCOM for one event made of TAG, DATE and PLACE
        """

        text = ""
        for event in events:
            if event[1] in data and data[event[1]]:
                text += f"1 {event[0]}\n"
                if f"{event[1]}date" in data and data[f"{event[1]}date"]:
                    text += f"2 DATE {data[f'{event[1]}date']}\n"
                if f"{event[1]}place" in data and data[f"{event[1]}place"]:
                    place = data[f'{event[1]}place']
                    text += f"2 PLAC {place.fullname}\n"
                    if place.latitude:
                        text += f"3 LATI {'N' if float(place.latitude) > 0 else 'S'}{abs(float(place.latitude)):.4f}\n"
                    if place.longitude:
                        text += f"3 LONG {'E' if float(place.longitude) > 0 else 'W'}{abs(float(place.longitude)):.4f}\n"

        return text

    # -------------------------------------------------------------------------
    # _shorten_data
    # -------------------------------------------------------------------------

    def _shorten_data(self, data):

        data = {key: value for key, value in data.items() if value is not None}

        data = {key: value for key, value in data.items() if not (isinstance(value, list) and len(value) == 0)}

        return data

    # -------------------------------------------------------------------------
    # _shorten_event
    # -------------------------------------------------------------------------

    def _shorten_event(self, data, keys):

        for key in keys:
            if key in data:

                if data[key] is False:
                    del data[key]

                elif not data[f"{key}date"] or not data[f"{key}place"] is None:
                    del data[key]

        return data

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

    def __init__(self, family):

        self._family = family

    # -------------------------------------------------------------------------
    # setids
    # -------------------------------------------------------------------------

    def setids(self, individuals_table, families_table):
        """
        Function to set GEDCOM ids
        """

        try:
            self._family.data.gedcomid = families_table[tuple(self._family.spousesref)]
        except Exception as e:
            display(f"Family gedcom (1): {type(e).__name__}", error=True)
            try:
                self._family.data.gedcomid = families_table[tuple(self._family.spousesref)[::-1]]
            except Exception as e2:
                display(f"Family gedcom (2): {type(e2).__name__}", error=True)

        self._family.data.spousesid = []
        for spouse in self._family.spousesref:
            try:
                self._family.data.spousesid += [individuals_table[spouse]]
            except KeyError:
                self._family.data.spousesid += [None]
            except Exception as e:
                display(f"Family spousesid: {type(e).__name__}", error=True)

        self._family.data.childsid = []
        for child in self._family.childsref:
            try:
                self._family.data.childsid += [individuals_table[child]]
            except KeyError:
                self._family.data.childsid += [None]
            except Exception as e:
                display(f"Family childid: {type(e).__name__}", error=True)

    # -------------------------------------------------------------------------
    # spousesref
    # -------------------------------------------------------------------------
    @property
    def spousesref(self):
        """
        Property to get the tuple of the spouses' reference of the family
        """
        return tuple(self._family.spousesref)

    # -------------------------------------------------------------------------
    # childsref
    # -------------------------------------------------------------------------
    @property
    def childsref(self):
        """
        Property to get the list of childs' reference of the family
        """
        return self._family.childsref

    # -------------------------------------------------------------------------
    # gedcom
    # -------------------------------------------------------------------------
    @property
    def gedcom(self):
        """
        Property to get the GEDCOM of the family
        """

        text = ""
        if self._family.data.gedcomid:

            text += f"0 @{self._family.data.gedcomid}@ FAM\n"

            if self._family.data.spousesid[0]:
                text += f"1 HUSB @{self._family.data.spousesid[0]}@\n"

            if self._family.data.spousesid[1]:
                text += f"1 WIFE @{self._family.data.spousesid[1]}@\n"

            for childid in self._family.data.childsid:
                if childid:
                    text += f"1 CHIL @{childid}@\n"

            events = [('MARR', 'marriage'), ('DIV', 'divorce')]
            text += self._event(self._family.data, events)

            text += "\n"

        return text

    # -------------------------------------------------------------------------
    # print
    # -------------------------------------------------------------------------

    def print(self, short=False):
        """
        Function to print the family
        """

        if short:
            p = self._shorten_event(self._family.data.copy(), ['marriage', 'divorce'])
            p = self._shorten_data(p.copy())

        else:
            p = self._family.copy()

        display(p, title=f"Family: {self._family.spousesref}")

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

    def __init__(self, source, url, force=False):

        display("")
        display(f"Individual: {url}", level=2)

        self._parser = source

        self._individual = None

        try:
            # scrap geneanet page
            self._individual = self._parser.scrap(url, force)

            # set families
            self._individual.families = [GFamily(family) for family in self._individual.familiesref]

        except Exception as e:
            display(f"{e}: Add processing for {url}", error=True)

        self.print(True)

        for family in self._individual.families:
            family.print(True)

    # -------------------------------------------------------------------------
    # setids
    # -------------------------------------------------------------------------
    def setids(self, individuals_table, families_table):
        """
        Function to set GEDCOM ids
        """

        # INDI id

        self._individual.data.gedcomid = None
        try:
            self._individual.data.gedcomid = individuals_table[self._individual.ref]
        except KeyError:
            pass
        except Exception as e:
            display(f"Gedcom individual: {type(e).__name__}", error=True)

        # Parents INDI id

        self._individual.data.parentsid = []
        for parent in self._individual.parentsref:
            try:
                self._individual.data.parentsid += [individuals_table[parent]]
            except KeyError:
                pass
            except Exception as e:
                display(f"Parentsid: {type(e).__name__}", error=True)
                self._individual.data.parentsid += [None]

        # Siblings INDI id

        self._individual.data.siblingsid = []
        for sibling in self._individual.siblingsref:
            try:
                self._individual.data.siblingsid += [individuals_table[sibling]]
            except KeyError:
                self._individual.data.siblingsid += [None]
            except Exception as e:
                display(f"Siblingsid: {type(e).__name__}", error=True)
                self._individual.data.siblingsid += [None]

        # Parents FAM id

        self._individual.data.familyid = None
        try:
            self._individual.data.familyid = families_table[tuple(self._individual.parentsref)]
        except KeyError:
            try:
                self._individual.data.familyid = families_table[tuple(self._individual.parentsref)[::-1]]
            except KeyError:
                pass
            except Exception as e2:
                display(f"Familyid (2): {type(e2).__name__}", error=True)
        except Exception as e:
            display(f"Familyid (1): {type(e).__name__}", error=True)

        # FAM id

        self._individual.data.familiesid = []
        for family in self._individual.families:
            try:
                self._individual.data.familiesid += [families_table[tuple(family.spousesref)]]
            except KeyError:
                try:
                    self._individual.data.familiesid += [families_table[tuple(family.spousesref)[::-1]]]
                except Exception as e2:
                    display(f"Familiesid (2): {type(e2).__name__}", error=True)
                    self._individual.data.familiesid += [None]
            except Exception as e:
                display(f"Familiesid (1): {type(e).__name__}", error=True)
                self._individual.data.familiesid += [None]

    # -------------------------------------------------------------------------
    # url
    # -------------------------------------------------------------------------
    @property
    def url(self):
        """
        Property to get the url of the individual
        """
        return self._individual.data.url

    # -------------------------------------------------------------------------
    # notes
    # -------------------------------------------------------------------------
    @property
    def notes(self):
        """
        Property to get the list of notes of the individual
        """
        return self._individual.data.notes if 'notes' in self._individual.data else None

    # -------------------------------------------------------------------------
    # portrait
    # -------------------------------------------------------------------------
    @property
    def portrait(self):
        """
        Property to get the data of the individual
        """
        return self._individual.data

    # -------------------------------------------------------------------------
    # parentsref
    # -------------------------------------------------------------------------
    @property
    def parentsref(self):
        """
        Property to get the list of parents' reference of the individual
        """
        return self._individual.parentsref

    # -------------------------------------------------------------------------
    # spousesref
    # -------------------------------------------------------------------------
    @property
    def spousesref(self):
        """
        Property to get the list of spouses' reference of the individual
        """
        return [item for sublist in [family.spousesref for family in self._individual.families] for item in sublist]

    # -------------------------------------------------------------------------
    # childsref
    # -------------------------------------------------------------------------
    @property
    def childsref(self):
        """
        Property to get the list of childs' reference of the individual
        """
        return [item for sublist in [family.childsref for family in self._individual.families] for item in sublist]

    # -------------------------------------------------------------------------
    # siblingsref
    # -------------------------------------------------------------------------
    @property
    def siblingsref(self):
        """
        Property to get the list of siblings' reference of the individual
        """
        return self._individual.siblingsref

    # -------------------------------------------------------------------------
    # families
    # -------------------------------------------------------------------------
    @property
    def families(self):
        """
        Property to get the list of families of the individual
        """
        return self._individual.families

    # -------------------------------------------------------------------------
    # html
    # -------------------------------------------------------------------------
    @property
    def html(self):
        """
        Property to get the html of the individual
        """
        if hasattr(self, '_parser'):
            return self._parser.html
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
        if self._individual.data.gedcomid:
            text += f"0 @{self._individual.data.gedcomid}@ INDI\n"

        names = {'name': "", "first": "", "last": ""}

        if 'firstname' in self._individual.data:
            names['name'] = self._individual.data['firstname']
            names["first"] = f"2 GIVN {self._individual.data['firstname']}\n"

        if 'lastname' in self._individual.data:
            names['name'] += f" /{self._individual.data['lastname']}/"
            names["last"] = f"2 SURN {self._individual.data['lastname']}\n"

        if len(names['name']) > 0:
            names['name'] = f"1 NAME {names['name'].strip()}\n"

        text += ''.join([name for key, name in names.items() if len(name) > 0])

        if 'sex' in self._individual.data:
            text += f"1 SEX {self._individual.data['sex']}\n"

        events = [('BIRT', 'birth'), ('DEAT', 'death'), ('BURI', 'burial')]
        text += self._event(self._individual.data, events)

        # family

        for family in self._individual.data.familiesid:
            if family:
                text += f"1 FAMS @{family}@\n"

        if self._individual.data.familyid is not None:
            text += f"1 FAMC @{self._individual.data.familyid}@\n"

        # notes

        if 'notes' in self._individual.data:
            for note in self._individual.data.notes:
                note = note.splitlines()
                first = True
                for line in note:
                    wrapped_line = textwrap.wrap(line, width=200)
                    if len(wrapped_line) == 0:
                        wrapped_line = ['']

                    if first:
                        text += f"1 NOTE {wrapped_line[0]}\n"
                    else:
                        text += f"2 CONT {wrapped_line[0]}\n"

                    wrapped_line.pop(0)

                    for sub_line in wrapped_line:
                        text += f"2 CONC {sub_line}\n"

                    first = False

        if self._individual.data.url is not None:
            text += f"1 SOUR {self._individual.data.url}\n"

        # sources

        text += "\n"

        return text

    # -------------------------------------------------------------------------
    # print
    # -------------------------------------------------------------------------

    def print(self, short=False):
        """
        Function to print the individual
        """

        if short:
            p = self._shorten_event(self._individual.data.copy(), ['birth', 'death', 'baptem', 'burial'])
            p = self._shorten_data(p.copy())

            if 'notes' in p:
                if len(p['notes']) > 0:
                    p['notes'] = len(p['notes'])
                else:
                    del p['notes']

        else:
            p = self._individual.copy()

        display(p, title=f"Individual: {self._individual.ref}")

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

    def __init__(self, max_level, ascendants, spouses, descendants):

        self._parser = None

        self._repositories = {}

        self._individuals = {}
        self._max_level = max_level
        self._ascendants = ascendants
        self._spouses = spouses
        self._descendants = descendants

        self._families = {}

    # -------------------------------------------------------------------------
    # add_individual
    # -------------------------------------------------------------------------

    def add_individual(self, url, force=False, level=0):
        """
        Function to add one individual to the genealogy
        """

        parsed_url = urlparse(url)
        repository = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))

        if 'geneanet' in url:
            if not isinstance(self._parser, Geneanet):
                self._parser = Geneanet()
        else:
            self._parser = None

        ref = self._parser.clean_query(url)

        if ref not in self._individuals:

            # Parser

            # Source

            if repository not in self._repositories:

                self._repositories[repository] = self._parser.informations(url)

                if datetime.strptime(self._repositories[repository]['lastchange'], "%d %b %Y").date() > datetime.today().date():
                    force = True

            # Individual

            self._individuals[ref] = GIndividual(self._parser, url, force)

            # Families

            try:
                new_families = self._individuals[ref].families
                for family in new_families:
                    if tuple(family.spousesref) not in self._families and tuple(family.spousesref)[::-1] not in self._families:
                        self._families[tuple(family.spousesref)] = family
            except Exception as e:
                display(f"Add individual: {type(e).__name__}", error=True)

            # Ascendants descendants and childs

            if level < self._max_level:

                if self._ascendants:
                    for parent in self._individuals[ref].parentsref:
                        parent = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', parent, ''))
                        self.add_individual(parent, force, level + 1)

                if self._spouses:
                    for spouse in self._individuals[ref].spousesref:
                        spouse = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', spouse, ''))
                        self.add_individual(spouse, force, level + 1)

                if self._descendants:
                    for child in self._individuals[ref].childsref:
                        child = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', child, ''))
                        self.add_individual(child, force, level + 1)

    # -------------------------------------------------------------------------
    # gedcom
    # -------------------------------------------------------------------------

    def gedcom(self):
        """
        Function to get the GEDCOM of the genealogy
        """

        display("")
        display("GEDCOM", level=2)

        # set gedcom id
        individuals_table = {key: f"I{index + 1:05d}" for index, key in enumerate(self._individuals)}
        families_table = {key: f"F{index + 1:05d}" for index, key in enumerate(self._families)}

        for individual in self._individuals.values():
            individual.setids(individuals_table, families_table)

        for family in self._families.values():
            family.setids(individuals_table, families_table)

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
        gedcom = gedcom + f"2 DATE {datetime.today().strftime('%d %b %Y').upper()}\n"
        gedcom = gedcom + "\n"

        # REPO
        idx = 0
        for informations in self._repositories.values():

            gedcom = gedcom + f"0 @R{idx:05d}@ REPO\n"
            if 'author' in informations:
                gedcom = gedcom + f"1 NAME {informations.author}\n"
            if 'lastchange' in informations:
                gedcom = gedcom + "1 CHAN\n"
                gedcom = gedcom + f"2 DATE {informations.lastchange}\n"
            gedcom = gedcom + f"1 WWW {informations.url}\n"
            # gedcom = gedcom + f"1 TYPE {informations.source}\n"
            gedcom = gedcom + "\n"

            idx = idx + 1

        # INDI with SOUR and NOTE

        for individual in self._individuals.values():
            gedcom = gedcom + individual.gedcom

        # FAM

        for family in self._families.values():
            gedcom = gedcom + family.gedcom

        # TAILER

        gedcom = gedcom + "0 TRLR"

        if self._parser:
            self._parser.save()

        return gedcom

    # -------------------------------------------------------------------------
    # print
    # -------------------------------------------------------------------------

    def print(self, all_details=False):
        """
        Function to print the genealogy
        """

        if all_details:
            display(self._individuals, title=f"{len(self._individuals)} Individuals")

            display(self._families, title=f"{len(self._families)} Families")

        for individual in self._individuals.values():
            individual.print(short=False)

        for family in self._families.values():
            family.print(short=False)

    # -------------------------------------------------------------------------
    # html
    # -------------------------------------------------------------------------

    def html(self, url):
        """
        Function to retrieve html for one individual
        """

        try:
            return [v.html for v in self._individuals.values() if v.url == url][0]
        except Exception as e:
            display(f"Genealogy html: {type(e).__name__}", error=True)
            return ""
