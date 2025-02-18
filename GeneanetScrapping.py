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
import json
from collections import namedtuple
from datetime import datetime
from pathlib import Path
import subprocess

import babel, babel.dates

#-------------------------------------------------------------------------
#
# Global variables
#
#-------------------------------------------------------------------------

# verbosity = 0
# force = False
# ascendants = False
# descendants = False
# spouses = False
# LEVEL = 2

ICLOUD_PATH = "."

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

console = Console(record=True, width=132)

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

# import gettext
# locale = 'fr'
# translation = gettext.translation('base', localedir='locales', languages=[locale])
# translation.install()
# _ = translation.gettext

#-------------------------------------------------------------------------
#
# Web Scrapping
#
#-------------------------------------------------------------------------

from bs4 import BeautifulSoup
from bs4 import Comment, NavigableString

import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service

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

def clean_query( url ):
    queries = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if len(queries) > 0:
        queries_to_keep = [ 'm', 'v', 'p', 'n', 'oc', 'i' ]

        removed_queries = {k: v for k, v in queries.items() if k not in queries_to_keep + ['lang', 'pz', 'nz']}
        if len(removed_queries) > 0:
            display( "Removed queries: %s"%(removed_queries) )

        return urllib.parse.urlencode({k: v for k, v in queries.items() if k in queries_to_keep}, doseq=True)
    else:
        return url

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

def sanitize( str ):
    return str.replace( '=', "_" ).replace( '+', " " ).replace( '&', "." )

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
# GFamily class
#
#----------------------------------------------------------------------------------------------------------------------------------

class GFamily(GBase):

    # -------------------------------------------------------------------------
    # __init__
    # -------------------------------------------------------------------------
    # family : geneanet soup

    def __init__(self, personref, family ):

        try:
            marriage = family.find("em").get_text()
        except:
            marriage = None
                
        # marriage date
        try:
            self._marriagedate = format_ca( convert_date(marriage.split(',')[0].split()[1:]) )
        except:
            self._marriagedate = None

        # marriage place
        try:
            self._marriageplace = ', '.join([x for x in marriage.strip().split(',')[1:] if x]).strip()
            self._marriageplace = ",".join( item.strip() for item in self._marriageplace.split(",") )
        except:
            self._marriageplace = None

        # spouses ref
        try:
            # first <a> can be a ref to sosa
            self._spousesref = [ clean_query( personref ), clean_query( [a for a in family.find_all('a') if a.get_text(strip=True)][0]['href'] ) ]
            
        except:
            self._spousesref = [ clean_query( personref ), None ]

        # annulation date
        self._annulationdate = None
        if 'annulé' in family.get_text().lower():
            display("Add annulation processing")

        # divorce date
        self._divorcedate = None
        if 'divorcé' in family.get_text().lower():
            display("Add divorce processing")

        # engagement date
        self._engagementdate = None
        if 'annulé' in family.get_text().lower():
            display("Add engagement processing")

        # publish date
        self._publishdate = None
        if 'bans' in family.get_text().lower():
            display("Add publish processing")

        # license date
        self._licensedate = None
        if 'license' in family.get_text().lower():
            display("Add license processing")

        # separation date
        self._separationdate = None
        if 'séparé' in family.get_text().lower():
            display("Add separation processing")

        # childs
        self._childsref = []
        try:
            for item in family.find("ul").find_all( "li", recursive=False ):
                # first <a> can be a ref to sosa
                self._childsref = self._childsref + [ clean_query( [a for a in item.find_all('a') if a.get_text(strip=True)][0]['href'] ) ]
        except:
            self._childsref = []

    # -------------------------------------------------------------------------
    # setids
    # -------------------------------------------------------------------------
    def setids(self, persons_table, families_table):
        try:
            self._gedcomid = families_table[self._spousesref]
        except:
            self._gedcomid = None

        self._spousesid = []
        for spouse in self._spousesref:
            try:
                self._spousesid = self._spousesid + [ persons_table[spouse] ]
            except:
                self._spousesid = self._spousesid + [ None ]

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
        text ="@F%d@ FAM"%(self._gedcomid)
        return text

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

    def __init__(self, url):

        display( "" )
        display("Person: %s"%(url), level=2 )

        # Geneanet
        self._url = url
        self._path = re.sub( r'^/', '', urllib.parse.urlparse(url).path )
        self._ref = clean_query( url )

        #Gedcom
        self._id = None

        self._portrait = {
            'firstname' : "",
            'lastname' : "",
            'sex' : "U",
            'birthdate' : None,
            'birthplace' : "",
            'deathdate' : None,
            'deathplace' : ""
        }

        self._parentsref = []

        self._siblingsref = []

        self._families = []

        self._medias = []

        self._notes = ""

        # scrap geneanet page
        self.scrap_geneanet()

    # -------------------------------------------------------------------------
    # _read_geneanet
    # -------------------------------------------------------------------------

    def _read_geneanet( self, url, force = True ):

        output_file = sanitize( clean_query(url) )

        output_txt = ICLOUD_PATH / self._path / "html" / (output_file + ".txt")

        # force fr language

        queries = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        if 'lang' in queries:
            if queries['lang'] != 'fr':
                url = url.replace( "lang=" + queries['lang'], "lang=fr" )
        else:
            url = url.replace( "?", "?lang=fr&" )

        browser = None

        if force == False or not output_txt.exists():

            # Chrome setup

            chrome_options = webdriver.ChromeOptions()
            # chrome_options.add_argument("--headless")  # Headless mode to avoid opening a browser window
            chrome_options.add_argument("--kiosk-printing")  # Enables silent printing
            chrome_options.add_argument("--disable-gpu")  # Disables GPU acceleration (helpful in some cases)

            # Configure Chrome print settings to save as PDF
            output_pdf = ICLOUD_PATH / self._path / "pdf"
            chrome_options.add_experimental_option("prefs", {
                "printing.print_preview_sticky_settings.appState": '{"recentDestinations":[{"id":"Save as PDF","origin":"local"}],"selectedDestinationId":"Save as PDF","version":2}',
                "savefile.default_directory": str(output_pdf)
            })

            service = Service()  # No need to specify path if using Selenium 4.6+
            browser = webdriver.Chrome(service=service, options=chrome_options)

            # let's go browse

            browser.get(url)

            try:
                consent_button = WebDriverWait(browser, 20).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button#tarteaucitronPersonalize2"))
                )
                ActionChains(browser).move_to_element(consent_button).click().perform()
            except:
                pass

            # Get content in perso bloc

            soup = BeautifulSoup(browser.page_source, 'html.parser')

            # process PDF
            try:
                output_pdf = output_pdf / output_file + ".pdf"
                output_pdf.parent.mkdir(parents=True, exist_ok=True)
                output_pdf.unlink(missing_ok=True)   

                # Use Chrome DevTools Protocol (CDP) to print as PDF
                pdf_settings = {
                    "landscape": False,
                    "displayHeaderFooter": False,
                    "printBackground": True,
                    "preferCSSPageSize": True
                }

                # Execute CDP command to save as PDF
                pdf_data = browser.execute_cdp_cmd("Page.printToPDF", pdf_settings)

                # Save PDF to file
                output_pdf.write_bytes(bytearray(pdf_data['data'], encoding='utf-8'))
            except:
                display( 'Failed to save PDF for %s'%(output_pdf))

            # process perso

            try:
                output_txt.parent.mkdir(parents=True, exist_ok=True)
                output_txt.unlink(missing_ok=True)

                NL = "\n"
                NC = 132

                output_txt.write_text( perso.prettify() )
            except:
                pass


        else:
            display( 'Read from %s'%(output_txt))
            soup = BeautifulSoup( output_txt.read_text(), 'html.parser' )

        # Parse content to sections

        perso = soup.find("div", {"id": "perso"})

        contents = []
        # medias = []

        Section = namedtuple("Section", "name content")

        try:
            # extract the medias

            # images = perso.find_all("img", attrs={"ng-src": re.compile(r".*")} )

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
            display( message, error=True )
            pass

        # process the clickable medias

        # medias = []
        # current_window = browser.current_window_handle

        # images = browser.find_elements(By.CSS_SELECTOR, "img[ng-click='mediasCtrl.mediaClick(media)']")
        # for image in images:
        #     try:
        #         browser.switch_to.window(current_window)
        #         current_windows = browser.window_handles
        #         print( image )
        #         print( 'click' )
        #         image.click()
        #         print( 'clicked' )
        #         time.sleep(2)  # Wait for the new window/tab to open
        #         all_windows = browser.window_handles

        #         for window in all_windows:
        #             if window not in current_windows:
        #                 browser.switch_to.window(window)
        #                 imagesoup = BeautifulSoup(browser.page_source, 'html.parser')
        #                 # find and click download button
        #                 # unzip file
        #                 # grab details
        #                 break
        #     except:
        #         print( 'failed action')

        # process the regular medias
        # image = browser.find_elements(By.CSS_SELECTOR, "img[ng-src]")
        # image = browser.find_elements(By.XPATH, "//img[@ng-src and not(@ng-click)]")

        if browser:
            browser.quit()

        return perso, None, None, contents

    # -------------------------------------------------------------------------
    # scrap_geneanet
    # -------------------------------------------------------------------------

    def scrap_geneanet(self):

        # read web page
        
        perso, images, medias, sections = self._read_geneanet( self._url )

        for section in sections:

            # -------------------------------------------------------------
            # Portrait section
            # -------------------------------------------------------------
            if 'portrait' in section.name.lower():

                # first and last names
                try:
                    names = section.content.find("div", {"id" : "person-title"}).find_all_next("a")

                    self._portrait['firstname'] = names[0].get_text().title()
                    self._portrait['lastname'] = names[1].get_text().title()
                except:
                    pass

                # sex: should return M or F
                try:
                    sex = section.content.find("div", {"id" : "person-title"}).find_all_next("img", alt=True)

                    self._portrait['sex'] = sex[0]['alt']
                    if self._portrait['sex'] == 'H':
                        self._portrait['sex'] = 'M'
                except:
                    self._portrait['sex'] = 'U'

                # birth
                try:
                    birth = section.content.find_all('li', string=lambda text: "Né" in text if text else False)[0].get_text()
                except:
                    birth = ""

                try:
                    self._portrait['birthdate'] = format_ca( convert_date(birth.split('-')[0].split()[1:]) )
                except:
                    pass

                try:
                    self._portrait['birthplace'] = str(birth.split(' - ')[1])
                    self._portrait['birthplace'] = ",".join( item.strip() for item in self._portrait['birthplace'].split(",") )
                except:
                    if len(birth) < 1:
                        pass
                    else:
                        self._portrait['birthplace'] = str(uuid.uuid3(uuid.NAMESPACE_URL, self._url))

                # death
                try:
                    death = section.content.find_all('li', string=lambda text: "Décédé" in text if text else False)[0].get_text()
                except:
                    death = ""

                try:
                    self._portrait['deathdate'] = format_ca( convert_date(death.split('-')[0].split()[1:]) )
                except:
                    pass

                try:
                    self._portrait['deathplace'] = re.split(f"{re.escape(",\nà l'âge")}|{re.escape(", à l'âge")}", str(death.split(' - ')[1]))[0]
                    self._portrait['deathplace'] = ",".join( item.strip() for item in self._portrait['deathplace'].split(",") )
                except:
                    if len(death ) < 1:
                        pass
                    else:
                        self._portrait['deathplace'] = str(uuid.uuid3(uuid.NAMESPACE_URL, self._url))

                # baptem
                try:
                    baptem = section.content.find_all('li', string=lambda text: "baptisé" in text.lower() if text else False)[0].get_text()
                    display("Add baptem processing")
                except:
                    baptem = ""

                # occupation
                try:
                    occupation = section.content.find_all('li', string=lambda text: "employé" in text.lower() if text else False)[0].get_text()
                    display("Add occupation processing")
                except:
                    occupation = ""

                # burial
                try:
                    burial = section.content.find_all('li', string=lambda text: "inhumé" in text.lower() if text else False)[0].get_text()
                    display("Add burial processing")
                except:
                    burial = ""

                # adoption
                try:
                    adoption = section.content.find_all('li', string=lambda text: "adopté" in text.lower() if text else False)[0].get_text()
                    display("Add adoption processing")
                except:
                    adoption = ""

            # -------------------------------------------------------------
            # Parents section
            # -------------------------------------------------------------
            elif 'parents' in section.name.lower():
                
                try:
                    self._parentsref = [clean_query( item['href'] ) for item in section.content.find_all("a") if len( item.find_all("img", {"alt" : "sosa"}) ) == 0]
                except:
                    pass

            # -------------------------------------------------------------
            # Families section
            # -------------------------------------------------------------
            elif 'union' in section.name.lower():
                try:
                    self._families = []
                    families = section.content.find('ul', class_=re.compile('.*fiche_union.*') ).find_all( "li", recursive=False )

                    for family in families:
                        self._families = self._families + [ GFamily(self._ref, family) ]
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
                            self._siblingsref = self._siblingsref + [ clean_query( tag_a['href'] ) ]
                except:
                    pass

            # -------------------------------------------------------------
            # Relation section
            # -------------------------------------------------------------
            elif 'relation' in section.name.lower():
                if len(section.content) > 0:
                    display("Add processing for section: %s"%(section.name))
                    self._notes = self._notes + clean_text( str(section.content) )

            # -------------------------------------------------------------
            # Related section
            # -------------------------------------------------------------
            elif 'related' in section.name.lower():
                if len(section.content) > 0:
                    display("Add processing for section: %s"%(section.name))
                    self._notes = self._notes + clean_text( str(section.content) )

            # -------------------------------------------------------------
            # Notes section
            # -------------------------------------------------------------
            elif 'notes' in section.name.lower():
                if 'timeline' in section.name.lower():
                    if len(section.content) > 0:
                        display("Add processing for section: %s"%(section.name))
                        self._notes = self._notes + clean_text( str(section.content) )
                else:
                    if len(section.content) > 0:
                        display("Add processing for section: %s"%(section.name))
                        self._notes = self._notes + clean_text( str(section.content) )

            # -------------------------------------------------------------
            # Sources section
            # -------------------------------------------------------------
            elif 'sources' in section.name.lower():
                if len(section.content) > 0:
                    try:
                        display("Add processing for section: %s"%(section.name))
                        self._notes = self._notes +  clean_text( section.content.find( "div", {"ng-non-bindable" : ""} ).decode_contents() )
                    except:
                        pass

            # -------------------------------------------------------------
            # Unprocess section
            # -------------------------------------------------------------
            else:
                if len(section.content) > 0:
                    display("Add processing for section: %s"%(section.name))

        self._notes = None

        # -------------------------------------------------------------
        # Images
        # -------------------------------------------------------------
        
        # -------------------------------------------------------------
        # Images
        # -------------------------------------------------------------
        
        # if len(medias) > 0:

        #     display("Add medias processing")
        #     display( medias )
        #     for media in medias:
        #         try:
        #             # Get the 'src' attribute of the image
        #             image_url = media.attrs['src']
        #             image_alt = media.attrs['alt']

        #             # Download the image using requests
        #             response = requests.get(urllib.parse.urljoin(ROOTURL, image_url))

        #             # Save the image to a file
        #             image_filename = os.path.join(ICLOUD_PATH, "images", encode_url( self._ref ), image_alt + "_" + os.path.basename(image_url))
        #             os.makedirs(os.path.dirname(image_filename), exist_ok=True)
        #             with open(image_filename, 'wb') as f:
        #                 try:
        #                     f.write(response.content)
        #                 except:
        #                     pass
        #                 f.close()
        #         except:
        #             pass

    # -------------------------------------------------------------------------
    # setids
    # -------------------------------------------------------------------------
    def setids(self, persons_table, families_table):
        try:
            self._gedcomid = persons_table[self._ref]
        except:
            self._gedcomid = None

        self._parentsid = []
        for parent in self._parentsref:
            try:
                self._parentsid = self._parentsid + [ persons_table[parent] ]
            except:
                self._parentsid = self._parentsid + [ None ]

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
        text ="@I%d@ INDI"%(self._gedcomid)
        return text

#----------------------------------------------------------------------------------------------------------------------------------
#
# GPersons class
#
#----------------------------------------------------------------------------------------------------------------------------------

class GPersons(GBase):

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

        self._parse = None
        self._user = ""

    # -------------------------------------------------------------------------
    # add_person
    # -------------------------------------------------------------------------

    def add_person( self, url, level = 0  ):

        if self._parse == None:
            self._parse = urllib.parse.urlparse(url)

        if self._user == "":
            self._user = re.sub( r'^/', '', self._parse.path )

        if urllib.parse.urlparse(url).scheme == "":
            url = urllib.parse.urlunparse((self._parse.scheme, self._parse.netloc, self._parse.path, '', url, ''))

        ref = clean_query( url )
        if ref not in self._persons:
            self._persons[ref] = GPerson( url )
            try:
                new_families = self._persons[ref].families
                for family in new_families:
                    if tuple(family.spousesref) not in self._families and tuple(family.spousesref)[::-1] not in self._families:
                        self._families[ tuple(family.spousesref) ] = family
            except:
                pass

            # display( vars(self._persons[ref]), title=ref )

            if level < self._max_level:

                if self._ascendants:
                    for parent in self._persons[ref].parentsref:
                        self.add_person( parent, level+1 )

                if self._spouses:
                    for spouse in self._persons[ref].spousesref:
                        self.add_person( spouse, level+1 )

                if self._descendants:
                    for child in self._persons[ref].childsref:
                        self.add_person( child, level+1 )

    # -------------------------------------------------------------------------
    # gedcom
    # -------------------------------------------------------------------------
    @property
    def gedcom( self ):

        # set gedcom id
        persons_table = {key: index+1 for index, key in enumerate(self._persons)}
        families_table = {key: index+1 for index, key in enumerate(self._families)}

        for ref, person in self._persons.items():
            person.setids( persons_table, families_table )

        for ref, family in self._families.items():
            family.setids( persons_table, families_table )


        return ""

    # -------------------------------------------------------------------------
    # print
    # -------------------------------------------------------------------------

    def print( self ):
        display( self._persons, title="%d Persons"%(len(self._persons)) )

        display( self._families, title="%d Families"%(len(self._families)) )

        for key, person in self._persons.items():
            display( vars(person), title="Person: %s"%(key) )

        for key, family in self._families.items():
            display( vars(family), title="Family: %s"%(str(key)) )

###################################################################################################################################
# geneanetscrapping
###################################################################################################################################

def geneanetscrapping( person, ascendants=False, descendants=False, spouses=False, max_levels= 0, force=False):

    try:
        persons = GPersons( max_levels, ascendants, spouses, descendants )
        persons.add_person( person, force )

        persons.gedcom
    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        message = f'Something went wrong with scrapping [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
        display( message, error=True )

###################################################################################################################################
# main
###################################################################################################################################

def main():

    # global allow local modification of these global variables
    # global LEVEL
    # global ascendants
    # global descendants
    # global spouses

    # global gedcom
    # global gedcomfile
    # global verbosity
    # global force
    # global translation
    # global locale
    # global _
    global ICLOUD_PATH

    display( "GeneanetScrapping", level=1 )

    parser = argparse.ArgumentParser(description="Export Geneanet subtrees into GEDCOM file")
    # parser.add_argument("-v", "--verbosity", action="count", default=0, help="Increase verbosity")
    parser.add_argument("-a", "--ascendants", default=False, action='store_true', help="Includes ascendants (off by default)")
    parser.add_argument("-d", "--descendants", default=False, action='store_true', help="Includes descendants (off by default)")
    parser.add_argument("-s", "--spouses", default=False, action='store_true', help="Includes all spouses (off by default)")
    parser.add_argument("-l", "--level", default=0, type=int, help="Number of level to explore (0 by default)")
    parser.add_argument("-g", "--gedcomfile", type=str, help="Full path of the out GEDCOM")
    parser.add_argument("-f", "--force", default=False, action='store_true', help="Force processing")
    parser.add_argument("searchedperson", type=str, nargs='?', help="Url of the person to search in Geneanet")
    args = parser.parse_args()

    if args.searchedperson == None:
        print("Veuillez indiquer une personne à rechercher")
        return -1
    else:
        purl = args.searchedperson

    gedcomfile = args.gedcomfile
    # verbosity = args.verbosity
    force = args.force
    ascendants = args.ascendants
    descendants = args.descendants
    spouses = args.spouses
    max_levels = args.level

    if max_levels == None:
        max_levels = 0

    header_gedcom_text = """
        0 HEAD
        1 GEDC
        2 VERS 5.5
        2 FORM LINEAGE-LINKED
        1 CHAR UTF-8
        0 TRLR
    """

    # Create data folder

    ICLOUD_PATH = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "GeneanetScrap"
    ICLOUD_PATH.mkdir(exist_ok=True)

    # disable screenlock

    process= subprocess.Popen(["caffeinate", "-d"])

    # Scrap geneanet

    geneanetscrapping( purl, ascendants, descendants, spouses, max_levels, force )

    # enable screenlock

    process.terminate()

    # Save logs

    output_file = ICLOUD_PATH / "output" / f"logs_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.txt"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.unlink(missing_ok=True)
    output_file.write_text(console.export_text())  # Saves formatted text output

    # Save outcome
    
    #console.clear()
    console._record_buffer = []

    persons.print()

    output_file = ICLOUD_PATH / "output" / f"console_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.txt"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.unlink(missing_ok=True)
    output_file.write_text(console.export_text())

if __name__ == '__main__':
    main()

