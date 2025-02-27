# common
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
Package with common elements
"""

# -------------------------------------------------------------------------
#
# Used Python Modules
#
# -------------------------------------------------------------------------

import urllib
import os
import sys
import base64
from pathlib import Path

# https://pypi.org/project/beautifulsoup4/
# pip3 install bs4

from bs4 import BeautifulSoup

# https://pypi.org/project/babel/
# pip3 install babel
import babel
import babel.dates

# https://pypi.org/project/weasyprint/
# pip3 install weasyprint
from weasyprint import HTML

# https://rich.readthedocs.io/en/stable/
# https://pypi.org/project/rich/
# pip3 install rich

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.pretty import pprint
from rich.pretty import Pretty

# https://pypi.org/project/selenium/
# pip3 install selenium

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException

# -------------------------------------------------------------------------
# convert_date
# -------------------------------------------------------------------------

def convert_date(datetab):
    """
    Function to convert a french date to GEDCOM date
    """

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
            return None

        idx = 0

        # clean
        datetab = [ v.strip() for v in datetab ]

        # Assuming there is just a year and last element is the year

        if len(datetab) == 1 or datetab[0] == 'en':
            # avoid a potential month
            if datetab[-1].isalpha():
                return datetab[-1][0:4]

            # avoid a potential , after the year
            elif datetab[-1].isnumeric():
                return datetab[-1][0:4]

        # Between date

        if datetab[0] == 'entre':
            try:
                index = datetab.index("et")
                return convert[datetab[0]] + " " + convert_date(datetab[1:index]) + " " + convert[datetab[index]] + " " + convert_date(datetab[index+1:])
            except ValueError:
                pass

        # Having prefix

        if datetab[0] in convert:
            return convert[datetab[0]] + " " + convert_date(datetab[1:])

        # Skip 'le' prefix

        if datetab[0] == 'le':
            idx = 1

        # In case of french language remove the 'er' prefix

        if datetab[idx] == "1er":
            datetab[idx] = "1"

        months = dict(babel.dates.get_month_names(width='wide', locale='fr'))

        # Just month and year
        if datetab[idx].lower() in months.values():
            bd1 = "1" + " " + str(list(months.keys())[list(months.values()).index(datetab[idx])]) + " " + datetab[idx+1][0:4]
            bd2 = babel.dates.parse_date(bd1, locale='fr')
            return bd2.strftime("%b %Y").upper()

        try:
            # day month year
            bd1 = datetab[idx] + " " + str(list(months.keys())[list(months.values()).index(datetab[idx+1])]) + " " + datetab[idx+2][0:4]
            bd2 = babel.dates.parse_date(bd1, locale='fr')
        except ValueError:
            # day monthnum year
            bd1 = datetab[idx] + " " + datetab[idx+1] + " " + datetab[idx+2][0:4]
            bd2 = babel.dates.parse_date(bd1, locale='fr')
        except Exception as e:
            display( f"Convert date: {type(e).__name__}", error=True )

        return bd2.strftime("%d %b %Y").upper()

    except Exception as e:
        display( f"Date error ({type(e).__name__}): {' '.join(datetab)}", error=True )
        raise ValueError from e

# -------------------------------------------------------------------------
# clean_query
# -------------------------------------------------------------------------

def clean_query( url ):
    """
    Function to return the query part of an url without unnecessary geneanet queries
    """

    queries = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if len(queries) > 0:
        queries_to_keep = [ 'm', 'v', 'p', 'n', 'oc', 'i' ]

        removed_queries = {k: v for k, v in queries.items() if k not in queries_to_keep + ['lang', 'pz', 'nz', 'iz']}
        if len(removed_queries) > 0:
            display( f"Removed queries: {removed_queries}" )

        if 'n' not in queries:
            queries['n'] = ""

        if 'p' not in queries:
            queries['p'] = ""

        return urllib.parse.urlencode({k: v for k, v in queries.items() if k in queries_to_keep}, doseq=True)
    else:
        return url

# -------------------------------------------------------------------------
# get_folder
# -------------------------------------------------------------------------

def get_folder():
    """
    Function to get the home folder for output files
    """

    folder = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "GeneanetScrap"
    folder.mkdir(exist_ok=True)
    return folder

# -------------------------------------------------------------------------
# convert_to_rtf
# -------------------------------------------------------------------------

def convert_to_rtf( text ):
    """
    Function to convert text to rtf
    """

    def ansi_to_rtf( text ):
        """Convert ANSI text to RTF-safe format."""
        converted_text = ''.join(f"\\u{ord(c)}?" if ord(c) > 127 else c for c in text)
        converted_text = converted_text.replace( "\n", "\\par ")

        return converted_text

    rtf_content = r"""{\rtf1\ansi\deff0
{\fonttbl{\f0\fnil\fcharset0 Courier New;}}
\viewkind4\uc1\pard\f0\fs24 %s \par
}""" % ansi_to_rtf( text )

    return rtf_content

# -------------------------------------------------------------------------
# display
# -------------------------------------------------------------------------

console = Console(record=True, width=132)

def display( what=None, title=None, level=0, error=False, exception=False ):
    """
    Function to print with Rich console
    """

    try:
        if exception:
            console.print_exception(show_locals=False, max_frames=1)

        elif isinstance( what, list ):
            pprint( what )

        elif isinstance( what, dict ):

            # console.print( Panel( Pretty(what), title=title, title_align='left' ) )
            console.print( '\n', Panel( Text(title), style="green" ) )
            console.print( Pretty(what) )

        elif isinstance( what, str ):
            if error:
                console.print( Text( what, style="bright_white on red" ))

            elif level == 1:
                console.print( Panel( Text(what.upper()), style="black" ))

            elif level > 1:
                console.print( '\n', Panel( Text(what), style="cyan" ), '\n')

            elif title:
                # console.print( Panel( Text(what), title=title ))
                console.print( '\n', Panel( Text(title), style="cyan" ) )
                console.print( what)

            else:
                console.print( Text(what) )

        elif isinstance( what, Markdown ):

            console.print( what )

        elif what:
            pprint( what )

    except Exception as e:
        display( f"Display: {type(e).__name__}", error=True )
        console.print_exception(show_locals=False, max_frames=1)

# -------------------------------------------------------------------------
# console_clear
# -------------------------------------------------------------------------

def console_clear():
    """
    Function to clear the Rich console
    """
    console.clear()

# -------------------------------------------------------------------------
# console_save
# -------------------------------------------------------------------------

def console_save( output ):
    """
    Function to save text from Rich console into a PDF file
    """

    print_options = """<head>
        <style>
            @page {
                size: A4 landscape;
                margin: 0.25in;
            }
            body {
                font-family: Courier, monospace;
                font-size: 10pt;
            }
    """

    html = console.export_html()

    # output_file = Path(output).resolve().with_suffix(".html")
    # output_file.parent.mkdir(parents=True, exist_ok=True)
    # output_file.unlink(missing_ok=True)

    # output_file.write_text( html )

    output_file = Path(output).resolve().with_suffix(".pdf")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.unlink(missing_ok=True)

    html = html.replace( "<head>", print_options )

    # soup=BeautifulSoup( html, "html.parser")
    # html = " ".join(soup.prettify().split())

    display( f"Starting to write {len(html)} bytes ...")
    HTML(string=html ).write_pdf(str(output_file))
    display( "... completed")

    console._record_buffer = []

# -------------------------------------------------------------------------
# load_chrome
# -------------------------------------------------------------------------

def load_chrome( url, output_pdf=None, landscape=False):
    """
    Function to load a page with Chrome then save as pdf and return html
    """

    html = None
    headless = urllib.parse.urlparse(url).scheme == 'file'

    try:
        # Chrome setup

        chrome_options = webdriver.ChromeOptions()
        if headless:
            chrome_options.add_argument("--headless")  # Headless mode to avoid opening a browser window
        chrome_options.add_argument("--kiosk-printing")  # Enables silent printing
        chrome_options.add_argument("--disable-gpu")  # Disables GPU acceleration (helpful in some cases)

        # Configure Chrome print settings to save as PDF
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        output_pdf.unlink(missing_ok=True)

        chrome_options.add_experimental_option("prefs", {
            "printing.print_preview_sticky_settings.appState": '{"recentDestinations":[{"id":"Save as PDF","origin":"local"}],"selectedDestinationId":"Save as PDF","version":2}',
            "savefile.default_directory": str(output_pdf)
        })

        service = Service()  # No need to specify path if using Selenium 4.6+
        browser = webdriver.Chrome(service=service, options=chrome_options)

        # let's go browse

        browser.get(url)

        if not headless:

            # wait for button click

            try:
                consent_button = WebDriverWait(browser, 20).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button#tarteaucitronPersonalize2"))
                )
                ActionChains(browser).move_to_element(consent_button).click().perform()
            except TimeoutException:
                pass
            except Exception as e:
                display( f"Clickable: {type(e).__name__}", error=True )

        # Process PDF
        try:
            # Use Chrome DevTools Protocol (CDP) to print as PDF
            pdf_settings = {
                "landscape": landscape,
                "paperWidth": 8.5,
                "paperHeight": 11,
                "displayHeaderFooter": True,
                "printBackground": False
            }

            # Execute CDP command to save as PDF
            pdf_data = browser.execute_cdp_cmd("Page.printToPDF", pdf_settings)

            # Save PDF to file
            output_pdf.write_bytes(base64.b64decode(pdf_data["data"]))
        except Exception as e:
            display( f"Save PDF: {type(e).__name__}", error=True )
            display( f'Failed to save PDF: {output_pdf}', error=True )

        # Get HTML

        html = browser.page_source

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        message = f'Exception {e} [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
        display( message, error=True )
        display( message, exception=True )
        html = None

    if browser:
        browser.quit()

    return html
