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

TIMEOUT = 5

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

        if verbosity >= 1:
            print(_("Creating GFamily: ")+father.firstname+" "+father.lastname+" - "+mother.firstname+" "+mother.lastname)
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
        if verbosity >= 2:
            print(_("Look for a Gramps Family"))
        f = None
        ids = db.get_family_gramps_ids()
        for i in ids:
            f = db.get_family_from_gedcom_id(i)
            if verbosity >= 3:
                print(_("Analysing Gramps Family ")+f.gramps_id)
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
                print(_("Check father ids: ")+fgid+_(" vs ")+sfgid)
                if not mother:
                    mgid = None
                else:
                    mgid = mother.gramps_id
                if not mgid:
                    mgid = "None"
                smgid = self.mother.gid
                if not smgid:
                    smgid = "None"
                print(_("Check mother ids: ")+mgid+_(" vs ")+smgid)
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
        # Once we get the right spouses, then we can have the marriage info
        idx = 0
        for sr in self.father.spouseref:
            if verbosity >= 3:
                print(_("Comparing sr %s to %s (idx: %d)")%(sr,self.mother.url,idx))
            if sr == self.mother.url:
                if verbosity >= 2:
                    print(_("Spouse %s found (idx: %d)")%(sr,idx))
                break
            idx = idx + 1

        if idx < len(self.father.spouseref):
            # We found one
            try:
                self.g_marriagedate = self.father.marriagedate[idx]
                self.g_marriageplace = self.father.marriageplace[idx]
                self.g_marriageplacecode = self.father.marriageplacecode[idx]
            except:
                LOG.debug('marriage, father and spouse(%s)' % idx)
            try:
                for c in self.father.childref[idx]:
                    LOG.info(c)
                    self.g_childref.append(c)
            except:
                LOG.debug('child, father and spouse(%s)' % idx)
            

        if self.g_marriagedate and self.g_marriageplace and self.g_marriageplacecode:
            if verbosity >= 2:
                print(_("Geneanet Marriage found the %s at %s (%s)")%(self.g_marriagedate,self.g_marriageplace,self.g_marriageplacecode))


    # -------------------------------------------------------------------------
    # from_gedcom: initiate GFamily from Gramps
    # -------------------------------------------------------------------------
    def from_gedcom(self,gid):
        '''
        Initiate the GFamily from GEDCOM data
        '''
        if verbosity >= 2:
            print(_("Calling from_gedcom with gid: %s")%(gid))

        # If our gid was already setup and we didn't pass one
        if not gid and self.gid:
            gid = self.gid

        if verbosity >= 2:
            print(_("Now gid is: %s")%(gid))

        found = None
        try:
            found = db.get_family_from_gedcom_id(gid)
            self.gid = gid
            self.family = found
            if verbosity >= 2:
                print(_("Existing gid of a Gramps Family: %s")%(self.gid))
        except:
            if verbosity >= 1:
                print(_("WARNING: Unable to retrieve id %s from the gramps db %s")%(gid,gname))

        if not found:
            # If we don't know which family this is, try to find it in Gramps
            # This supposes that Geneanet data are already present in GFamily
            self.family = self.find_grampsf()
            if self.family:
                if verbosity >= 2:
                    print(_("Found an existing Gramps family ")+self.family.gramps_id)
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
                    print(_("Gramps Marriage found the %s at %s (%s)")%(self.marriagedate,self.marriageplace,self.marriageplacecode))

    # -------------------------------------------------------------------------
    # to_gedcom: copy GFamily from Geneanet to Gramps DB
    # -------------------------------------------------------------------------
    def to_gedcom(self):
        '''
        '''
        # Smart copy from Geneanet to Gramps inside GFamily
        self.smartcopy()
        with DbTxn("Geneanet import", db) as tran:
            # When it's not the case create the family
            if self.family == None:
                self.family = Family()
                db.add_family(self.family, tran)

            try:
                grampsp0 = db.get_person_from_gedcom_id(self.father.gid)
            except:
                if verbosity >= 2:
                    print(_("No father for this family"))
                grampsp0 = None

            if grampsp0:
                try:
                    self.family.set_father_handle(grampsp0.get_handle())
                except:
                    if verbosity >= 2:
                        print(_("Can't affect father to the family"))

                db.commit_family(self.family, tran)
                grampsp0.add_family_handle(self.family.get_handle())
                db.commit_person(grampsp0, tran)

            try:
                grampsp1 = db.get_person_from_gedcom_id(self.mother.gid)
            except:
                if verbosity >= 2:
                    print(_("No mother for this family"))
                grampsp1 = None

            if grampsp1:
                try:
                    self.family.set_mother_handle(grampsp1.get_handle())
                except:
                    if verbosity >= 2:
                        print(_("Can't affect mother to the family"))

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
        found = None
        i = 0
        # Avoid handling already processed children in Gramps
        for cr in self.family.get_child_ref_list():
            c = db.get_person_from_handle(cr.ref)
            if c.gramps_id == child.gid:
                found = child
                if verbosity >= 1:
                    print(_("Child already existing : ")+child.firstname+" "+child.lastname)
                break
            # Ensure that the child is part of the family

        if not found:
            if child:
                if verbosity >= 2:
                    print(_("Adding child: ")+child.firstname+" "+child.lastname)
                childref = ChildRef()
                if child.grampsp:
                    try:
                        childref.set_reference_handle(child.grampsp.get_handle())
                    except:
                        if verbosity >= 2:
                            print(_("No handle for this child"))
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
        try:
            cpt = len(self.g_childref)
        except:
            if verbosity >= 1:
                print(_("Stopping exploration as there are no more children for family ")+self.fater.firstname+" "+self.father.lastname+" - "+self.mother.firstname+" "+self.mother.lastname)
            return
        loop = False
        # Recurse while we have children urls and level not reached
        if level <= LEVEL and (cpt > 0):
            loop = True
            level = level + 1

            if not self.family:
                print(_("WARNING: No family found whereas there should be one :-("))
                return

            # Create a GPerson from all children mentioned in Geneanet
            for c in self.g_childref:
                child = geneanet_to_gedcom(None,level-1,None,c)
                if verbosity >= 2:
                    print(_("=> Recursion on the child of ")+self.father.lastname+' - '+self.mother.lastname+': '+child.firstname+' '+child.lastname)
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

                if verbosity >= 2:
                    print(_("=> End of recursion on the child of ")+self.father.lastname+' - '+self.mother.lastname+': '+child.firstname+' '+child.lastname)

        if not loop:
            if cpt == 0:
                if verbosity >= 1:
                    print(_("Stopping exploration for family ")+self.father.firstname+" "+self.father.lastname+' - '+self.mother.firstname+" "+self.mother.lastname+_(" as there are no more children"))
                return

            if level > LEVEL:
                if verbosity >= 1:
                    print(_("Stopping exploration for family ")+self.father.firstname+" "+self.father.lastname+' - '+self.mother.firstname+" "+self.mother.lastname+_(" as we reached level ")+str(level))
        return

#-------------------------------------------------------------------------
#
# GPerson class
#
#-------------------------------------------------------------------------

class GPerson(GBase):
    '''
    Generic Person common between Gramps and Geneanet
    '''
    def __init__(self,level):
        if verbosity >= 3:
            print(_("Initialize Person at level %d")%(level))
        # Counter
        self.level = level
        # GEDCOM
        self.gedcom_id = None
        self.gedcom_individual = None
        # Father and Mother and Spouses GPersons
        self.father = None
        self.mother = None
        self.spouse = []

        # GFamilies
        self.family = []

        # Geneanet
        self.url = ""
        self.html = ""
        self.ref = ""
        self.firstname = ""
        self.lastname = ""
        self.sex = 'U'
        self.birthdate = None
        self.birthplace = None
        ##self.birthplacecode = None
        self.deathdate = None
        self.deathplace = None
        ##self.deathplacecode = None
        ##self.parents = []
        ##self.spouses = []

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
    # smartcopy: copy Geneanet to Gramps
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
    # from_geneanet: parse Geneanet
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

        if verbosity >= 3:
            print(_("Purl:"),purl)
        if not purl:
            return()

        if verbosity >= 1:
            print("######################################################################################################################")
            print(_("Page considered:"), purl)

        import requests 
        s = requests.session()
        s.auth = (self.user, self.password)
        header = s.head(purl)
        LOG.info('header %s' % header)
        page = s.get(purl)
        if page.status_code == "302":
            LOG.debug('Need to log in?')
            self.connexion(self.user, self.password)
        LOG.info('content %s' % str(page.content))
        LOG.info('text %s' % page.text)
        LOG.info('type %s' % page.headers['Content-Type'])
        LOG.debug('body %s'% page.request.body)
        if verbosity >= 3:
            print(_("Return code:"), page.status_code)
        LOG.debug("How to handle HTML page on non linux environments?")
        print(_("[Requests]: We failed to reach the server at"), purl)
        LOG.info("Fallback, try via built-in urllib module")

        if page.ok and page.status_code != "200" or "201":
            try:
                tree = html.fromstring(str(page.content))
                LOG.info(str(page.content))
            except XMLSyntaxError:
                LOG.debug(_("Unable to perform HTML analysis"))
                # os.system('''wget "%(url)s"''' % {'url': purl})
            import urllib.request, ssl
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                page = urllib.request.urlopen(purl, context=ctx)
            except urllib.error.HTTPError:
                LOG.debug(purl)
            tree = html.fromstring(page.read())
            LOG.info(str(page))

            self.url = purl
            self.title = tree.xpath('//title/text()')
            LOG.debug((purl, self.title))
            # Wait after a Genanet request to be fair with the site
            # between 2 and 7 seconds
            time.sleep(random.randint(2,7))

            # -----------------------------------------------------------------
            # ref
            # -----------------------------------------------------------------
            pu = urllib.parse.urlparse(purl)
            self.ref = pu.path[1:] + "?" + pu.query

            # -----------------------------------------------------------------
            # firstname & lastname
            # -----------------------------------------------------------------
            try:
                names = tree.xpath('//div[@id="perso"]//a/text()')
                self.firstname = str(names[0]).title()
                self.lastname = str(names[1]).title()
            except:
                LOG.debug(names)
            if verbosity >= 1:
                print("Niveau: %d"%(self.level))
                print("Nom: %s %s"%(self.firstname,self.lastname))

            # -----------------------------------------------------------------
            # sex
            # -----------------------------------------------------------------
            try:
                # Should return M or F
                sex = tree.xpath('//div[@id="person-title"]//img/attribute::alt')
                self.sex = sex[0]
                # Seems we have a french codification on the site
                if sex[0] == 'H':
                    self.sex = 'M'
            except:
                LOG.debug(self.sex)
                self.sex = 'U'
            if verbosity >= 1:
                print("Sexe: %s"%(self.sex))

            # -----------------------------------------------------------------
            # birth
            # -----------------------------------------------------------------
            try:
                bstring = '//li[contains(., "Né")]/text()'
                birth = tree.xpath(bstring)
            except:
                birth = [""]
            if verbosity >= 2:
                print("==> birth: %s"%(birth))

            try:
                ld = convert_date(birth[0].split('-')[0].split()[1:])
                self.birthdate = format_ca(ld)
                if verbosity >= 1:
                    print("Date de naissance: %s"%(self.birthdate))
            except:
                LOG.debug('birth %s' % birth)
                self.birthdate = None
                
            try:
                bp = str(birth[0].split(' - ')[1])
                self.birthplace = bp.partition("à l'âge")[0]
                if verbosity >= 1:
                    print("Lieu de naissance: %s"%(self.birthplace))
            except:
                if len(birth) < 1:
                    pass
                else:
                    LOG.debug(str(birth[0]))
                    self.birthplace = str(uuid.uuid3(uuid.NAMESPACE_URL, self.url))

            # -----------------------------------------------------------------
            # death
            # -----------------------------------------------------------------
            try:
                dstring = '//li[contains(., "Décédé")]/text()'
                death = tree.xpath(dstring)
            except:
                death = [""]
            if verbosity >= 2:
                print("==> death: %s"%(death))

            try:
                ld = convert_date(death[0].split('-')[0].split()[1:])
                self.deathdate = format_ca(ld)
                if verbosity >= 1:
                    print("Date de décès: %s"%(self.deathdate))
            except:
                LOG.debug('death %s' % death)
                self.deathdate = None

            try:
                dp = str(death[0].split(' - ')[1])
                self.deathplace = dp.partition("à l'âge")[0]
                if verbosity >= 1:
                    print("Lieu de décès: %s"%(self.deathplace))
            except:
                if len(death) < 1:
                    pass
                else:
                    LOG.debug(str(death[0]))
                    self.deathplace = str(uuid.uuid3(uuid.NAMESPACE_URL, self.url))

            # -----------------------------------------------------------------
            # parents
            # -----------------------------------------------------------------
            try:
                # sometime parents are using circle, sometimes disc !
                # parents = tree.xpath('//ul[not(descendant-or-self::*[@class="fiche_union"])]//li[@style="vertical-align:middle;list-style-type:disc" or @style="vertical-align:middle;list-style-type:circle"]//a/attribute::href')
                parents = tree.xpath('//ul[not(descendant-or-self::*[@class="fiche_union"])]//li[@style="vertical-align:middle;list-style-type:disc" or @style="vertical-align:middle;list-style-type:circle"]')
                parents = tree.xpath('//ul[not(@class="fiche_union")]//li[@style="vertical-align:middle;list-style-type:disc" or @style="vertical-align:middle;list-style-type:circle"]')
                if verbosity >= 2:
                    print("==> parents: %s"%(parents) )

            except:
                LOG.debug(str(tree.xpath('//ul[not(descendant-or-self::*[@class="fiche_union"])]//')))
                parents = []

            self.fref = ""
            self.mref = ""
            prefl = []

            for p in parents:
                LOG.info(etree.tostring(p, method='xml', pretty_print=True))
                if verbosity >= 1:
                    print('==> parent text', p.xpath('text()'))
                LOG.info(p.text)

                for a in p.xpath('a'):
                    pref = a.xpath('attribute::href')[0]

                    if verbosity >= 1:
                        print("Référence du parent:", pref)

                    LOG.debug(pref)

                    try:
                        pname = a.xpath('text()')[0].title()
                        LOG.info(pname)
                    except:
                        pname = str(uuid.uuid3(uuid.NAMESPACE_URL, self.url))
                        LOG.debug(pname)
                        # if pname is ? ? then go to next one

                    if verbosity >= 1:
                        print("Nom du parent: %s"%(pname))

                else:
                    LOG.info(etree.tostring(p, method='html', pretty_print=False))
                    #LOG.debug('Failed to set parents %s' % p.text)
                prefl.append(str(pref))

            try:
                self.fref = prefl[0]
            except:
                LOG.debug('no ref for parent 1')
                self.fref = ""

            try:
                self.mref = prefl[1]
            except:
                LOG.debug('no ref for parent 2')
                self.mref = ""

            # -----------------------------------------------------------------
            # spouses
            # -----------------------------------------------------------------
            try:
                spouses = tree.xpath('//ul[@class="fiche_union"]/li')
                if verbosity >= 2:
                    print("==> spouses: %s"%(spouses) )
            except:
                LOG.debug(str(tree.xpath('//ul[@class="fiche_union"]/li')))
                spouses = []

            s = 0
            sname = []
            sref = []
            marriage = []

            for spouse in spouses:
                if verbosity >= 1:
                    print("---------------------------")
                # -------------------------------------------------------------
                # spouse
                # -------------------------------------------------------------
                for a in spouse.xpath('a'):
                    try:
                        ref = a.xpath('attribute::href')[0]
                        if verbosity >= 1:
                            print("Conjoint %d ref: %s"%(s, ref))
                    except:
                        ref = None
                        LOG.debug(str(a.xpath('attribute::href')))

                    try:
                        sname.append(str(a.xpath('text()')[0]).title())
                        if verbosity >= 1:
                            print("Nom du conjoint:", sname[s])
                    except:
                        sname.append("")

                    try:
                        sref.append(str(a.xpath('attribute::href')[0]))
                        if verbosity >= 1:
                            print("Référence du conjoint:", purl+sref[s])
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
                    if verbosity >= 1:
                        print(_("Married:"), ld)
                    self.marriagedate.append(format_ca(ld))
                except:
                    self.marriagedate.append(None)

                try:
                    self.marriageplace.append(str(marriage[0].split(',')[1][1:]).title())
                    if verbosity >= 1:
                        print(_("Married place:"), self.marriageplace[0])
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
                    if verbosity >= 1:
                        print("-------------")

                    try:
                        cref = c.xpath('attribute::href')[0]
                        if verbosity >= 1:
                            print("Enfant %d ref: %s"%(cnum, cref))
                    except:
                        cref = None
                        LOG.debug(str(a.xpath('attribute::href')))

                    try:
                        cname = c.xpath('text()')[0].title()
                        if verbosity >= 1:
                            print(_("Nom de l'enfant: %s")%(cname))
                    except:
                        cname = str(uuid.uuid3(uuid.NAMESPACE_URL, self.url))
                        LOG.debug(cname)

                    LOG.info(etree.tostring(c, method='xml', pretty_print=True))

                    clist.append(cref)
                    cnum = cnum + 1

                self.childref.append(clist)

                s = s + 1
                # End spouse loop
                LOG.info('clist %s' % clist)

            if verbosity >= 1:
                print("-----------------------------------------------------------")

        else:
            print(_("We failed to be ok with the server"))
     
    # -------------------------------------------------------------------------
    # connexion: Geneanet connexion
    # -------------------------------------------------------------------------
    def connexion(self, user, password):
        '''
        Login and password set for geneanet servers
        '''
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
        LOG.info(r.text)

    # -------------------------------------------------------------------------
    # create_person: 
    # -------------------------------------------------------------------------
    def create_person(self):
        '''
        Create a Person and return it
        '''

        individual = gedcom.individual()
        individual.set_source( self.url )

        self.gedcom_individual = individual
        self.gedcom_id = individual.id
        if verbosity >= 1:
            print(_("Create new GEDCOM Person: ")+self.gedcom_id+' ('+self.gedcom_individual.source+')')

    # -------------------------------------------------------------------------
    # find_person: find person from GEDCOM data
    # -------------------------------------------------------------------------
    def find_person(self):
        '''
        Find a Person and return it
        The parameter precises the relationship with our person
        '''
        person = gedcom.individuals()

        # for p in gedcom.individuals:
        #     if p. != self.url:
        #         continue
        p = None
        ids = db.get_person_gramps_ids()
        for i in ids:
            if verbosity >= 3:
                print(_("DEBUG: Looking after ")+i)
            p = db.get_person_from_gedcom_id(i)
            try:
                name = p.primary_name.get_name().split(', ')
            except:
                continue
            if len(name) == 0:
                continue
            elif len(name) == 1:
                name.append(None)
            if name[0]:
                lastname = name[0]
            else:
                lastname = ""
            if name[1]:
                firstname = name[1]
            else:
                firstname = ""
            # Assumption it's the right one
            self.grampsp = p
            bd = self.get_gramps_date(EventType.BIRTH)
            # Remove empty month/day if needed to compare below with just a year potentially
            bd = format_year(bd)
            dd = self.get_gramps_date(EventType.DEATH)
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
                self.grampsp = None
                continue
            if not bd and not dd and not self.g_birthdate and not self.g_deathdate:
                # we skip a person for which we have no date at all
                # this may create duplicates, but is the best apparoach
                self.grampsp = None
                continue
            if bd == self.g_birthdate or dd == self.g_deathdate:
                self.gid = p.gramps_id
                if verbosity >= 2:
                    print(_("Found a Gramps Person: ")+self.g_firstname+' '+self.g_lastname+ " ("+self.gid+")")
                # Found it we can exit
                break
            else:
                # still not found
                self.grampsp = None

    # -------------------------------------------------------------------------
    # to_gedcom
    # -------------------------------------------------------------------------
    def to_gedcom(self):
        '''
        Push into GEDCOM the GPerson
        '''

        return 

        def smartcopy( tag, level, value ):
            try:
                node = self.gedcom_individual[tag]
                node.value = value
            except IndexError:
                self.gedcom_individual.add_child_element(gedcom.element(tag, level=level, value=value))

        value = self.g_firstname + self.g_lastname
        smartcopy( 'NAME', 1, value )

        smartcopy( 'SEX', 1, self.g_sex )

        bd = gedcom.element('BIRT', level=1, value="")
        bd.add_child_element(gedcom.element('DATE', level=1, value=self.g_birthdate))
        bd.add_child_element(gedcom.element('PLAC', level=1, value=self.g_birthplace))
        self.gedcom_individual.add_child_element(bd)

        elements = {}
        elements += { "NAME": self.g_firstname + self.g_lastname}
        elements += { "SEX": self.g_sex}
        elements += { "BIRT": { "DATE": self.g_birthdate, "PLAC": self.g_birthplace }}
        elements += { "DEAT": { "DATE": self.g_deathdate, "PLAC": self.g_deathplace }}

        dd = gedcom.element('DEAT', level=1, value="")
        dd.add_child_element(gedcom.element('DATE', level=1, value=self.g_deathdate))
        dd.add_child_element(gedcom.element('PLAC', level=1, value=self.g_deathplace))
        self.gedcom_individual.add_child_element(dd)

        return

        with DbTxn("Geneanet import", db) as tran:
            db.disable_signals()
            grampsp = self.grampsp
            if not grampsp:
                if verbosity >= 2:
                    print(_("ERROR: Unable sync unknown Gramps Person"))
                return

            if self.sex == 'M':
                grampsp.set_gender(Person.MALE)
            elif self.sex == 'F':
                grampsp.set_gender(Person.FEMALE)
            else:
                grampsp.set_gender(Person.UNKNOWN)

            n = Name()
            n.set_type(NameType(NameType.BIRTH))
            n.set_first_name(self.firstname)
            s = n.get_primary_surname()
            s.set_surname(self.lastname)
            grampsp.set_primary_name(n)

            # We need to create events for Birth and Death
            for ev in ['birth', 'death']:
                timelog = _('event from Geneanet')
                self.get_or_create_event(grampsp, ev, tran, timelog)

            # Store the importation place as an Internet note
            if self.url != "":
                found = False
                for u in grampsp.get_url_list():
                    if u.get_type() == UrlType.WEB_HOME \
                    and u.get_path() == self.url:
                        found = True
                if not found:
                    url = Url()
                    try:
                        url.set_description(str(self.title[0]))
                    except:
                        url.set_description(_("Geneanet"))
                    url.set_type(UrlType.WEB_HOME)
                    url.set_path(self.url)
                    grampsp.add_url(url)

            db.commit_person(grampsp, tran)
            db.enable_signals()
            db.request_rebuild()

    # -------------------------------------------------------------------------
    # from_gedcom
    # -------------------------------------------------------------------------

    def from_gedcom(self, gid):
        '''
        Fill a GPerson with its GEDCOM data
        '''

        if verbosity >= 2:
            print(_("Calling from_gedcom with gid: %s")%(gid))

        # If our gid was already setup and we didn't pass one
        if not gid and self.gedcom_id:
            gid = self.gedcom_id

        if verbosity >= 3:
            print(_("Now gid is: %s")%(gid))

        # parse gedcom.individuals to get the one with geneanet url
        self.gedcom_individual = None
        for ind in gedcom.individuals:
            if ind.source != gid:
                continue
            self.gedcom_id = gid
            self.gedcom_individual = ind

        if self.gedcom_individual:
            if verbosity >= 2 and self.gedcom_id:
                print(_("Existing GEDCOM Person: %s")%(self.gid))
        else:
            self.create_person()

        try:
            self.firstname, self.lastname = self.gedcom_individual.name
        except:
            self.firstname, self.lastname = ( None, None )

        if verbosity >= 2:
            print(_("===> GEDCOM Name of %s: %s %s")%(self.gedcom_id, self.firstname, self.lastname))

        try:
            bd = self.gedcom_individual.birth
            if bd:
                if verbosity >= 2:
                    print(_("Birth:"),bd)
                self.birthdate = bd.date
                self.birthplace = bd.place
            else:
                if verbosity >= 2:
                    print(_("No Birth date"))
        except:
            if verbosity >= 1:
                print(_("WARNING: Unable to retrieve birth date for id %s")%(self.gedcom_id))

        try:
            dd = self.gedcom_individual.death
            if dd:
                if verbosity >= 2:
                    print(_("Death:"),dd)
                self.deathdate = dd.date
                self.deathplace = dd.place
            else:
                if verbosity >= 2:
                    print(_("No Death date"))
        except:
            if verbosity >= 1:
                print(_("WARNING: Unable to retrieve death date for id %s")%(self.gedcom_id))

        # Deal with the parents now, as they necessarily exist
        self.father = GPerson(self.level+1)
        self.mother = GPerson(self.level+1)

        return

# *********************************************************************************************************************
# *********************************************************************************************************************

        try:
            fh = self.grampsp.get_main_parents_family_handle()
            if fh:
                if verbosity >= 3:
                    print(_("Family:"),fh)
                fam = db.get_family_from_handle(fh)
                if fam:
                    if verbosity >= 3:
                        print(_("Family:"),fam)

                # find father from the family
                fh = fam.get_father_handle()
                if fh:
                    if verbosity >= 3:
                        print(_("Father H:"),fh)
                    father = db.get_person_from_handle(fh)
                    if father:
                        if verbosity >= 1:
                            print(_("Father name:"),father.primary_name.get_name())
                        self.father.gid = father.gramps_id

                # find mother from the family
                mh = fam.get_mother_handle()
                if mh:
                    if verbosity >= 3:
                        print(_("Mother H:"),mh)
                    mother = db.get_person_from_handle(mh)
                    if mother:
                        if verbosity >= 1:
                            print(_("Mother name:"),mother.primary_name.get_name())
                        self.mother.gid = mother.gramps_id

        except:
            if verbosity >= 1:
                print(_("NOTE: Unable to retrieve family for id %s")%(self.gid))

    # -------------------------------------------------------------------------
    # add_spouses
    # -------------------------------------------------------------------------

    def add_spouses(self,level):
        '''
        Add all spouses for this person, with corresponding families
        returns all the families created in a list
        '''
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
                    # Create a GFamily with them and do a Geaneanet to Gramps for it
                    if verbosity >= 2:
                        print(_("=> Initialize Family of ")+self.firstname+" "+self.lastname+" + "+spouse.firstname+" "+spouse.lastname)
                if self.sex == 'M':
                    f = GFamily(self, spouse)
                elif self.sex == 'F':
                    f = GFamily(spouse, self)
                else:
                    if verbosity >= 1:
                        print(_("Unable to Initialize Family of ")+self.firstname+" "+self.lastname+_(" sex unknown"))
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


###################################################################################################################################
# geneanet_to_gedcom
###################################################################################################################################

def geneanet_to_gedcom(p, level, gid, url):
    '''
    Function to create a person from Geneanet into GEDCOM
    '''

    # Create the Person coming from Geneanet
    if not p:
        p = GPerson(level)

    p.from_geneanet(url)

    import pprint
    pprint.pprint(vars(p))

    # Find this Person in GEDCOM
    # p.find_gedcom(url)

    # Filling the Person  from GEDCOM
    # Done after so we can try to find it in Gramps with the Geneanet data
    ##p.from_gedcom(p.url)

    # Check we point to the same person
    gid = None
    if gid != None:
        if (p.firstname != p.g_firstname or p.lastname != p.g_lastname) and (not force):
            # print(_("Gramps   person: %s %s")%(p.firstname,p.lastname))
            print(_("Geneanet person: %s %s")%(p.g_firstname,p.g_lastname))
            db.close()
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
            print(_("Gramps   person birth/death: %s / %s")%(p.birthdate,p.deathdate))
            print(_("Geneanet person birth/death: %s / %s")%(p.g_birthdate,p.g_deathdate))
            sys.exit(_("Do not continue without force"))

    # Copy from Geneanet into GEDCOM and commit
    p.to_gedcom()

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
        #purl = 'https://gw.geneanet.org/agnesy?lang=fr&pz=hugo+mathis&nz=renard&p=marie+sebastienne&n=helgouach'
        #purl = 'https://gw.geneanet.org/agnesy?lang=fr&n=queffelec&oc=17&p=marie+anne'
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
        print("Please provide a gedcom file name to write to")
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

