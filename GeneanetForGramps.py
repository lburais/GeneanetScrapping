#!/usr/bin/python3
#
# GeneanetForGramps
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

# $Id: $

"""
Geneanet Gramplet
Import into Gramps persons from Geneanet
"""
#-------------------------------------------------------------------------
#
# Standard Python Modules
#
#-------------------------------------------------------------------------
import os
import time
import io
import sys

#------------------------------------------------------------------------
#
# GTK modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk

from gramps.gen.plug import Gramplet
from gramps.gui.editors import EditPerson
from gramps.gen.errors import WindowActiveError, DatabaseError
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.datehandler import get_date

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

import logging
from gramps.gen.config import config
from gramps.gen.display.place import displayer as _pd
from gramps.gen.db import DbTxn
from gramps.gen.db.utils import open_database
from gramps.gen.dbstate import DbState
from gramps.cli.grampscli import CLIManager
from gramps.gen.lib import Person, Name, Surname, NameType, Event, EventType, Date, Place, EventRoleType, EventRef, PlaceName, Family, ChildRef
#from gramps.gen.utils.location import get_main_location
#from gramps.version import VERSION

LOG = logging.getLogger("geneanetforgedcom")

GENDER = ['F', 'H', 'I']
TRAN = None

# Events we manage
BIRTH = 0
DEATH = 1
MARRIAGE = 2

TIMEOUT = 5

LANGUAGES = {
    'cs' : 'Czech', 'da' : 'Danish','nl' : 'Dutch',
    'en' : 'English','eo' : 'Esperanto', 'fi' : 'Finnish',
    'fr' : 'French', 'de' : 'German', 'hu' : 'Hungarian',
    'it' : 'Italian', 'lt' : 'Latvian', 'lv' : 'Lithuanian',
    'no' : 'Norwegian', 'po' : 'Polish', 'pt' : 'Portuguese',
    'ro' : 'Romanian', 'sk' : 'Slovak', 'es' : 'Spanish',
    'sv' : 'Swedish', 'ru' : 'Russian',
    }

GRAMPLET_CONFIG_NAME = "geneanetforgramps"
CONFIG = config.register_manager("geneanetforgramps")

CONFIG.register("preferences.include_ascendants", True)
CONFIG.register("preferences.include_descendants", True)
CONFIG.register("preferences.include_spouse", True)
CONFIG.load()

from lxml import html
import requests
import argparse
from datetime import datetime

ROOTURL = 'https://gw.geneanet.org/'
LEVEL = 0
headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

parser = argparse.ArgumentParser(description="Import Geneanet subtrees into Gramps")
parser.add_argument("-v", "--verbosity", action="count", default=0, help="Increase verbosity")
parser.add_argument("-a", "--ascendants", default=False, action='store_true', help="Includes ascendants (off by default)")
parser.add_argument("-d", "--descendants", default=False, action='store_true', help="Includes descendants (off by default)")
parser.add_argument("-s", "--spouse", default=False, action='store_true', help="Includes spouse (off by default)")
parser.add_argument("-l", "--level", default=1, type=int, help="Number of level to explore (1 by default)")
parser.add_argument("-g", "--grampsfile", type=str, help="Name of the Gramps database")
parser.add_argument("-i", "--id", type=str, help="ID of the person to start from in Gramps")
parser.add_argument("-f", "--force", default=False, action='store_true', help="Force processing")
parser.add_argument("searchedperson", type=str, nargs='?', help="Url of the person to search in Geneanet")
args = parser.parse_args()

if args.verbosity >= 1:
    print("LEVEL:",LEVEL)
if args.searchedperson == None:
    #purl = 'agnesy?lang=fr&pz=hugo+mathis&nz=renard&p=marie+sebastienne&n=helgouach'
    purl = 'agnesy?lang=fr&n=queffelec&oc=17&p=marie+anne'
else:
    purl = args.searchedperson

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

def get_gramps_date(person,evttype,db):
    '''
    Give back the date of the event related to the person
    '''

    if args.verbosity >= 3:
        print("EventType: %d"%(evttype))

    if evttype == BIRTH:
        ref = person.get_birth_ref()
    elif evttype == DEATH:
        ref = person.get_death_ref()
    elif evttype == MARRIAGE:
        ref = get_marriage_date(db,person)
    else:
        print("Didn't find a known EventType: ",evttype)
        return(None)

    if ref:
        if args.verbosity >= 3:
            print("Ref:",ref)
        try:
            event = db.get_event_from_handle(ref.ref)
        except:
            print("Didn't find a known ref for this ref date: ",ref)
            return(None)
        if event:
            if args.verbosity >= 3:
                print("Event:",event)
            date = event.get_date_object()
            tab = date.get_dmy()
            if args.verbosity >= 3:
                print("Found date:",tab)
            if len(tab) == 3:
                tab = date.get_ymd()
                if args.verbosity >= 3:
                    print("Found date2:",tab)
                ret = format_iso(tab)
            else:
                ret = format_noniso(tab)
            if args.verbosity >= 3:
                print("Returned date:",ret)
            return(ret)
        else:
            return(None)
    else:
        return(None)

def get_child_list(db, person, spouse):
    "return list of children for given person or None"
    children = []
    cret = []
    for fam_handle in person.get_family_handle_list():
        fam = db.get_family_from_handle(fam_handle)
        for child_ref in fam.get_child_ref_list():
            # Adds only if this is the correct spouse
            children.append(child_ref.ref)
    if children:
        for c in children:
            c1 = db.get_person_from_handle(c)
            cret.append(c1)
        return (cret)
    return None

def get_marriage_list(db, person):
    "return list of marriages for given person or None"
    marriages = []
    for family_handle in person.get_family_handle_list():
        family = db.get_family_from_handle(family_handle)
        if int(family.get_relationship()) == FamilyRelType.MARRIED:
            for event_ref in family.get_event_ref_list():
                event = db.get_event_from_handle(event_ref.ref)
                if (event.get_type() == EventType.MARRIAGE and
                        (event_ref.get_role() == EventRoleType.FAMILY or
                         event_ref.get_role() == EventRoleType.PRIMARY)):
                    marriages.append(event_ref.ref)
    if marriages:
        return (marriages)
    return None

def convert_date(datetab):
    ''' Convert the Geneanet date format for birth/death/married lines
    into an ISO date format
    '''

    if args.verbosity >= 3:
        print("datetab received:",datetab)

    if len(datetab) == 0:
        return("")
    idx = 0
    if datetab[0] == 'le':
        idx = 1
    if datetab[idx] == "1er":
        datetab[idx] = "1"
    bd1 = " "
    bd1 = bd1.join(datetab[idx:])
    bd2 = datetime.strptime(bd1, "%d %B %Y")
    return(bd2.strftime("%Y-%m-%d"))

class Geneanet(Gramplet):
    '''
    Gramplet to import Geneanet persons into Gramps
    '''

    def init(sefl):
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.gui.WIDGET)
        self.gui.WIDGET.show()

    def build_gui(self):
        """
        Build the GUI interface.
        """
        tip = _('Double-click on a row to take the selected person as starting point.')
        self.set_tooltip(tip)
        self.view = Gtk.TreeView()
        titles = [(_('Name'), 0, 230),
                  (_('Birth'), 2, 100),
                  ('', NOSORT, 1),
                  ('', NOSORT, 1), # tooltip
                  ('', NOSORT, 100)] # handle
        self.model = ListModel(self.view, titles, list_mode="tree",
                               event_func=self.cb_double_click)
        return self.view

class GFamily():
    '''
    Family as seen by Gramps
    '''
    def __init__(self,gp0,gp1):
        if args.verbosity >= 1:
            print("Creating Family: "+gp0.lastname+" - "+gp1.lastname)
        self.marriage = None
        self.marriageplace = None
        self.marriageplacecode = None
        self.children = []

        # TODO: do these people already form a family, supposing not for now
        self.family = Family()
        with DbTxn("Geneanet import", db) as tran:
            db.add_family(self.family,tran)

            try:
                grampsp0 = db.get_person_from_gramps_id(gp0.gid)
            except:
                if args.verbosity >= 2:
                    print('No father for this family')
                grampsp0 = None

            if grampsp0:
                try:
                    self.family.set_father_handle(grampsp0.get_handle())
                except:
                    if args.verbosity >= 2:
                        print("Can't affect father to the family")

                db.commit_family(self.family,tran)
                grampsp0.add_family_handle(self.family.get_handle())
                db.commit_person(grampsp0,tran)

            try:
                grampsp1 = db.get_person_from_gramps_id(gp1.gid)
            except:
                if args.verbosity >= 2:
                    print('No mother for this family')
                grampsp1 = None

            if grampsp1:
                try:
                    self.family.set_mother_handle(grampsp1.get_handle())
                except:
                    if args.verbosity >= 2:
                        print("Can't affect mother to the family")

                db.commit_family(self.family,tran)
                grampsp1.add_family_handle(self.family.get_handle())
                db.commit_person(grampsp1,tran)

    def add_child(self,child):
        if args.verbosity >= 1:
            print("Adding Child : "+child.firstname+" "+child.lastname)
        childref = ChildRef()
        try:
            childref.set_reference_handle(child.get_handle())
            self.family.add_child_ref(childref)
            with DbTxn("Geneanet import", db) as tran:
                db.commit_family(self.family,self.tran)
                child.add_parent_family_handle(self.family.get_handle())
        except:
            pass

class GPerson():
    '''
    Generic Person common between Gramps and Geneanet
    '''
    def __init__(self,level):
        if args.verbosity >= 3:
            print("Initialize Person")
        self.level = level
        self.firstname = ""
        self.lastname = ""
        self.sex = 'I'
        self.birth = None
        self.birthplace = None
        self.birthplacecode = None
        self.death = None
        self.deathplace = None
        self.deathplacecode = None
        self.gid = None
        self.url = None
        self.family = []
        self.fref = ""
        self.mref = ""
        # Father and Mother id in gramps
        self.fgid = None
        self.mgid = None

    def __smartcopy(self,p,attr):
        '''
        Smart Copying an attribute from p into self
        '''
        if args.verbosity >= 3:
            print("Smart Copying Attributes",attr)

        # By default do not copy
        scopy = False

        # Find the case where copy is to be done
        # Nothing yet
        if not self.__dict__[attr]:
            scopy = True

        # Force the copy
        if self.__dict__[attr] != p.__dict__[attr] and args.force:
            scopy = True

        # Improve sex if we can
        if attr == 'sex' and self.__dict__[attr] == 'I':
            scopy = True

        if scopy:
            self.__dict__[attr] = p.__dict__[attr]
        else:
            if args.verbosity >= 3:
                print("Not Copying Person attribute (%s, value %s) onto %s"%(attr, self.__dict__[attr],p.__dict__[attr]))

    def smartcopy(self,p):
        '''
        Smart Copying p into self
        '''
        if args.verbosity >= 2:
            print("Smart Copying Person")
        self.__smartcopy(p,"firstname")
        self.__smartcopy(p,"lastname")
        self.__smartcopy(p,"sex")
        self.__smartcopy(p,"url")
        self.__smartcopy(p,"birth")
        self.__smartcopy(p,"birthplace")
        self.__smartcopy(p,"birthplacecode")
        self.__smartcopy(p,"death")
        self.__smartcopy(p,"deathplace")
        self.__smartcopy(p,"deathplacecode")
        self.mref = p.mref
        self.fref = p.fref
        # Does it work ?
        self.family = p.family

    def from_geneanet(self,purl):
        ''' Use XPath to retrieve the details of a person
        Used example from https://gist.github.com/IanHopkinson/ad45831a2fb73f537a79
        and doc from https://www.w3schools.com/xml/xpath_axes.asp
        and https://docs.python-guide.org/scenarios/scrape/

        lxml can return _ElementUnicodeResult instead of str so cast
        '''

        if args.verbosity >= 3:
            print("Purl:",purl)
        if not purl:
            return()
        try:
            p = ROOTURL+purl
            if args.verbosity >= 1:
                print('-----------------------------------------------------------')
                print("Page considered:",p)
            page = requests.get(p)
            if args.verbosity >= 3:
                print(_("Return code:"),page.status_code)
        except:
            print("We failed to reach the server at",p)
        else:
            if page.ok:
                try:
                    tree = html.fromstring(page.content)
                except:
                    print(_("Unable to perform HTML analysis"))
    
                    self.url = purl
                try:
                    # Should return F or H
                    sex = tree.xpath('//div[@id="person-title"]//img/attribute::alt')
                    self.sex = sex[0]
                except:
                    self.sex = 'I'
                try:
                    name = tree.xpath('//div[@id="person-title"]//a/text()')
                    self.firstname = str(name[0])
                    self.lastname = str(name[1])
                except:
                    self.firstname = ""
                    self.lastname = ""
                if args.verbosity >= 1:
                    print('==> GENEANET Name (L%d): %s %s'%(self.level,self.firstname,self.lastname))
                if args.verbosity >= 2:
                    print('Sex:', self.sex)
                try:
                    birth = tree.xpath('//li[contains(., "Né")]/text()')
                except:
                    birth = [""]
                try:
                    death = tree.xpath('//li[contains(., "Décédé")]/text()')
                except:
                    death = [""]
                try:
                    parents = tree.xpath('//li[@style="vertical-align:middle;list-style-type:disc"]')
                except:
                    parents = []
                try:
                    spouse = tree.xpath('//ul[@class="fiche_union"]//li[@style="vertical-align:middle;list-style-type:disc"]')
                except:
                    spouse = []
                try:
                    ld = convert_date(birth[0].split('-')[0].split()[1:])
                    if args.verbosity >= 2:
                        print('Birth:', ld)
                    self.birth = ld
                except:
                    self.birth = ""
                try:
                    self.birthplace = str(birth[0].split('-')[1].split(',')[0].strip())
                    if args.verbosity >= 2:
                        print('Birth place:', self.birthplace)
                except:
                    self.birthplace = ""
                try:
                    self.birthplacecode = str(birth[0].split('-')[1].split(',')[1]).strip()
                    if args.verbosity >= 2:
                        print('Birth place code:', self.birthplacecode)
                except:
                    self.birthplacecode = ""
                try:
                    ld = convert_date(death[0].split('-')[0].split()[1:])
                    if args.verbosity >= 2:
                        print('Death:', ld)
                    self.death = ld
                except:
                    self.death = ""
                try:
                    self.deathplace = str(death[0].split('-')[1].split(',')[0]).strip()
                    if args.verbosity >= 2:
                        print('Death place:', self.deathplace)
                except:
                    self.deathplace = ""
                try:
                    self.deathplacecode = str(death[0].split('-')[1].split(',')[1]).strip()
                    if args.verbosity >= 2:
                        print('Death place code:', self.deathplacecode)
                except:
                    self.deathplacecode = ""

                for s in spouse:
                    try:
                        sname = str(s.xpath('a/text()')[0])
                        if args.verbosity >= 2:
                            print('Spouse name:', sname)
                    except:
                        sname = ""

                    try:
                        sref = str(s.xpath('a/attribute::href')[0])
                        if args.verbosity >= 2:
                            print('Spouse ref:', ROOTURL+sref)
                    except:
                        sref = ""
                    self.spouseref = sref

                    try:
                        married = str(s.xpath('em/text()')[0])
                    except: 
                        married = ""
                    try:
                        ld = convert_date(married.split(',')[0].split()[1:])
                        if args.verbosity >= 2:
                            print('Married:', ld)
                        self.married = ld
                    except:
                        self.married = ""
                    try:
                        self.marriedplace = str(married.split(',')[1])
                        if args.verbosity >= 2:
                            print('Married place:', self.marriedplace)
                    except:
                        self.marriedplace = ""
                    try:
                        self.marriedplacecode = str(married.split(',')[2])
                        if args.verbosity >= 2:
                            print('Married place code:', self.marriedplacecode)
                    except:
                        self.marriedplacecode = ""
    
                    children = s.xpath('ul/li[@style="vertical-align:middle;list-style-type:square;"]')
                    cnum = 0
                    self.childref = []
                    for c in children:
                        try:
                            cname = c.xpath('a/text()')[0]
                            print('Child %d name: %s'%(cnum,cname))
                        except:
                            cname = ""
                        try:
                            cref = c.xpath('a/attribute::href')[0]
                            print('Child %d ref: %s'%(cnum,ROOTURL+cref))
                        except:
                            cref = ""
                        self.childref.append(str(cref))
                        cnum = cnum + 1
    
                self.fref = ""
                self.mref = ""
                self.pref = []
                for p in parents:
                    if args.verbosity >= 3:
                        print(p.xpath('text()'))
                    if p.xpath('text()')[0] == '\n':
                        try:
                            pname = p.xpath('a/text()')[0]
                            print('Parent name: %s'%(pname))
                        except:
                            pname = ""
                            # if pname is ? ? then go to next one
                        try:
                            pref = p.xpath('a/attribute::href')[0]
                            print('Parent ref:', ROOTURL+pref)
                        except:
                            pref = ""
                        self.pref.append(str(pref))
                try:
                    self.fref = self.pref[0]
                except:
                    self.fref = ""
                try:
                    self.mref = self.pref[1]
                except:
                    self.mref = ""
                if args.verbosity >= 2:
                    print('-----------------------------------------------------------')
    
            else:
                print(_("We failed to be ok with the server"))


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
                if args.verbosity >= 2:
                    print("Reuse Place from Event:", placename)
            except:
                place = Place()
        else:
            keep = None
            # Check whether our place already exists
            for handle in db.get_place_handles():
                pl = db.get_place_from_handle(handle)
                explace = pl.get_name().value
                if args.verbosity >= 3:
                    print("DEBUG: search for "+str(placename)+" in "+str(explace))
                if str(explace) == str(placename):
                    keep = pl
                    break
            if keep == None:
                if args.verbosity >= 2:
                    print("Create Place:", placename)
                place = Place()
            else:
                if args.verbosity >= 2:
                    print("Reuse existing Place:", placename)
                place = keep
        return(place)

        
    def get_or_create_person_event(self,grampsp,attr,tran):
        '''
        Create Birth and Death Events for this person or get an existing one
        '''
        
        # Manages name indirection
        func = getattr(grampsp,'get_'+attr+'_ref')
        reffunc = func()
        event = None
        if reffunc:
            try:
                event = db.get_event_from_handle(reffunc.ref)
                eventref = reffunc
                if args.verbosity >= 2:
                    print("Existing "+attr+" Event")
            except:
                pass
        if event is None:
            event = Event()
            # We manage a person here (for family place False)
            event.personal = True
            uptype = getattr(EventType,attr.upper())
            event.set_type(EventType(uptype))
            if self.url:
                event.set_description('Imported from '+self.url)
            else:
                event.set_description('Imported from Geaneanet')
            db.add_event(event,tran)
            
            eventref = EventRef()
            eventref.set_role(EventRoleType.PRIMARY)
            eventref.set_reference_handle(event.get_handle())
            func = getattr(grampsp,'set_'+attr+'_ref')
            reffunc = func(eventref)
            #p.event_ref_list.append(eventref)
            if args.verbosity >= 2:
                print("Creating "+attr+" ("+str(uptype)+") Event, Rank: "+str(grampsp.birth_ref_index))

        if self.__dict__[attr] \
            or self.__dict__[attr+'place'] \
            or self.__dict__[attr+'placecode'] :
            # TODO: Here we create a new date each time there is a date in object
            date = Date()
            if self.__dict__[attr]:
                if self.__dict__[attr][:1] == 'ca':
                    mod = Date.MOD_ABOUT 
                elif self.__dict__[attr][:1] == 'av':
                    mod = Date.MOD_BEFORE 
                elif self.__dict__[attr][:1] == 'ap':
                    mod = Date.MOD_AFTER 
                else:
                    mod = Date.MOD_NONE 
                # ISO string, put in a tuple, reversed
                tab = self.__dict__[attr].split('-')
                date.set_yr_mon_day(int(tab[0]),int(tab[1]),int(tab[2]))
            if args.verbosity >= 2:
                print("Update "+attr+" Date to "+self.__dict__[attr])
            event.set_date_object(date)
            db.commit_event(event,tran)

            if self.__dict__[attr+'place'] \
                or self.__dict__[attr+'placecode'] :
                if self.__dict__[attr+'place']:
                    placename = self.__dict__[attr+'place']
                else:
                    placename = ""
                place = self.get_or_create_place(event,placename)
                # TODO: Here we overwrite any existing value.
                place.set_name(PlaceName(value=placename))
                if self.__dict__[attr+'placecode']:
                    place.set_code(self.__dict__[attr+'placecode'])
                db.add_place(place,tran)
                event.set_place_handle(place.get_handle())
                db.commit_event(event,tran)
        return(event)

    def validate(self,p):
        '''
        Validate the GPerson attributes 
        and use them to enrich or create a Gramps Person
        using data from the Genanet p person
        '''

        self.smartcopy(p)
        with DbTxn("Geneanet import", db) as tran:
            db.disable_signals()
            grampsp = db.get_person_from_gramps_id(self.gid)
            if grampsp:
                if args.verbosity >= 2:
                    print("Existing Gramps Person:", self.gid)
            else:
                # Create a new Person in Gramps
                grampsp = Person()
                db.add_person(grampsp,tran)
                self.gid = grampsp.gramps_id
                if args.verbosity >= 2:
                    print("Create new Gramps Person: "+self.gid+' ('+self.firstname+' '+self.lastname+')')

            if self.sex == 'H':
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
                e = self.get_or_create_person_event(grampsp,ev,tran)
                db.commit_event(e,tran)
    
            db.commit_person(grampsp,tran)
            db.enable_signals()
            db.request_rebuild()
 
    def from_gramps(self,gid):
        self.gid = gid
        if gid == None:
            return
        try:
            grampsp = db.get_person_from_gramps_id(gid)
            if args.verbosity >= 3:
                print("Person object:", grampsp)
            if grampsp.gender:
                self.sex = GENDER[grampsp.gender]
                if args.verbosity >= 1:
                    print("Gender:",GENDER[grampsp.gender])
            name = grampsp.primary_name.get_name().split(', ')
            if name[0]:
                self.firstname = name[1]
            else:
                self.lastname = ""
            if name[1]:
                self.lastname = name[0]
            else:
                self.firstname = ""
            if args.verbosity >= 1:
                print("===> GRAMPS Name: %s %s"%(self.firstname,self.lastname))
                print("Gramps Id: %s"%(gid))
        except:
            if args.verbosity >= 2:
                print(_("Unable to retrieve id %s from the gramps db %s")%(gid,name))
            return

        try:
            bd = get_gramps_date(grampsp,BIRTH,db)
            if bd:
                if args.verbosity >= 1:
                    print("Birth:",bd)
                self.birth = bd
            else:
                if args.verbosity >= 1:
                    print("No Birth date")
        except:
            if args.verbosity >= 1:
                print(_("Unable to retrieve birth date for id %s")%(gid))

        try:
            dd = get_gramps_date(grampsp,DEATH,db)
            if dd:
                if args.verbosity >= 1:
                    print("Death:",dd)
                self.death = dd
            else:
                if args.verbosity >= 1:
                    print("No Death date")
        except:
            if args.verbosity >= 1:
                print(_("Unable to retrieve death date for id %s")%(gid))
        
        #try:
            #self.childref = get_child_list(db,grampsp)

        try:
            fh = grampsp.get_main_parents_family_handle()
            if fh:
                if args.verbosity >= 3:
                    print("Family:",fh)
                fam = db.get_family_from_handle(fh)
                if fam:
                    if args.verbosity >= 1:
                        print("Family:",fam)
                # find father from a family
                fh = fam.get_father_handle()
                if fh:
                    if args.verbosity >= 3:
                        print("Father H:",fh)
                    father = db.get_person_from_handle(fh)
                    if father:
                        if args.verbosity >= 1:
                            print("Father name:",father.primary_name.get_name())
                        self.fgid = father.gramps_id
                mh = fam.get_mother_handle()
                if mh:
                    if args.verbosity >= 3:
                        print("Mother H:",mh)
                    mother = db.get_person_from_handle(mh)
                    if mother:
                        if args.verbosity >= 1:
                            print("Mother name:",mother.primary_name.get_name())
                        self.mgid = mother.gramps_id
        except:
            if args.verbosity >= 1:
                print(_("Unable to retrieve family for id %s")%(gid))

#
# To be seen later
                #if args.spouse:
                    #time.sleep(5)
                    #find_geneanet_person(sref)

                    #if args.descendants and LEVEL < args.level:
                        #LEVEL = LEVEL + 1
                        #time.sleep(5)
                        #find_geneanet_person(cref)

def import_data(database, filename, user):

    global callback

    try:
        g = GeneanetParser(database)
    except IOError as msg:
        user.notify_error(_("%s could not be opened\n") % filename,str(msg))
        return

    try:
        #status = g.find_geneanet_person(purl)
        pass
    except IOError as msg:
        errmsg = _("%s could not be opened\n") % filename
        user.notify_error(errmsg,str(msg))
        return
    return ImportInfo({_("Results"): _("done")})

def geneanet_to_gramps(level, gid, url):
    '''
    Function to create a person from Geneanet into gramps
    '''
    # Create the Person coming from Gramps
    gp = GPerson(level)
    gp.from_gramps(gid)

    # Create the Person coming from Geneanet
    p = GPerson(level)
    p.from_geneanet(url)

    # Check we point to the same person
    if gid != None:
        if (gp.firstname != p.firstname or gp.lastname != p.lastname) and (not args.force):
            print("Gramps   person: %s %s"%(gp.firstname,gp.lastname))
            print("Geneanet person: %s %s"%(p.firstname,p.lastname))
            db.close()
            sys.exit("Do not continue without force")

        if (gp.birth != p.birth or gp.death != p.death) and (not args.force):
            print("Gramps   person birth/death: %s / %s"%(gp.birth,gp.death))
            print("Geneanet person birth/death: %s / %s"%(p.birth,p.death))
            db.close()
            sys.exit("Do not continue without force")

    # Copy from Geneanet into Gramps and commit
    gp.validate(p)
    return(gp)

def recurse_parents(level,gp):
    '''
    analyze the parents of the person passed in parameter recursively
    '''
    # Recurse while we have parents urls and level not reached
    while level < args.level and (gp.fref != "" or gp.mref != ""):
        level = level + 1
        time.sleep(TIMEOUT)
        gp0 = geneanet_to_gramps(level,gp.fgid,gp.fref)
        recurse_parents(level,gp0)
        time.sleep(TIMEOUT)
        gp1 = geneanet_to_gramps(level,gp.mgid,gp.mref)
        recurse_parents(level,gp1)
        f = GFamily(gp0,gp1)
        f.add_child(gp)

def recurse_children(level,gp):
    '''
    analyze the children of the person passed in parameter recursively
    '''
    # TODO: probably need the spouse as param
    # Recurse while we have parents urls and level not reached
    while level < args.level and (gp.fref != "" or gp.mref != ""):
        level = level + 1
        time.sleep(TIMEOUT)

# MAIN
name = args.grampsfile

# TODO: to a backup before opening
if name == None:
    #name = "Test import"
    # To be searched in ~/.gramps/recent-files-gramps.xml
    name = "/users/bruno/.gramps/grampsdb/5ec17554"
try:
    dbstate = DbState()
    climanager = CLIManager(dbstate, True, None)
    climanager.open_activate(name)
    db = dbstate.db
except:
    ErrorDialog(_("Opening the '%s' database") % name,
                _("An attempt to convert the database failed. "
                  "Perhaps it needs updating."), parent=self.top)
    sys.exit()

gid = args.id
if gid == None:
    gid = "0000"
gid = "I"+gid

ids = db.get_person_gramps_ids()
for i in ids:
    if args.verbosity >= 1:
        print(i)

if args.verbosity >= 1 and args.force:
    print("WARNING: Force mode activated")
    time.sleep(TIMEOUT)

# Create the first Person 
gp = geneanet_to_gramps(0,gid,purl)

if args.ascendants:
        recurse_parents(LEVEL,gp)

LEVEL = 0
if args.descendants:
    while LEVEL < args.level:
        LEVEL = LEVEL + 1
        time.sleep(TIMEOUT)

db.close()
sys.exit(0)
