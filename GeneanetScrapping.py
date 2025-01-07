#!/usr/bin/python3
#
# GeneanetScrapping
#
# Copyright (C) 2020  Bruno Cornec
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

# $Id: $

"""
Geneanet Import Tool
Export into GEDCOM persons from Geneanet
"""
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
from lxml import html, etree
import argparse
from datetime import datetime
import uuid
import urllib
import babel, babel.dates

import logging
LOG = logging.getLogger("GeneanetForGramps")

handler = logging.FileHandler('info.log')
LOG.addHandler(handler)

#-------------------------------------------------------------------------
#
# Global variables
#
#-------------------------------------------------------------------------

####db = None
gname = None

verbosity = 0
force = False
ascendants = False
descendants = False
spouses = False
LEVEL = 2

ROOTURL = 'https://gw.geneanet.org/'

PROFIL = None
##progress = None

TIMEOUT = 5

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

    global locale

    if verbosity >= 3:
        print(_("datetab received:"),datetab)

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

    if (datetab[0][0:2] == _("about")[0:2] or datetab[0][0:2] ==  _("after")[0:2] or datetab[0][0:2] ==  _("before")[0:2]) and (len(datetab) == 2):
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

    # -------------------------------------------------------------------------
    # _smartcopy: copy Geneanet to Gramps
    # -------------------------------------------------------------------------
    def _smartcopy(self,attr):
        '''
        Smart Copying an attribute from geneanet (g_ attrs) into attr
        Works for GPerson and GFamily
        '''
        if verbosity >= 3:
            print(_("Smart Copying Attributes"),attr)

        # By default do not copy as Gramps is the master reference
        scopy = False

        # Find the case where copy is to be done
        # Nothing yet
        if not self.__dict__[attr]:
            scopy = True

        # Empty field
        if self.__dict__[attr] and self.__dict__[attr] == "" and self.__dict__['g_'+attr] and self.__dict__['g_'+attr] != "":
            scopy = True

        # Force the copy
        if self.__dict__[attr] != self.__dict__['g_'+attr] and force:
            scopy = True

        # Managing sex, Gramps is always right except when unknown
        # Warn on conflict
        if attr == 'sex' and self.__dict__[attr] == 'U' and self.__dict__['g_'+attr] != 'U':
            scopy = True
            if (self.__dict__[attr] == 'F' and self.__dict__['g_'+attr] == 'M') \
            or (self.__dict__[attr] == 'M' and self.__dict__['g_'+attr] == 'F'):
                if verbosity >= 1:
                    print(_("WARNING: Gender conflict between Geneanet (%s) and Gramps (%s), keeping Gramps value")%(self.__dict__['g_'+attr],self.__dict__[attr]))
                scopy = False

        if attr == 'lastname' and self.__dict__[attr] != self.__dict__['g_'+attr]:
            if verbosity >= 1 and self.__dict__[attr] != "":
                print(_("WARNING: Lastname conflict between Geneanet (%s) and Gramps (%s), keeping Gramps value")%(self.__dict__['g_'+attr],self.__dict__[attr]))
        if attr == 'lastname' and self.__dict__[attr] == "":
            scopy = True

        if attr == 'firstname' and self.__dict__[attr] != self.__dict__['g_'+attr]:
            if verbosity >= 1 and self.__dict__[attr] != "":
                print(_("WARNING: Firstname conflict between Geneanet (%s) and Gramps (%s), keeping Gramps value")%(self.__dict__['g_'+attr],self.__dict__[attr]))
        if attr == 'firstname' and self.__dict__[attr] == "":
            scopy = True

        # Copy only if code is more precise
        match = re.search(r'code$', attr)
        if match:
            if not self.__dict__[attr]:
                scopy = True
            else:
                if not self.__dict__['g_'+attr]:
                    scopy = False
                else:
                    try:
                        if int(self.__dict__[attr]) < int(self.__dict__['g_'+attr]):
                            scopy = True
                    except ValueError:
                        LOG.debug(str(self.__dict__[attr]))

        # Copy only if date is more precise
        match = re.search(r'date$', attr)
        if match:
            if not self.__dict__[attr]:
                scopy = True
            else:
                if not self.__dict__['g_'+attr]:
                    scopy = False
                else:
                    if self.__dict__[attr] == "" and self.__dict__['g_'+attr] != "":
                        scopy = True
                    elif self.__dict__[attr] < self.__dict__['g_'+attr]:
                        scopy = True

        if scopy:
            if verbosity >= 2:
                print(_("Copying Person attribute %s (former value %s newer value %s)")%(attr, self.__dict__[attr],self.__dict__['g_'+attr]))

            self.__dict__[attr] = self.__dict__['g_'+attr]
        else:
            if verbosity >= 3:
                print(_("Not Copying Person attribute (%s, value %s) onto %s")%(attr, self.__dict__[attr],self.__dict__['g_'+attr]))

    # -------------------------------------------------------------------------
    # get_or_create_place: create place 
    # -------------------------------------------------------------------------
    def get_or_create_place(self,event,placename):
        '''
        Create Place for Events or get an existing one based on the name
        '''

        try:
            pl = event.get_place_handle()
        except:
            place = Place()
            return(place)

        if pl:
            try:
                place = db.get_place_from_handle(pl)
                if verbosity >= 2:
                    print(_("Reuse Place from Event:"), place.get_name().value)
            except:
                place = Place()
        else:
            if placename == None:
                place = Place()
                return(place)
            keep = None
            # Check whether our place already exists
            for handle in db.get_place_handles():
                pl = db.get_place_from_handle(handle)
                explace = pl.get_name().value
                if verbosity >= 4:
                    LOG.debug((("search for "), str(placename),str(explace)))
                if str(explace) == str(placename):
                    keep = pl
                    break
            if keep == None:
                if verbosity >= 2:
                    print(_("Create Place:"), placename)
                place = Place()
            else:
                if verbosity >= 2:
                    print(_("Reuse existing Place:"), placename)
                place = keep
        return(place)

    # -------------------------------------------------------------------------
    # get_or_create_event: create event 
    # -------------------------------------------------------------------------
    def get_or_create_event(self, gobj, attr, tran, timelog):
        '''
        Create Birth and Death Events for a person
        and Marriage Events for a family or get an existing one
        self is GPerson or GFamily
        gobj is a gramps object Person or Family
        '''

        if config.get('preferences.tag-on-import'):
            pref = config.get('preferences.tag-on-import-format')
            default_tag = time.strftime(pref)
        else:
            default_tag= timelog
        event = None
        # Manages name indirection for person
        if gobj.__class__.__name__ == 'Person':
            role = EventRoleType.PRIMARY
            func = getattr(gobj,'get_'+attr+'_ref')
            reffunc = func()
            if reffunc:
                event = db.get_event_from_handle(reffunc.ref)
                if verbosity >= 2:
                    print(_("Existing ")+attr+_(" Event"))
        elif gobj.__class__.__name__ == 'Family':
            role = EventRoleType.FAMILY
            if attr == 'marriage':
                marev = None
                for event_ref in gobj.get_event_ref_list():
                    event = db.get_event_from_handle(event_ref.ref)
                    if (event.get_type() == EventType.MARRIAGE and
                            (event_ref.get_role() == EventRoleType.FAMILY or
                             event_ref.get_role() == EventRoleType.PRIMARY)):
                        marev = event
                if marev:
                    event = marev
                    if verbosity >= 2:
                        print(_("Existing ")+attr+_(" Event"))
        else:
            print(_("ERROR: Unable to handle class %s in get_or_create_all_event")%(gobj.__class__.__name__))

        if event is None:
            event = Event()
            uptype = getattr(EventType,attr.upper())
            event.set_type(EventType(uptype))
            try:
                event.set_description(str(self.title[0]))
            except:
                event.set_description(_("No title"))
            if db.get_tag_from_name(default_tag):
               tag = db.get_tag_from_name(default_tag)
            else:
               tag = Tag()
               tag.set_name(default_tag)
            db.add_tag(tag, tran)
            event.add_tag(tag.handle)
            db.add_event(event, tran)

            eventref = EventRef()
            eventref.set_role(role)
            eventref.set_reference_handle(event.get_handle())
            if gobj.__class__.__name__ == 'Person':
                func = getattr(gobj,'set_'+attr+'_ref')
                reffunc = func(eventref)
                db.commit_event(event, tran)
                gobj.add_tag(tag.handle)
                db.commit_person(gobj, tran)
            elif gobj.__class__.__name__ == 'Family':
                eventref.set_role(EventRoleType.FAMILY)
                gobj.add_event_ref(eventref)
                if attr == 'marriage':
                    gobj.set_relationship(FamilyRelType(FamilyRelType.MARRIED))
                db.commit_event(event, tran)
                gobj.add_tag(tag.handle)
                db.commit_family(gobj, tran)
            if verbosity >= 2:
                print(_("Creating ")+attr+" ("+str(uptype)+") "+_("Event"))

        if self.__dict__[attr+'date'] \
            or self.__dict__[attr+'place'] \
            or self.__dict__[attr+'placecode'] :
            # Get or create the event date
            date = event.get_date_object()
            if self.__dict__[attr+'date']:
                idx = 0
                mod = Date.MOD_NONE
                if self.__dict__[attr+'date'][0:2] == _("about")[0:2]:
                    idx = 1
                    mod = Date.MOD_ABOUT
                elif self.__dict__[attr+'date'][0:2] == _("before")[0:2]:
                    idx = 1
                    mod = Date.MOD_BEFORE
                elif self.__dict__[attr+'date'][0:2] == _("after")[0:2]:
                    idx = 1
                    mod = Date.MOD_AFTER
                # Only in case of french language analysis
                elif self.__dict__[attr+'date'][0:2] == _("in")[0:2]:
                    idx = 1
                else:
                    pass
                if idx == 1:
                    # we need to removed the first word
                    string = self.__dict__[attr+'date'].split(' ',1)[1]
                else:
                    string = self.__dict__[attr+'date']
                # ISO string, put in a tuple, reversed
                tab = string.split('-')
                if len(tab) == 3:
                    date.set_yr_mon_day(int(tab[0]),int(tab[1]),int(tab[2]))
                elif len(tab) == 2:
                    date.set_yr_mon_day(int(tab[0]),int(tab[1]),0)
                elif len(tab) == 1:
                    date.set_year(int(tab[0]))
                elif len(tab) == 0:
                    print(_("WARNING: Trying to affect an empty date"))
                    pass
                else:
                    print(_("WARNING: Trying to affect an extra numbered date"))
                    pass
                if mod:
                    date.set_modifier(mod)
            if verbosity >= 2 and self.__dict__[attr+'date']:
                print(_("Update ")+attr+_(" Date to ")+self.__dict__[attr+'date'])
            event.set_date_object(date)
            db.commit_event(event, tran)

            if self.__dict__[attr+'place'] \
                or self.__dict__[attr+'placecode'] :
                if self.__dict__[attr+'place']:
                    placename = self.__dict__[attr+'place']
                else:
                    placename = ""
                place = self.get_or_create_place(event, placename)
                # TODO: Here we overwrite any existing value.
                # Check whether that can be a problem
                place.set_name(PlaceName(value=placename))
                if self.__dict__[attr+'placecode']:
                    place.set_code(self.__dict__[attr+'placecode'])
                place_tag = _('place from geneanet')
                if db.get_tag_from_name(place_tag):
                    ptag = db.get_tag_from_name(place_tag)
                else:
                    ptag = Tag()
                    ptag.set_name(place_tag)
                db.add_tag(ptag, tran)
                place.add_tag(ptag.handle)
                db.add_place(place, tran)
                event.set_place_handle(place.get_handle())
                db.commit_event(event, tran)

        db.commit_event(event, tran)
        return

    # -------------------------------------------------------------------------
    # get_gramps_date
    # -------------------------------------------------------------------------
    def get_gramps_date(self, evttype):
        '''
        Give back the date of the event related to the GPerson or GFamily
        as a string ISO formated
        '''

        if verbosity >= 4:
            print(_("EventType: %d")%(evttype))

        if not self:
            return(None)

        if evttype == EventType.BIRTH:
            ref = self.grampsp.get_birth_ref()
        elif evttype == EventType.DEATH:
            ref = self.grampsp.get_death_ref()
        elif evttype == EventType.MARRIAGE:
            eventref = None
            for eventref in self.family.get_event_ref_list():
                event = db.get_event_from_handle(eventref.ref)
                if (event.get_type() == EventType.MARRIAGE
                    and (eventref.get_role() == EventRoleType.FAMILY
                    or eventref.get_role() == EventRoleType.PRIMARY)):
                        break
            ref = eventref
        else:
            print(_("Didn't find a known EventType: "),evttype)
            return(None)

        if ref:
            if verbosity >= 4:
                print(_("Ref:"),ref)
            try:
                event = db.get_event_from_handle(ref.ref)
            except:
                print(_("Didn't find a known ref for this ref date: "),ref)
                return(None)
            if event:
                if verbosity >= 4:
                    print(_("Event")+":",event)
                date = event.get_date_object()
                moddate = date.get_modifier()
                tab = date.get_dmy()
                if verbosity >= 4:
                    print(_("Found date: "),tab)
                if len(tab) == 3:
                    tab = date.get_ymd()
                    if verbosity >= 4:
                        print(_("Found date2: "),tab)
                    ret = format_iso(tab)
                else:
                    ret = format_noniso(tab)
                if moddate == Date.MOD_BEFORE:
                    pref = _("before")+" "
                elif moddate == Date.MOD_AFTER:
                    pref = _("after")+" "
                elif moddate == Date.MOD_ABOUT:
                    pref = _("about")+" "
                else:
                    pref = ""
                if verbosity >= 3:
                    print(_("Returned date: ")+pref+ret)
                return(pref+ret)
            else:
                return(None)
        else:
            return(None)

#-------------------------------------------------------------------------
#
# GFamily class
#
#-------------------------------------------------------------------------

class GFamily(GBase):
    '''
    Family as seen by Gramps and Geneanet
    '''
    def __init__(self,father,mother):

        display(_("GFamily::__init__ - Creating family: %s %s - %s %s")%(father.firstname, father.lastname, mother.firstname, mother.lastname), level=2, verbose=1 )

        # The 2 GPersons parents in this family should exist
        # and properties filled before we create the family
        # Gramps properties
        self.title = ""
        self.marriagedate = None
        self.marriageplace = None
        self.marriageplacecode = None
        self.gid = None
        # Pointer to the Gramps Family instance
        self.family = None
        # Geneanet properties
        self.g_marriagedate = None
        self.g_marriageplace = None
        self.g_marriageplacecode = None
        self.g_childref = []

        self.url = father.url
        if self.url == "":
            self.url = mother.url
        # TODO: what if father or mother is None
        self.father = father
        self.mother = mother

    # -------------------------------------------------------------------------
    # create_grampsf: create family in Gramps DB
    # -------------------------------------------------------------------------
    def create_grampsf(self):
        '''
        Create a Family in Gramps and return it
        '''
        display(_("GFamily::grampsf"), level=2, verbose=1 )

        with DbTxn("Geneanet import", db) as tran:
            grampsf = Family()
            db.add_family(grampsf, tran)
            self.gid = grampsf.gramps_id
            self.family = grampsf
            if verbosity >= 2:
                print(_("Create new Gramps Family: ")+self.gid)

    # -------------------------------------------------------------------------
    # find_grampsf: find family in Gramps DB
    # -------------------------------------------------------------------------
    def find_grampsf(self):
        '''
        Find a Family in Gramps and return it
        '''
        display(_("GFamily::find_grampsf - Look for a Gramps Family"), level=2, verbose=1 )

        f = None
        ids = db.get_family_gramps_ids()
        for i in ids:
            f = db.get_family_from_gid(i)
            display(_("Analysing Gramps Family ")+f.gramps_id, verbose=2)
            # Do these people already form a family
            father = None
            fh = f.get_father_handle()
            if fh:
                father = db.get_person_from_handle(fh)
            mother = None
            mh = f.get_mother_handle()
            if mh:
                mother = db.get_person_from_handle(mh)
            if verbosity >= 3:
                if not father:
                    fgid = None
                else:
                    fgid = father.gramps_id
                if not fgid:
                    fgid = "None"
                sfgid = self.father.gid
                if not sfgid:
                    sfgid = "None"
                display(_("Check father ids: ")+fgid+_(" vs ")+sfgid, verbose=2)
                if not mother:
                    mgid = None
                else:
                    mgid = mother.gramps_id
                if not mgid:
                    mgid = "None"
                smgid = self.mother.gid
                if not smgid:
                    smgid = "None"
                display(_("Check mother ids: ")+mgid+_(" vs ")+smgid, verbose=2)
            if self.father and father and father.gramps_id == self.father.gid \
                and self.mother and mother and mother.gramps_id == self.mother.gid:
                return(f)
            #TODO: What about preexisting families not created in this run ?
        return(None)

    # -------------------------------------------------------------------------
    # from_geneanet: initiate GFamily from Geneanet
    # -------------------------------------------------------------------------
    def from_geneanet(self):
        '''
        Initiate the GFamily from Geneanet data
        '''
        display(_("GFamily::from_geneanet - Initiate the GFamily from Geneanet data"), level=2, verbose=1 )

        # Once we get the right spouses, then we can have the marriage info
        idx = 0
        for sr in self.father.spouseref:
            display(_("Comparing sr %s to %s (idx: %d)")%(sr,self.mother.url,idx), verbose=2)
            if sr == self.mother.url:
                display(_("Spouse %s found (idx: %d)")%(sr,idx), verbose=2)
                break
            idx = idx + 1

        if idx < len(self.father.spouseref):
            # We found one
            try:
                self.g_marriagedate = self.father.marriagedate[idx]
                self.g_marriageplace = self.father.marriageplace[idx]
                self.g_marriageplacecode = self.father.marriageplacecode[idx]
            except:
                pass

            try:
                for c in self.father.childref[idx]:
                    self.g_childref.append(c)
            except:
                pass
            

        if self.g_marriagedate and self.g_marriageplace and self.g_marriageplacecode:
            display(_("Geneanet Marriage found the %s at %s (%s)")%(self.g_marriagedate,self.g_marriageplace,self.g_marriageplacecode), verbose=2)


    # -------------------------------------------------------------------------
    # from_gedcom: initiate GFamily from GEDCOM
    # -------------------------------------------------------------------------
    def from_gedcom(self,gid):
        '''
        Initiate the GFamily from GEDCOM data
        '''
        display(_("GFamily::from_gedcom - Calling from_gedcom with gid: %s")%(gid), level=2, verbose=1 )

        # If our gid was already setup and we didn't pass one
        if not gid and self.gid:
            gid = self.gid

        display(_("Now gid is: %s")%(gid), verbose=2)

        found = None
        try:
            found = db.get_family_from_gid(gid)
            self.gid = gid
            self.family = found
            display(_("Existing gid of a Gramps Family: %s")%(self.gid), verbose=2)
        except:
            display(_("WARNING: Unable to retrieve id %s from the gramps db %s")%(gid,gname), verbose=1)

        if not found:
            # If we don't know which family this is, try to find it in Gramps
            # This supposes that Geneanet data are already present in GFamily
            self.family = self.find_grampsf()
            if self.family:
                display(_("Found an existing Gramps family ")+self.family.gramps_id, verbose=2)
                self.gid = self.family.gramps_id
            # And if we haven't found it, create it in gramps
            if self.family == None:
                self.create_grampsf()

        if self.family:
            self.marriagedate = self.get_gramps_date(EventType.MARRIAGE)
            if self.marriagedate == "":
                self.marriagedate = None
            for eventref in self.family.get_event_ref_list():
                event = db.get_event_from_handle(eventref.ref)
                if (event.get_type() == EventType.MARRIAGE
                and (eventref.get_role() == EventRoleType.FAMILY
                or eventref.get_role() == EventRoleType.PRIMARY)):
                    place = self.get_or_create_place(event,None)
                    self.marriageplace = place.get_name().value
                    self.marriageplacecode = place.get_code()
                    break

            if verbosity >= 2:
                if self.marriagedate and self.marriageplace and self.marriageplacecode:
                    display(_("Gramps Marriage found the %s at %s (%s)")%(self.marriagedate,self.marriageplace,self.marriageplacecode), verbose=2)

    # -------------------------------------------------------------------------
    # to_gedcom: copy GFamily from Geneanet to Gramps DB
    # -------------------------------------------------------------------------
    def to_gedcom(self):
        '''
        '''
        display(_("GFamily::to_gedcom"), level=2, verbose=1 )

        # Smart copy from Geneanet to Gramps inside GFamily
        self.smartcopy()
        with DbTxn("Geneanet import", db) as tran:
            # When it's not the case create the family
            if self.family == None:
                self.family = Family()
                db.add_family(self.family, tran)

            try:
                grampsp0 = db.get_person_from_gid(self.father.gid)
            except:
                display(_("No father for this family"), verbose=2)
                grampsp0 = None

            if grampsp0:
                try:
                    self.family.set_father_handle(grampsp0.get_handle())
                except:
                    display(_("Can't affect father to the family"), verbose=2)

                db.commit_family(self.family, tran)
                grampsp0.add_family_handle(self.family.get_handle())
                db.commit_person(grampsp0, tran)

            try:
                grampsp1 = db.get_person_from_gid(self.mother.gid)
            except:
                display(_("No mother for this family"), verbose=2)
                grampsp1 = None

            if grampsp1:
                try:
                    self.family.set_mother_handle(grampsp1.get_handle())
                except:
                    display(_("Can't affect mother to the family"), verbose=2)

                db.commit_family(self.family, tran)
                grampsp1.add_family_handle(self.family.get_handle())
                db.commit_person(grampsp1, tran)

            # Now celebrate the marriage ! (if needed)
            timelog = _('marriage from Geneanet')
            self.get_or_create_event(self.family, 'marriage', tran, timelog)

    # -------------------------------------------------------------------------
    # smartcopy: copy GFamily 
    # -------------------------------------------------------------------------
    def smartcopy(self):
        '''
        Smart Copying GFamily
        '''
        if verbosity >= 2:
            print(_("Smart Copying Family"))
        self._smartcopy("marriagedate")
        self._smartcopy("marriageplace")
        self._smartcopy("marriageplacecode")

    # -------------------------------------------------------------------------
    # add_child: add a child GPerson in GFamily 
    # -------------------------------------------------------------------------
    def add_child(self, child):
        '''
        Adds a child GPerson child to the GFamily
        '''
        display(_("GFamily::add_child"), level=2, verbose=1 )

        found = None
        i = 0
        # Avoid handling already processed children in Gramps
        for cr in self.family.get_child_ref_list():
            c = db.get_person_from_handle(cr.ref)
            if c.gramps_id == child.gid:
                found = child
                display(_("Child already existing : ")+child.firstname+" "+child.lastname, verbose=1)
                break
            # Ensure that the child is part of the family

        if not found:
            if child:
                display(_("Adding child: ")+child.firstname+" "+child.lastname, verbose=2)
                childref = ChildRef()
                if child.grampsp:
                    try:
                        childref.set_reference_handle(child.grampsp.get_handle())
                    except:
                        display(_("No handle for this child"), verbose=2)
                    self.family.add_child_ref(childref)

                    with DbTxn("Geneanet import", db) as tran:
                        db.commit_family(self.family, tran)
                        child.grampsp.add_parent_family_handle(self.family.get_handle())
                        db.commit_person(child.grampsp, tran)

    # -------------------------------------------------------------------------
    # recurse_children: analyze recursively the children of the GFamily 
    # -------------------------------------------------------------------------
    def recurse_children(self,level):
        '''
        analyze recursively the children of the GFamily passed in parameter
        '''
        display(_("GFamily::recurse_children"), level=2, verbose=1 )

        try:
            cpt = len(self.g_childref)
        except:
            display(_("Stopping exploration as there are no more children for family ")+self.fater.firstname+" "+self.father.lastname+" - "+self.mother.firstname+" "+self.mother.lastname, verbose=1)
            return

        loop = False
        # Recurse while we have children urls and level not reached
        if level <= LEVEL and (cpt > 0):
            loop = True
            level = level + 1

            if not self.family:
                display(_("WARNING: No family found whereas there should be one :-("), verbose=1)
                return

            # Create a GPerson from all children mentioned in Geneanet
            for c in self.g_childref:
                child = geneanet_to_gedcom(None,level-1,None,c)
                display(_("=> Recursion on the child of ")+self.father.lastname+' - '+self.mother.lastname+': '+child.firstname+' '+child.lastname, verbose=2)
                self.add_child(child)

                fam = []
                if spouses:
                     fam = child.add_spouses(level)
                     if ascendants:
                         for f in fam:
                             if child.sex == 'M':
                                 f.mother.recurse_parents(level-1)
                             if child.sex == 'F':
                                 f.father.recurse_parents(level-1)
                     if descendants:
                         for f in fam:
                             f.recurse_children(level)

                display(_("=> End of recursion on the child of ")+self.father.lastname+' - '+self.mother.lastname+': '+child.firstname+' '+child.lastname, verbose=2)

        if not loop:
            if cpt == 0:
                display(_("Stopping exploration for family ")+self.father.firstname+" "+self.father.lastname+' - '+self.mother.firstname+" "+self.mother.lastname+_(" as there are no more children"), verbose=1)
                return

            if level > LEVEL:
                display(_("Stopping exploration for family ")+self.father.firstname+" "+self.father.lastname+' - '+self.mother.firstname+" "+self.mother.lastname+_(" as we reached level ")+str(level), verbose=1)
        return

#----------------------------------------------------------------------------------------------------------------------------------
#
# GPerson class
#
#----------------------------------------------------------------------------------------------------------------------------------

class GPerson(GBase):
    '''
    Generic Person common between GEDCOM and Geneanet
    '''
    def __init__(self,level):

        display(_("GPerson::__init__ - Initialize Person at level %d")%(level), level=2, verbose=1 )

        # Counter
        self.level = level

        # GEDCOM
        self.gid = None
        self.gedcomp = None

        # Father and Mother and Spouses GPersons
        self.father = None
        self.mother = None
        self.spouse = []

        # GFamilies
        self.family = []

        # Geneanet
        self.url = ""
        #self.html = ""
        self.ref = ""

        self.g_firstname = ""
        self.g_lastname = ""
        self.g_sex = 'U'
        self.g_birthdate = None
        self.g_birthplace = None
        ##self.g_birthplacecode = None
        self.g_deathdate = None
        self.g_deathplace = None
        ##self.g_deathplacecode = None

        self.fatherref = ""
        self.motherref = ""
        self.spouseref = []
        self.childref = []
        self.marriagedate = []
        self.marriageplace = []
        ##self.marriageplacecode = []
        self.divorcedate = []

        self.user = "lburais" #storage and privacy issues
        self.password = "twenty" #storage and privacy issues

    # -------------------------------------------------------------------------
    # smartcopy: copy Geneanet to GEDCOM
    # -------------------------------------------------------------------------
    def smartcopy(self):
        '''
        Smart Copying GPerson
        '''
        if verbosity >= 2:
            print(_("Smart Copying Person"),self.gid)
        self._smartcopy("firstname")
        self._smartcopy("lastname")
        self._smartcopy("sex")
        self._smartcopy("birthdate")
        self._smartcopy("birthplace")
        self._smartcopy("birthplacecode")
        self._smartcopy("deathdate")
        self._smartcopy("deathplace")
        self._smartcopy("deathplacecode")

    # -------------------------------------------------------------------------
    # from_geneanet
    # -------------------------------------------------------------------------

    def from_geneanet(self, purl):
        ''' Use XPath to retrieve the details of a person
        Used example from https://gist.github.com/IanHopkinson/ad45831a2fb73f537a79
        and doc from https://www.w3schools.com/xml/xpath_axes.asp
        and https://docs.python-guide.org/scenarios/scrape/

        lxml can return _ElementUnicodeResult instead of str so cast
        '''
        
        # Needed as Geneanet returned relative links
        # https://edmundmartin.com
        from random import choice
 
        desktop_agents = ['Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
                 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
                 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
                 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/602.2.14 (KHTML, like Gecko) Version/10.0.1 Safari/602.2.14',
                 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.71 Safari/537.36',
                 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36',
                 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36',
                 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.71 Safari/537.36',
                 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
                 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:50.0) Gecko/20100101 Firefox/50.0']
 
        def random_headers():
            return {'User-Agent': choice(desktop_agents),'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'}
 
        headers = random_headers()

        display(_("Purl: %s")%(purl), verbose=2)

        if not purl:
            return()

        display(_("GPerson::from_geneanet - page considered: %s")%(purl), level=2, verbose=1 )

        import requests 
        s = requests.session()
        s.auth = (self.user, self.password)
        header = s.head(purl)

        page = s.get(purl)
        if page.status_code == "302":
            self.connexion_geneanet(self.user, self.password)

        display( _("Return code: %s")%(page.status_code), error=True, verbose=3)

        display( _("[Requests]: We failed to reach the server at %s")%(purl), error=True)

        if page.ok and page.status_code != "200" or "201":
            try:
                tree = html.fromstring(str(page.content))
            except XMLSyntaxError:
                pass
            import urllib.request, ssl
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                page = urllib.request.urlopen(purl, context=ctx)
            except urllib.error.HTTPError:
                LOG.debug(purl)
            tree = html.fromstring(page.read())

            self.url = purl
            self.title = tree.xpath('//title/text()')
            # Wait after a Genanet request to be fair with the site
            # between 2 and 7 seconds
            time.sleep(random.randint(2,7))

            # -----------------------------------------------------------------
            # ref
            # -----------------------------------------------------------------
            pu = urllib.parse.urlparse(purl)
            self.ref = pu.path[1:] + "?" + pu.query
            display("Référence: %s"%(self.ref), verbose=1)

            # -----------------------------------------------------------------
            # firstname & lastname
            # -----------------------------------------------------------------
            try:
                names = tree.xpath('//div[@id="perso"]//a/text()')
                self.g_firstname = str(names[0]).title()
                self.g_lastname = str(names[1]).title()
            except:
                pass

            display("Niveau: %d"%(self.level), verbose=1)
            display("Nom: %s %s"%(self.g_firstname,self.g_lastname), verbose=1)

            # -----------------------------------------------------------------
            # sex
            # -----------------------------------------------------------------
            try:
                # Should return M or F
                sex = tree.xpath('//div[@id="person-title"]//img/attribute::alt')
                self.g_sex = sex[0]
                # Seems we have a french codification on the site
                if sex[0] == 'H':
                    self.g_sex = 'M'
            except:
                self.sex = 'U'

            display("Sexe: %s"%(self.g_sex), verbose=1)

            # -----------------------------------------------------------------
            # birth
            # -----------------------------------------------------------------
            try:
                bstring = '//li[contains(., "Né")]/text()'
                birth = tree.xpath(bstring)
            except:
                birth = [""]

            display("==> birth: %s"%(birth), verbose=2)

            try:
                ld = convert_date(birth[0].split('-')[0].split()[1:])
                self.g_birthdate = format_ca(ld)

                display("Date de naissance: %s"%(self.g_birthdate), verbose=1)
            except:
                self.birthdate = None
                
            try:
                bp = str(birth[0].split(' - ')[1])
                self.g_birthplace = bp.partition("à l'âge")[0]

                display("Lieu de naissance: %s"%(self.g_birthplace), verbose=1)
            except:
                if len(birth) < 1:
                    pass
                else:
                    self.g_birthplace = str(uuid.uuid3(uuid.NAMESPACE_URL, self.url))

            # -----------------------------------------------------------------
            # death
            # -----------------------------------------------------------------
            try:
                dstring = '//li[contains(., "Décédé")]/text()'
                death = tree.xpath(dstring)
            except:
                death = [""]

            display("==> death: %s"%(death), verbose=2)

            try:
                ld = convert_date(death[0].split('-')[0].split()[1:])
                self.g_deathdate = format_ca(ld)

                display("Date de décès: %s"%(self.g_deathdate), verbose=1)
            except:
                self.g_deathdate = None

            try:
                dp = str(death[0].split(' - ')[1])
                self.g_deathplace = dp.partition("à l'âge")[0]

                display("Lieu de décès: %s"%(self.g_deathplace), verbose=1)
            except:
                if len(death) < 1:
                    pass
                else:
                    self.g_deathplace = str(uuid.uuid3(uuid.NAMESPACE_URL, self.url))

            # -----------------------------------------------------------------
            # parents
            # -----------------------------------------------------------------
            try:
                # sometime parents are using circle, sometimes disc !
                # parents = tree.xpath('//ul[not(descendant-or-self::*[@class="fiche_union"])]//li[@style="vertical-align:middle;list-style-type:disc" or @style="vertical-align:middle;list-style-type:circle"]//a/attribute::href')
                parents = tree.xpath('//ul[not(descendant-or-self::*[@class="fiche_union"])]//li[@style="vertical-align:middle;list-style-type:disc" or @style="vertical-align:middle;list-style-type:circle"]')
                parents = tree.xpath('//ul[not(@class="fiche_union")]//li[@style="vertical-align:middle;list-style-type:disc" or @style="vertical-align:middle;list-style-type:circle"]')

                display("---------------------------", verbose=1)

            except:
                parents = []

            self.fref = ""
            self.mref = ""
            prefl = []

            for p in parents:
                display('==> parent text', p.xpath('text()'), verbose=2)

                for a in p.xpath('a'):
                    pref = a.xpath('attribute::href')[0]

                    display("Référence du parent: %s"%(pref), verbose=1)

                    try:
                        pname = a.xpath('text()')[0].title()
                    except:
                        pname = str(uuid.uuid3(uuid.NAMESPACE_URL, self.url))
                        # if pname is ? ? then go to next one

                    display("Nom du parent: %s"%(pname), verbose=1)

                else:
                    pass
                prefl.append(str(pref))

            try:
                self.fref = prefl[0]
            except:
                self.fref = ""

            try:
                self.mref = prefl[1]
            except:
                self.mref = ""

            # -----------------------------------------------------------------
            # spouses
            # -----------------------------------------------------------------
            try:
                spouses = tree.xpath('//ul[@class="fiche_union"]/li')
                
                display("==> spouses: %s"%(spouses), verbose=2 )

            except:
                LOG.debug(str(tree.xpath('//ul[@class="fiche_union"]/li')))
                spouses = []

            s = 0
            sname = []
            sref = []
            marriage = []

            for spouse in spouses:
                display("---------------------------", verbose=1)

                # -------------------------------------------------------------
                # spouse
                # -------------------------------------------------------------
                for a in spouse.xpath('a'):
                    try:
                        ref = a.xpath('attribute::href')[0]

                        display("Conjoint %d ref: %s"%(s, ref), verbose=1)
                    except:
                        ref = None

                    try:
                        sname.append(str(a.xpath('text()')[0]).title())

                        display("Nom du conjoint: %s"%(sname[s]), verbose=1)
                    except:
                        sname.append("")

                    try:
                        sref.append(str(a.xpath('attribute::href')[0]))
                        display("Référence du conjoint: %s"%(purl+sref[s]), verbose=1)
                    except:
                        sref.append("")

                    try:
                        self.spouseref.append(sref[s])
                    except:
                        continue

                # -------------------------------------------------------------
                # marriage
                # -------------------------------------------------------------
                try:
                    marriage.append(str(spouse.xpath('em/text()')[0]))
                except:
                    marriage.append(None)
                    
                try:
                    ld = convert_date(marriage[s].split(',')[0].split()[1:])
                    self.marriagedate.append(format_ca(ld))

                    display("Date du marriage: %s"%(ld), verbose=1)
                except:
                    self.marriagedate.append(None)

                try:
                    self.marriageplace.append(str(marriage[0].split(',')[1][1:]).title())
                    
                    display("Lieu du marriage:"%(self.marriageplace[0]), verbose=1)
                except:
                    self.marriageplace.append(str(marriage[0]))

                # -------------------------------------------------------------
                # divorce
                # -------------------------------------------------------------

                # -------------------------------------------------------------
                # childs
                # -------------------------------------------------------------
                cnum = 0
                clist = []
                for c in spouse.xpath('ul/li/a[1]'):
                    display("-------------", verbose=1)

                    try:
                        cref = c.xpath('attribute::href')[0]

                        display("Enfant %d ref: %s"%(cnum, cref), verbose=1)
                    except:
                        cref = None

                    try:
                        cname = c.xpath('text()')[0].title()
                        display("Nom de l'enfant: %s"%(cname), verbose=1)
                    except:
                        pass

                    clist.append(cref)
                    cnum = cnum + 1

                self.childref.append(clist)

                s = s + 1
                # End spouse loop

            display("-----------------------------------------------------------", verbose=1)

        else:
            display("We failed to be ok with the server", error=True)
     
    # -------------------------------------------------------------------------
    # create_gedcom
    # -------------------------------------------------------------------------
    def create_gedcom(self):
        '''
        Create a Person in GEDCOM and return it
        '''

        display(_("GPerson::create_gedcom"), level=2, verbose=1 )

        individual = gedcom.individual()
        individual.set_source( self.ref )

        self.gedcomp = individual
        self.gid = individual.id
        display(_("Create new GEDCOM Person: ")+self.gid+' ('+self.g_firstname+' '+self.g_lastname+')'+' ['+self.gedcomp.source+']', verbose=1)

    # -------------------------------------------------------------------------
    # find_gedcom
    # -------------------------------------------------------------------------
    def find_gedcom(self):
        '''
        Find a Person from GEDCOM and return it
        The parameter precises the relationship with our person
        '''
        display(_("GPerson::find_gedcom"), level=2, verbose=1 )

        p = None
        for ind in gedcom.individuals:
            pprint(ind)
            if ind.source != self.url:
                continue
            else:
                p = ind

        if p:
            # person found in GEDCOM

            # Assumption it's the right one
            self.gedcomp = p

            try:
                firstname, lastname = self.gedcomp.name
            except:
                pass

            bd = self.gedcomp.birth
            bd = format_year(bd)

            dd = self.gedcomp.death
            dd = format_year(dd)

            if verbosity >= 3:
                print(_("DEBUG: firstname: ")+firstname+_(" vs g_firstname: ")+self.g_firstname)
                print(_("DEBUG: lastname: ")+lastname+_(" vs g_lastname: ")+self.g_lastname)
                if not bd:
                    pbd = "None"
                else:
                    pbd = bd
                if not dd:
                    pdd = "None"
                else:
                    pdd = dd
                if not self.g_birthdate:
                    g_pbd = "None"
                else:
                    g_pbd = self.g_birthdate
                if not self.g_deathdate:
                    g_pdd = "None"
                else:
                    g_pdd = self.g_deathdate
                print(_("DEBUG: bd: ")+pbd+_(" vs g_bd: ")+g_pbd)
                print(_("DEBUG: dd: ")+pdd+_(" vs g_dd: ")+g_pdd)

            if firstname != self.g_firstname or lastname != self.g_lastname:
                # it's not the right person finally
                self.gedcomp = None
                return

            if not bd and not dd and not self.g_birthdate and not self.g_deathdate:
                # we skip a person for which we have no date at all
                # this may create duplicates, but is the best apparoach
                self.gedcomp = None
                return
                
            if bd == self.g_birthdate or dd == self.g_deathdate:
                self.gid = p.gid

                if verbosity >= 2:
                    print(_("Found a GEDCOM Person: ")+self.g_firstname+' '+self.g_lastname+ " ("+self.gid+")")

    # -------------------------------------------------------------------------
    # to_gedcom
    # -------------------------------------------------------------------------
    def to_gedcom(self):
        '''
        Push into GEDCOM the GPerson
        '''
        display(_("GPerson::to_gedcom"), level=2, verbose=1 )

        # def smartcopy( tag, level, value ):
        #     try:
        #         node = self.gedcomp[tag]
        #         node.value = value
        #     except IndexError:
        #         self.gedcomp.add_child_element(gedcom.element(tag, level=level, value=value))

        self.gedcomp.add_child_element(gedcom.element('NAME', level=1, value=(self.g_firstname + " /" + self.g_lastname + "/")))

        self.gedcomp.add_child_element(gedcom.element('SEX', level=1, value=self.g_sex))

        bd = gedcom.element('BIRT', level=1, value="")
        bd.add_child_element(gedcom.element('DATE', level=1, value=self.g_birthdate))
        bd.add_child_element(gedcom.element('PLAC', level=1, value=self.g_birthplace))

        self.gedcomp.add_child_element(bd)

        dd = gedcom.element('DEAT', level=1, value="")
        dd.add_child_element(gedcom.element('DATE', level=1, value=self.g_deathdate))
        dd.add_child_element(gedcom.element('PLAC', level=1, value=self.g_deathplace))

        self.gedcomp.add_child_element(dd)

    # -------------------------------------------------------------------------
    # from_gedcom
    # -------------------------------------------------------------------------

    def from_gedcom(self, gid):
        '''
        Fill a GPerson with its GEDCOM data
        '''
        display(_("GPerson::from_gedcom - gid: %s")%(gid), level=2, verbose=1 )

        # If our gid was already setup and we didn't pass one
        if not gid and self.gid:
            gid = self.gid

        display(_("Now gid is: %s")%(gid), verbose=2)

        # parse gedcom.individuals to get the one with geneanet relative url (aka. source)
        found = None
        for ind in gedcom.individuals:
            if ind.source != gid:
                continue
            found = ind
            self.gid = gid
            self.gedcomp = found

        if found:
            if self.gid:
                display(_("Existing GEDCOM Person: %s")%(self.gid), verbose=1)
        else:
            display(_("WARNING: Unable to retrieve id %s from the GEDCOM %s") %(gid, gname), verbose=1)
            # If we don't know who this is, try to find it in Gramps
            # This supposes that Geneanet data are already present in GPerson
            self.find_gedcom()
            # And if we haven't found it, create it in gramps
            if self.gedcomp == None:
                self.create_gedcom()

        # Retrieve name

        try:
            self.firstname, self.lastname = self.gedcomp.name
        except:
            self.firstname, self.lastname = ( None, None )

        display(_("===> GEDCOM Name of %s: %s %s")%(self.gid, self.firstname, self.lastname), verbose=1)

        # Retrieve birth

        try:
            bd = self.gedcomp.birth
            if bd:
                display(_("Birth: %s")%bd, verbose=2)
                self.birthdate = bd.date
                self.birthplace = bd.place
        except:
            display("Pas d'information sur la naissance", verbose=1)

        # Retrieve death

        try:
            dd = self.gedcomp.death
            if dd:
                display(_("Death: %s")%dd, verbose=2)
                self.deathdate = dd.date
                self.deathplace = dd.place
        except:
            display("Pas d'information sur le décès", verbose=1)

        # Deal with the parents now, as they necessarily exist

        self.father = GPerson(self.level+1)
        self.mother = GPerson(self.level+1)

        try:
            # find father from the family
            self.father.gedcomp = self.gedcomp.father
            if self.father.gedcomp:
                display("Nom du père: %s"%(self.father.gedcomp.name), verbose=1)
                self.father.gid = self.father.gedcomp.id

            # find mother from the family
            self.mother.gedcomp = self.gedcomp.mother
            if self.mother.gedcomp:
                display("Nom de la mère: %s"%(self.mother.gedcomp.name))
                self.mother.gid = self.mother.gedcomp.id

        except:
            display(_("NOTE: Unable to retrieve family for id %s")%(self.gid), verbose=1)

    # -------------------------------------------------------------------------
    # add_spouses
    # -------------------------------------------------------------------------

    def add_spouses(self,level):
        '''
        Add all spouses for this person, with corresponding families
        returns all the families created in a list
        '''

        display(_("GPerson::add_spouses"), level=2, verbose=1 )

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
                    # Create a GFamily with them and do a Geaneanet to GEDCOM for it
                    display(_("=> Initialize Family of %s %s - %s %s")%(self.firstname,self.lastname,spouse.firstname,spouse.lastname), verbose=1)
                if self.g_sex == 'M':
                    f = GFamily(self, spouse)
                elif self.g_sex == 'F':
                    f = GFamily(spouse, self)
                else:
                    display(_("Unable to Initialize Family of ")+self.firstname+" "+self.lastname+_(" sex unknown"), verbose=1)
                    break

                f.from_geneanet()
                f.from_gedcom(f.gid)
                f.to_gedcom()
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

        display(_("GPerson::recurse_parents"), level=2, verbose=1 )

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
                    print(_("=> Recursing on the parents of ")+self.father.firstname+" "+self.father.lastname)
                self.father.recurse_parents(level)

                if verbosity >= 2:
                    print(_("=> End of recursion on the parents of ")+self.father.firstname+" "+self.father.lastname)

            if self.mother:
                geneanet_to_gedcom(self.mother, level, self.mother.gid, self.motherref)
                if self.father:
                    self.father.spouse.append(self.mother)
                if verbosity >= 2:
                    print(_("=> Recursing on the mother of ")+self.mother.firstname+" "+self.mother.lastname)
                self.mother.recurse_parents(level)

                if verbosity >= 2:
                    print(_("=> End of recursing on the mother of ")+self.mother.firstname+" "+self.mother.lastname)

            # Create a GFamily with them and do a Geaneanet to Gramps for it
            if verbosity >= 2:
                print(_("=> Initialize Parents Family of ")+self.firstname+" "+self.lastname)
            f = GFamily(self.father, self.mother)
            f.from_geneanet()
            f.from_gedcom(f.gid)
            f.to_gedcom()
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
                    print(_("Stopping exploration as we reached level ")+str(level))
            else:
                if verbosity >= 1:
                    print(_("Stopping exploration as there are no more parents"))
        return

    # -------------------------------------------------------------------------
    # connexion_geneanet
    # -------------------------------------------------------------------------
    def connexion_geneanet(self, user, password):
        '''
        Login and password set for geneanet servers
        '''

        display(_("GPerson::connexion_geneanet"), level=2, verbose=1 )

        import requests

        headers = {'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36' }
        r = requests.get("https://www.geneanet.org/connexion/"
             ,headers=headers
            )
        
        pos1 = r.text.find('name="_csrf_token" value="')
        pos1 = pos1 + len('name="_csrf_token" value="')
        pos2 = r.text.find('"', pos1)
        csrf = r.text[pos1:pos2]
        cooks = r.cookies
        headers.update({'referer':'https://www.geneanet.org/connexion/'})
        headers.update({'authority':'www.geneanet.org'})
        r = requests.post(
                 "https://www.geneanet.org/connexion/login_check"
                ,data={
                      "_username": user
                     ,"_password": password
                     ,"_submit": ""
                     ,"_remember_me": "1"
                     ,"_csrf_token": csrf
                     }
               ,allow_redirects=False
               ,cookies=cooks
               ,headers=headers
             )

###################################################################################################################################
# geneanet_to_gedcom
###################################################################################################################################

def geneanet_to_gedcom(p, level, gid, url):
    '''
    Function to create a person from Geneanet into GEDCOM
    '''

    display(_("geneanet_to_gedcom - Person: %s, Level: %d, GID: %s, url: %s")%(p,level,gid,url), level=2, verbose=1 )

    # Create the Person coming from Geneanet
    if not p:
        p = GPerson(level)

    p.from_geneanet(url)

    # Filling the Person from GEDCOM
    # Done after so we can try to find it in Gramps with the Geneanet data
    p.from_gedcom(gid)

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
# Persons
###################################################################################################################################

class Persons():

    def __init__(self, url):

        display("Persons::__init__ - build tree from %s"%(url), level=2, verbose=1 )

        self.persons = []

        

        # Counter
        self.level = level

        # GEDCOM
        self.gid = None
        self.gedcomp = None

        # Father and Mother and Spouses GPersons
        self.father = None
        self.mother = None
        self.spouse = []

        # GFamilies
        self.family = []

        # Geneanet
        self.url = ""
        #self.html = ""
        self.ref = ""

        self.g_firstname = ""
        self.g_lastname = ""
        self.g_sex = 'U'
        self.g_birthdate = None
        self.g_birthplace = None
        ##self.g_birthplacecode = None
        self.g_deathdate = None
        self.g_deathplace = None
        ##self.g_deathplacecode = None

        self.fatherref = ""
        self.motherref = ""
        self.spouseref = []
        self.childref = []
        self.marriagedate = []
        self.marriageplace = []
        ##self.marriageplacecode = []
        self.divorcedate = []

        self.user = "lburais" #storage and privacy issues
        self.password = "twenty" #storage and privacy issues
    
###################################################################################################################################
# Person
###################################################################################################################################

class Person():

    def __init__(self, url):

        display("Person::__init__", level=2, verbose=1 )

        self.persons = []

        # Counter
        self.level = level

        # GEDCOM
        self.gedcom_id = None
        self.gedcom_individual = None

        # Geneanet
        self.url = url

        self.tree = get_geneanet( url )

        parse_geneanet( self.tree )

        self.geneanet_id = ""


        # Father and Mother and Spouses GPersons
        self.father = None
        self.mother = None
        self.spouse = []

        # GFamilies
        self.family = []

        # Geneanet
        self.ref = ""

        self.g_firstname = ""
        self.g_lastname = ""
        self.g_sex = 'U'
        self.g_birthdate = None
        self.g_birthplace = None
        ##self.g_birthplacecode = None
        self.g_deathdate = None
        self.g_deathplace = None
        ##self.g_deathplacecode = None

        self.fatherref = ""
        self.motherref = ""
        self.spouseref = []
        self.childref = []
        self.marriagedate = []
        self.marriageplace = []
        ##self.marriageplacecode = []
        self.divorcedate = []

        self.user = "lburais" #storage and privacy issues
        self.password = "twenty" #storage and privacy issues

    def parse_geneanet( self ):
        return

# -------------------------------------------------------------------------
# connexion_geneanet
# -------------------------------------------------------------------------
def connexion_geneanet(user, password):
    '''
    Login and password set for geneanet servers
    '''

    display(_("connexion_geneanet"), level=2, verbose=1 )

    import requests

    headers = {'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36' }
    r = requests.get( "https://www.geneanet.org/connexion/" ,headers=headers )
    
    pos1 = r.text.find('name="_csrf_token" value="')
    pos1 = pos1 + len('name="_csrf_token" value="')
    pos2 = r.text.find('"', pos1)
    csrf = r.text[pos1:pos2]
    cooks = r.cookies
    headers.update({'referer':'https://www.geneanet.org/connexion/'})
    headers.update({'authority':'www.geneanet.org'})
    r = requests.post( "https://www.geneanet.org/connexion/login_check"
            ,data={
                    "_username": user
                    ,"_password": password
                    ,"_submit": ""
                    ,"_remember_me": "1"
                    ,"_csrf_token": csrf
                    }
            ,allow_redirects=False
            ,cookies=cooks
            ,headers=headers
            )

# -------------------------------------------------------------------------
# get_geneanet
# -------------------------------------------------------------------------
def get_geneanet( url ):
    ''' Use XPath to retrieve the details of a person
    Used example from https://gist.github.com/IanHopkinson/ad45831a2fb73f537a79
    and doc from https://www.w3schools.com/xml/xpath_axes.asp
    and https://docs.python-guide.org/scenarios/scrape/

    lxml can return _ElementUnicodeResult instead of str so cast
    '''
    
    # Needed as Geneanet returned relative links
    # https://edmundmartin.com
    from random import choice

    tree = None

    desktop_agents = ['Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/602.2.14 (KHTML, like Gecko) Version/10.0.1 Safari/602.2.14',
                'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.71 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36',
                'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.71 Safari/537.36',
                'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:50.0) Gecko/20100101 Firefox/50.0']

    def random_headers():
        return {'User-Agent': choice(desktop_agents),'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'}

    headers = random_headers()

    display(_("url: %s")%(url), verbose=2)

    if not url:
        return None

    display(_("get_geneanet - page considered: %s")%(url), level=2, verbose=1 )

    import requests 
    s = requests.session()
    s.auth = (self.user, self.password)
    header = s.head(url)

    page = s.get(url)
    if page.status_code == "302":
        connexion_geneanet(user, password)

    display( _("Return code: %s")%(page.status_code), error=True, verbose=3)

    display( _("[Requests]: We failed to reach the server at %s")%(url), error=True)

    if page.ok and page.status_code != "200" or "201":
        try:
            tree = html.fromstring(str(page.content))
        except XMLSyntaxError:
            pass

        import urllib.request, ssl
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            page = urllib.request.urlopen(purl, context=ctx)
        except urllib.error.HTTPError:
            LOG.debug(purl)
        tree = html.fromstring(page.read())

    return tree

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

    display( _("GeneanetScrapping"), level=1 )

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
        print(_("Please provide a person to search for"))
        return -1
    else:
        purl = args.searchedperson

        # set fr language
        queries = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(purl).query))
        if 'lang' in queries:
            if queries['lang'] == 'fr':
                pass
            else:
                purl = purl.replace( "&", "&lang=fr" )
        else:
            purl = purl.replace( "lang=" + queries['lang'], "lang=fr" )

    gname = args.gedcomfile
    verbosity = args.verbosity
    force = args.force
    ascendants = args.ascendants
    descendants = args.descendants
    spouses = args.spouses
    LEVEL = args.level

    if gname == None:
        print(_("Please provide a gedcom file name to write to"))
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
        print(_("WARNING: Force mode activated"))
        time.sleep(TIMEOUT)

    # Create the first Person

    gp = geneanet_to_gedcom(None, 0, None, purl)

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
    gedcom.save(gname)

    sys.exit(0)


if __name__ == '__main__':
    main()

