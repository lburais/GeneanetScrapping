# GenealogyScrapping
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
import base64

import babel, babel.dates

#-------------------------------------------------------------------------
#
# Global variables
#
#-------------------------------------------------------------------------

ICLOUD_PATH = "."
NL = '\n'

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
from rich.theme import Theme

console = Console(record=True, width=132)

HEADER1 = 1
HEADER2 = 2
HEADER3 = 3

def display( what=None, title=None, level=0, error=False, exception=False ):
    """
    My function to display various type of objects
    """

    try:
        if isinstance( what, list ):
            pprint( what )

        elif isinstance( what, dict ):

            console.print( Panel( Pretty(what), title=title, title_align='left' ) )
                
        elif isinstance( what, str ):
            if exception:
                console.print_exception(show_locals=False, max_frames=1)

            elif error:
                console.print( Text( what, style="white on red" ), NL)

            elif level == 1:
                console.print( Panel( Text(what.upper(), style="white"), style="white on cyan" ), NL)

            elif level > 1:
                console.print( Panel( Text(what), style="cyan" ), NL)

            elif title:
                console.print( Panel( Text(what), title=title ))

            else:
                console.print( Text(what) )

        elif isinstance( what, Markdown ):

            #console.print( what.markup )
            console.print( what )
                
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
# Date functions
#
#-------------------------------------------------------------------------

def convert_date(datetab):
    ''' Convert the french date format for birth/death/married lines
    into an ISO date format
    '''

    convert = {
        'ca': 'ABT',
        'vers': 'ABT',
        'à propos': 'ABT',
        'estimé': 'EST',
        'après': 'AFT',
        'avant': 'BEF',
        'entre': 'BET',
        'et': 'AND'
    }

    try:
        if len(datetab) == 0:
            return(None)

        idx = 0

        # Assuming there is just a year and last element is the year

        if len(datetab) == 1 or datetab[0] == 'en':
            # avoid a potential month
            if datetab[-1].isalpha():
                return(datetab[-1][0:4])

            # avoid a potential , after the year
            elif datetab[-1].isnumeric():
                return(datetab[-1][0:4])

        # Between date

        if datetab[0] == 'entre':
            try:
                index = datetab.index("et")
                return(convert[datetab[0]]+" "+convert_date(datetab[1:index])+" "+convert[datetab[index]]+" "+convert_date(datetab[index+1:]))
            except ValueError:
                pass

        # Having prefix

        if datetab[0] in list(convert.keys()):
            return(convert[datetab[0]]+" "+convert_date(datetab[1:]))

        # Skip 'le' prefix

        if datetab[0] == 'le':
            idx = 1

        # In case of french language remove the 'er' prefix

        if datetab[idx] == "1er":
            datetab[idx] = "1"

        months = dict(babel.dates.get_month_names(width='wide', locale='fr'))

        try:
            # day month year
            bd1 = datetab[idx]+" "+str(list(months.keys())[list(months.values()).index(datetab[idx+1])])+" "+datetab[idx+2][0:4]
            bd2 = babel.dates.parse_date(bd1, locale='fr')
        except:
            # day monthnum year 
            bd1 = datetab[idx]+" "+datetab[idx+1]+" "+datetab[idx+2][0:4]
            bd2 = babel.dates.parse_date(bd1, locale='fr')

        return(bd2.strftime("%d %b %Y").upper())
    except:
        display( "Date error: %s"%(' '.join(datetab)), error=True )
        return "UNKNOW"

#-------------------------------------------------------------------------
#
# Generic functions
#
#-------------------------------------------------------------------------

def clean_query( url ):
    queries = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if len(queries) > 0:
        queries_to_keep = [ 'm', 'v', 'p', 'n', 'oc', 'i' ]

        removed_queries = {k: v for k, v in queries.items() if k not in queries_to_keep + ['lang', 'pz', 'nz', 'iz']}
        if len(removed_queries) > 0:
            display( "Removed queries: %s"%(removed_queries) )

        if 'n' not in queries:
            queries['n'] = ""

        if 'p' not in queries:
            queries['p'] = ""

        return urllib.parse.urlencode({k: v for k, v in queries.items() if k in queries_to_keep}, doseq=True)
    else:
        return url

def event( obj, tag, date, place ): 
    text = ""
    if isinstance( obj, dict ):
        data = obj
    else:
        data = vars(obj)
    if date in data or place in data: # date in vars(obj)
        text = text + "1 %s\n"%(tag)
        if date in data:
            text = text + "2 DATE %s\n"%(data[date])
        if place in data:
            text = text + "2 PLAC %s\n"%(data[place])
    return text

#-------------------------------------------------------------------------
#
# WikiTree class
#
#-------------------------------------------------------------------------

class WikiTree:

    # -------------------------------------------------------------------------
    # __init__
    # -------------------------------------------------------------------------
    def __init__(self):
        pass

    # -------------------------------------------------------------------------
    # scrap
    # -------------------------------------------------------------------------

    def scrap( self, person, url, force = False ):
        pass

#-------------------------------------------------------------------------
#
# Geneanet class
#
#-------------------------------------------------------------------------

class Geneanet:

    # -------------------------------------------------------------------------
    # __init__
    # -------------------------------------------------------------------------
    def __init__(self):
        pass

    # -------------------------------------------------------------------------
    # _load
    # -------------------------------------------------------------------------
    def _load( self, url, force = False ):

        try:
            output_folder = ICLOUD_PATH / re.sub( r'^/', '', urllib.parse.urlparse(url).path )
            output_folder.mkdir(parents=True, exist_ok=True)

            if len(urllib.parse.urlparse(url).query) == 0:
                output_file = "repository"
            else:
                output_file = clean_query(url).replace( '=', "_" ).replace( '+', " " ).replace( '&', "." )

            output_txt = output_folder / (output_file + ".txt")

            # force fr language

            queries = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
            if 'lang' in queries:
                if queries['lang'] != 'fr':
                    url = url.replace( "lang=" + queries['lang'], "lang=fr" )
            elif '?' in url:
                url = url.replace( "?", "?lang=fr&" )
            else:
                url = url + "?lang=fr"

            browser = None

            if force == True or not output_txt.exists():

                display( 'Load from %s'%(url))

                # Chrome setup

                chrome_options = webdriver.ChromeOptions()
                # chrome_options.add_argument("--headless")  # Headless mode to avoid opening a browser window
                chrome_options.add_argument("--kiosk-printing")  # Enables silent printing
                chrome_options.add_argument("--disable-gpu")  # Disables GPU acceleration (helpful in some cases)

                # Configure Chrome print settings to save as PDF
                output_pdf = output_folder / (output_file + ".pdf")
                output_pdf.unlink(missing_ok=True)   

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
                perso = soup.find("div", {"id": "perso"})

                if not perso:
                    perso = soup.find("div", {"id": "content"})

                # process PDF
                try:
                    # Use Chrome DevTools Protocol (CDP) to print as PDF
                    pdf_settings = {
                        "landscape": False,
                        "displayHeaderFooter": True,
                        "printBackground": False,
                        # "preferCSSPageSize": True
                    }

                    # Execute CDP command to save as PDF
                    pdf_data = browser.execute_cdp_cmd("Page.printToPDF", pdf_settings)

                    # Save PDF to file
                    output_pdf.write_bytes(base64.b64decode(pdf_data["data"]))
                except:
                    display( 'Failed to save PDF: %s'%(output_pdf), error=True )

                # process perso

                try:
                    output_txt.unlink(missing_ok=True)   

                    NL = "\n"
                    NC = 132

                    output_txt.write_text( perso.prettify() )
                except:
                    display( 'Failed to save HTML: %s'%(output_txt), error=True )


            else:
                display( 'Read from %s'%(output_txt))
                perso = BeautifulSoup( output_txt.read_text(), 'html.parser' )

        except:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            message = f'Exception [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
            display( message, error=True )
            perso = None

        if browser:
            browser.quit()

        return perso

    # -------------------------------------------------------------------------
    # _read
    # -------------------------------------------------------------------------

    def _read( self, url, force = False ):

        perso = self._load( url, force )

        # Parse content to sections

        contents = []

        Section = namedtuple("Section", "name content")

        try:
            # extract the geneanet sections

            comments = perso.find_all(string=lambda text: isinstance(text, Comment))

            for comment in comments:
                if ' ng' in comment or 'arbre' in comment.lower():
                    continue

                # Extract comment section
                extracted_content = []
                for sibling in comment.next_siblings:
                    if isinstance( sibling, Comment ):
                        break
                    extracted_content.append(str(sibling))
                extracted_soup = BeautifulSoup( ''.join([i for i in extracted_content if i != '\n']), 'html.parser' )

                # Remove <a> tags with href containing "javascript"
                a_tags = extracted_soup.find_all('a')
                for a_tag in a_tags:
                    href = a_tag.get('href')
                    if href and 'javascript' in href.lower():
                        a_tag.decompose()

                contents = contents + [Section( comment.strip(), extracted_soup )]

                comment.extract()

        except:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            message = f'Exception [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
            display( message, error=True )

        return contents

    # -------------------------------------------------------------------------
    # _scrap_notes
    # -------------------------------------------------------------------------
    def _scrap_notes( self, notes, str ):

        output = ''
        soup = BeautifulSoup(str, 'html.parser')

        try: # H2
            tag = '\n'.join(line for line in soup.find('h2').get_text().split('\n') if line.strip() != "").strip()
            line = tag + '\n' + "="*len(tag) + '\n'*2
            try: # H3
                tag = '\n'.join(line for line in soup.find('h3').get_text().split('\n') if line.strip() != "").strip()
                line = line + tag + '\n' + "-"*len(tag) + '\n'*2
            except:
                pass
            # DIV
            tag = '\n'.join(line for line in soup.find('div').get_text().split('\n') if line.strip() != "").strip()
            if len(tag) > 0:
                output = output + line + tag + '\n'*2
        except:
            pass

        try: # LI - RELATED
            lines = soup.find_all('li')
            for line in lines:
                output = output + '- ' + ' '.join(line for line in line.get_text().replace('\n',' ').split(' ') if line.strip() != "").strip() + '\n'
        except:
            pass

        try: # TABLE - TIMELINE
            table = soup.find('table', class_=re.compile(r'^ligne_vie'))
            for row in table.find_all("tr"):
                try:
                    cells = row.find_all("td")
                    td = cells[1]
                    
                    for tag in td.find_all(['span', 'bdo', 'a']):
                        tag.unwrap()

                    for br in cells[1].find_all("br"):
                        br.replace_with("<br>")  

                    cleaned_html = cells[1].get_text(" ", strip=True)
                    cleaned_html = re.sub(r'[ \t]+', ' ', cleaned_html)  # Remove extra spaces (except newlines)
                    cleaned_html = re.sub(r'\n+', ' ', cleaned_html)  # Replace newlines with spaces
                    cleaned_html = re.sub(r'(<br\s*/?>)\s+', r'\1', cleaned_html)  # Remove spaces after <br>
                    cleaned_html = re.sub(r'\s+(<br\s*/?>)', r'\1', cleaned_html)  # Remove spaces before <br>
                    cleaned_html = re.sub(r'\s+([,:])', r'\1', cleaned_html)  # Remove spaces before comma or column
                    cleaned_html = re.sub(r'<br>', r'\n', cleaned_html)  # Replace <br> with new line

                    output = output + '- ' + cleaned_html + '\n'
                except:
                    pass
        except:
            pass

        return notes + ('\n' if ( len(notes) > 0 and len(output) > 0 ) else '') + output

    # -------------------------------------------------------------------------
    # _scrap_medias
    # -------------------------------------------------------------------------
    def _scrap_medias(self):
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
        pass

    # -------------------------------------------------------------------------
    # _scrap_family
    # -------------------------------------------------------------------------
    
    def _scrap_family( self, personref, soup ):

        family = GFamily()

        try:
            marriage = soup.find("em").get_text()
        except:
            marriage = None
                
        # marriage date
        try:
            family._marriagedate = convert_date(marriage.split(',')[0].split()[1:])
        except:
            pass

        # marriage place
        try:
            family._marriageplace = marriage[marriage.find(',') + 1:].strip()
            family._marriageplace = ",".join( item.strip() for item in family._marriageplace.split(",") )
        except:
            pass

        # spouses ref
        try:
            # first <a> can be a ref to sosa
            family._spousesref = [ clean_query( personref ), clean_query( [a for a in soup.find_all('a') if a.get_text(strip=True)][0]['href'] ) ]
            
        except:
            family._spousesref = [ clean_query( personref ), None ]

        # annulation date
        if 'annulé' in soup.get_text().lower():
            display("Add annulation processing")
            family._annulationdate = None

        # divorce date
        if 'divorcé' in soup.get_text().lower():
            display("Add divorce processing")
            family._divorcedate = None

        # engagement date
        if 'annulé' in soup.get_text().lower():
            display("Add engagement processing")
            family._engagementdate = None

        # publish date
        if 'bans' in soup.get_text().lower():
            display("Add publish processing")
            family._publishdate = None

        # license date
        if 'license' in soup.get_text().lower():
            display("Add license processing")
            family._licensedate = None

        # separation date
        if 'séparé' in soup.get_text().lower():
            display("Add separation processing")
            family._separationdate = None

        # childs
        childsref = []
        try:
            for item in soup.find("ul").find_all( "li", recursive=False ):
                # first <a> can be a ref to sosa
                childsref = childsref + [ clean_query( [a for a in item.find_all('a') if a.get_text(strip=True)][0]['href'] ) ]
            family._childsref = childsref
        except:
            pass

        return family

    # -------------------------------------------------------------------------
    # scrap
    # -------------------------------------------------------------------------

    def scrap( self, person, url, force = False ):

        try:
            # Reference
            person._ref = clean_query( url )

            # read web page
            
            sections = self._read( url, force )

            for section in sections:

                # -------------------------------------------------------------
                # Portrait section
                # -------------------------------------------------------------
                if 'portrait' in section.name.lower():

                    # first and last names
                    try:
                        names = section.content.find("div", {"id" : "person-title"}).find_all_next("a")

                        person._portrait['firstname'] = names[0].get_text().replace('\n', '').strip().title()
                        person._portrait['lastname'] = names[1].get_text().replace('\n', '').strip().title()
                    except:
                        pass

                    # sex: should return M or F
                    try:
                        sex = section.content.find("div", {"id" : "person-title"}).find_all_next("img", alt=True)

                        person._portrait['sex'] = sex[0]['alt']
                        if person._portrait['sex'] == 'H':
                            person._portrait['sex'] = 'M'
                    except:
                        person._portrait['sex'] = 'U'

                    # birth
                    try:
                        birth = section.content.find_all('li', string=lambda text: "Né" in text if text else False)[0].get_text()
                    except:
                        birth = None

                    try:
                        person._portrait['birthdate'] = convert_date(birth.split('-')[0].split()[1:])
                    except:
                        pass

                    try:
                        person._portrait['birthplace'] = birth[birth.find('-') + 1:].strip()
                        person._portrait['birthplace'] = ",".join( item.strip() for item in person._portrait['birthplace'].split(",") )
                    except:
                        pass

                    # death
                    try:
                        death = section.content.find_all('li', string=lambda text: "Décédé" in text if text else False)[0].get_text()
                    except:
                        death = None

                    try:
                        person._portrait['deathdate'] = convert_date(death.split('-')[0].split()[1:])
                    except:
                        pass

                    try:
                        person._portrait['deathplace'] = re.split(f"{re.escape(",\nà l'âge")}|{re.escape(", à l'âge")}", death[death.find('-') + 1:].strip())[0]
                        person._portrait['deathplace'] = ",".join( item.strip() for item in person._portrait['deathplace'].split(",") )
                    except:
                        pass

                    # baptem
                    try:
                        baptem = section.content.find_all('li', string=lambda text: "baptisé" in text.lower() if text else False)[0].get_text()
                        display("Processing baptem ")
                    except:
                        baptem = None

                    try:
                        person._portrait['baptemdate'] = convert_date(baptem.split('-')[0].split()[1:])
                    except:
                        pass

                    try:
                        person._portrait['baptemplace'] = baptem[baptem.find('-') + 1:].strip()
                        person._portrait['baptemplace'] = ",".join( item.strip() for item in person._portrait['baptemplace'].split(",") )
                    except:
                        pass

                    # burial
                    try:
                        burial = section.content.find_all('li', string=lambda text: "inhumé" in text.lower() if text else False)[0].get_text()
                        display("Processing burial")
                    except:
                        burial = None

                    try:
                        person._portrait['burialdate'] = convert_date(burial.split('-')[0].split()[1:])
                    except:
                        pass

                    try:
                        person._portrait['burialplace'] = burial[burial.find('-') + 1:].strip()
                        person._portrait['burialplace'] = ",".join( item.strip() for item in person._portrait['burialplace'].split(",") )
                    except:
                        pass

                    # occupation
                    try:
                        lines = section.content.find_all('li')
                        for line in lines:
                            if 'né' not in line.get_text() and 'décédé' not in line.get_text() and 'baptisé' not in line.get_text() and 'inhumé' not in line.get_text():
                                display("Processing occupation: %s"%(self._occupation))
                                person._occupation = line.get_text()
                                break
                    except:
                        occupation = ""

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
                        person._parentsref = [clean_query( item['href'] ) for item in section.content.find_all("a") if len( item.find_all("img", {"alt" : "sosa"}) ) == 0]
                    except:
                        pass

                # -------------------------------------------------------------
                # Families section
                # -------------------------------------------------------------
                elif 'union' in section.name.lower():
                    try:
                        person._families = []
                        unions = section.content.find('ul', class_=re.compile('.*fiche_union.*') ).find_all( "li", recursive=False )

                        for union in unions:
                            try:                                
                                person._families = person._families + [ self._scrap_family( person._ref, union ) ]
                            except:
                                pass
                    except:
                        pass

                # -------------------------------------------------------------
                # Freres et Soeurs section
                # -------------------------------------------------------------
                elif 'freres et soeurs' in section.name.lower():
                    try:
                        for item in section.content.find("ul").find_all( "li", recursive=False ):
                            tag_a = item.find('a')
                            if tag_a.get_text(strip=True): 
                                # first <a> can be a ref to sosa
                                person._siblingsref = person._siblingsref + [ clean_query( tag_a['href'] ) ]
                    except:
                        pass

                # -------------------------------------------------------------
                # Famille section
                # -------------------------------------------------------------
                elif 'famille' in section.name.lower():
                    if len(section.content) > 0:
                        display("Add processing for section: %s"%(section.name))

                # -------------------------------------------------------------
                # Relation, related or notes sections
                # -------------------------------------------------------------
                elif 'relation' in section.name.lower() or 'related' in section.name.lower() or 'notes' in section.name.lower():
                    if len(section.content) > 0:
                        person._notes = self._scrap_notes( person._notes, str(section.content) )

                # -------------------------------------------------------------
                # Sources section
                # -------------------------------------------------------------
                elif 'sources' in section.name.lower():
                    if len(section.content) > 0:
                        try:
                            display("Processing %s"%(section.name))
                            # Remove all elements before the <h2> tag
                            h2_element = section.content.find('h2')
                            if h2_element:
                                for element in h2_element.find_all_previous():
                                    element.decompose()
                            if len(section.content) > 0:
                                person._notes = self._scrap_notes( person._notes, str(section.content) )
                        except:
                            pass

                # -------------------------------------------------------------
                # Unprocess section
                # -------------------------------------------------------------
                else:
                    if len(section.content) > 0:
                        display("Add processing for section: %s"%(section.name))

        except:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            message = f'Exception [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
            display( message, error=True )

    # -------------------------------------------------------------------------
    # informations
    # -------------------------------------------------------------------------
    def informations( self, url, force = False ):

        informations = {}

        try:
            parsed_url = urllib.parse.urlparse(url)

            if parsed_url.scheme != "":

                informations['url'] = urllib.parse.urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))

                perso = self._load( informations['url'], force )

                informations['author'] = perso.select( "div[class*='info-auteur']" )[0].find("strong").get_text().strip()
                informations['persons'] = int(re.sub(r'\D', '', perso.select( "span[class*='stats-number']" )[0].get_text()))
                informations['lastchange'] = [ p for p in perso.select( "p[class*='text-light']" ) if 'Dernière' in p.get_text() ][0]
                informations['lastchange'] = convert_date( informations['lastchange'].find("span").get_text().split( '/' ))

        except:
            pass

        return informations

#----------------------------------------------------------------------------------------------------------------------------------
#
# GFamily class
#
#----------------------------------------------------------------------------------------------------------------------------------

class GFamily():

    # -------------------------------------------------------------------------
    # __init__
    # -------------------------------------------------------------------------

    def __init__(self):
        pass

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

        self._notes = ""

        if 'geneanet' in url:
            # scrap geneanet page
            geneanet = Geneanet()
            geneanet.scrap( self, url, force )
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
            del p['_notes']
            display( p, title="Person: %s"%(key) )
            if person.notes != "":
                display( person.notes, title="" )

        for key, family in self._families.items():
            display( vars(family), title="Family: %s"%(str(key)) )

###################################################################################################################################
# genealogyscrapping
###################################################################################################################################

def genealogyscrapping( person, ascendants=False, descendants=False, spouses=False, max_levels= 0, force=False, gedcom_file=None):

    try:
        persons = GPersons( max_levels, ascendants, spouses, descendants )
        persons.add_person( person, force )

        if gedcom_file:
            gedcom_file.write_text( persons.gedcom( force ) )

            try:
                import pygedcom

                parser = pygedcom.GedcomParser( str(gedcom_file) )
                parser.parse()
                check = parser.verify()

                display("")
                if check['status'] == 'ok':
                    display(parser.get_stats(), title="Your %s file is valid"%(str(gedcom_file)))
                else:
                    display( check['message'], title="Your %s file is not valid"%(str(gedcom_file)))

            except:
                pass

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        message = f'Something went wrong with scrapping [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
        display( message, error=True )

    return persons

###################################################################################################################################
# main
###################################################################################################################################

def main():

    console.clear()

    display( "GenealogyScrapping", level=1 )

    # Create data folder

    global ICLOUD_PATH

    ICLOUD_PATH = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "GeneanetScrap"
    ICLOUD_PATH.mkdir(exist_ok=True)

    # Process parameters

    parser = argparse.ArgumentParser(description="Export genealogy subtrees into GEDCOM file")
    parser.add_argument("-a", "--ascendants", default=False, action='store_true', help="Includes ascendants (off by default)")
    parser.add_argument("-d", "--descendants", default=False, action='store_true', help="Includes descendants (off by default)")
    parser.add_argument("-s", "--spouses", default=False, action='store_true', help="Includes all spouses (off by default)")
    parser.add_argument("-l", "--level", default=0, type=int, help="Number of level to explore (0 by default)")
    parser.add_argument("-f", "--force", default=False, action='store_true', help="Force preloading web page (off by default)")
    parser.add_argument("searchedperson", type=str, nargs='?', help="Url of the person to search in Geneanet")
    args = parser.parse_args()

    force = args.force
    ascendants = args.ascendants
    descendants = args.descendants
    spouses = args.spouses
    max_levels = args.level

    if max_levels == None:
        max_levels = 0

    if args.searchedperson == None:

        searchedpersons = [
            'https://gw.geneanet.org/lipari?p=leon+desire+louis&n=bessey',              # lipari - Léon Désiré Louis Bessey
            'https://gw.geneanet.org/asempey?n=jantieu&p=margueritte&oc=0',             # asempey - Marguerite Jantieu
            'https://gw.geneanet.org/iraird?p=nicholas&n=le+teuton',                    # iraird - Nicholas le Teuton
            'https://gw.geneanet.org/plongeur?p=charlotte+marie&n=postel',              # plongeur - Charlotte Marie Postel
            'https://gw.geneanet.org/sarahls?p=marcel+marius&n=lhomme',                 # sarahls - Marcel Marius Lhomme
            'https://gw.geneanet.org/balcaraz?n=stefani&oc=1&p=leonard',                # balcaraz - Léonard Stéphani
            'https://gw.geneanet.org/zeking?iz=2&p=6+2+leonard&n=stefani',              # zeking - Léonard Stéphani
            'https://gw.geneanet.org/sanso2b?p=romain+jean+michel&n=burais',            # sanso2b - Romain Jean Michel Burais
            'https://gw.geneanet.org/zlc061?p=marie+rose&n=cler&oc=1',                  # zlc061 - Marie Rose Cler
            'https://gw.geneanet.org/comrade28?iz=0&p=nicholas&n=de+bacqueville',       # comrade28 - Nicholas de Bacqueville
            'https://gw.geneanet.org/12marcel?p=marie+rose&n=cler',                     # 12marcel - Marie Rose Cler
            'https://gw.geneanet.org/pierreb0142?p=desire+antonin&n=bessey',            # pierre0142 - Désiré Antonin Bessey
            'https://gw.geneanet.org/lburais_w?p=milo&n=x&oc=1125',                       # lburais - Milo
            # 'https://gw.geneanet.org/alandur',                                        # alandur
            # 'https://gw.geneanet.org/domale',                                         # domale
            # 'https://gw.geneanet.org/malugi',                                         # malugi
        ]

    else:
        searchedpersons = [ args.searchedperson ]

    params = {
        'force' : force,
        'ascendants' : ascendants,
        'descendants' : descendants,
        'spouses' : spouses,
        'max_levels' : max_levels,
        'searchedpersons' : searchedpersons
    }
    display( params, title="Paramùeters")

    # Process searched persons

    for searchedperson in searchedpersons:

        userid = re.sub( r'^/', '', urllib.parse.urlparse(searchedperson).path )

        # disable screenlock

        process= subprocess.Popen(["caffeinate", "-d"])

        # Scrap geneanet

        gedcom = ICLOUD_PATH / "gedcom" / f"{userid}.ged"
        gedcom.parent.mkdir(parents=True, exist_ok=True)
        gedcom.unlink(missing_ok=True)

        persons = genealogyscrapping( searchedperson, ascendants, descendants, spouses, max_levels, force, gedcom )

        # enable screenlock

        process.terminate()

        # Save logs

        display( "" )

        #output_file = ICLOUD_PATH / "output" / f"{userid}_logs_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.txt"
        output_file = ICLOUD_PATH / "output" / f"{userid}_logs.txt"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.unlink(missing_ok=True)
        output_file.write_text(console.export_text())  # Saves formatted text output

        # Save outcome
        
        console._record_buffer = []

        persons.print()

        output_file = ICLOUD_PATH / "output" / f"{userid}_console.txt"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.unlink(missing_ok=True)
        output_file.write_text(console.export_text())

if __name__ == '__main__':
    main()

