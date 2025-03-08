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

# ---------------------------------------------------------------------------------------------------------------------------------
#
# Used Python Modules
#
# ---------------------------------------------------------------------------------------------------------------------------------

from pathlib import Path
from datetime import datetime
import base64
import traceback

# https://www.selenium.dev
# https://pypi.org/project/selenium/
# pip3 install selenium

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException

# https://pypi.org/project/beautifulsoup4/
# pip3 install bs4
from bs4 import BeautifulSoup

# https://wkhtmltopdf.org
# download and install
# https://pypi.org/project/pdfkit/
# pip3 install pdfkit
import pdfkit

# https://rich.readthedocs.io/en/stable/
# https://pypi.org/project/rich/
# pip3 install rich

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.pretty import pprint
from rich.pretty import Pretty

# ---------------------------------------------------------------------------------------------------------------------------------
# get_folder
# ---------------------------------------------------------------------------------------------------------------------------------


def get_folder():
    """
    Function to get the home folder for output files
    """

    folder = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "GeneanetScrap"
    folder.mkdir(exist_ok=True)
    return folder

# ---------------------------------------------------------------------------------------------------------------------------------
# display
# ---------------------------------------------------------------------------------------------------------------------------------


console = Console(record=True, width=132)


def display(what=None, title=None, level=0, error=False, exception=False):
    """
    Function to print with Rich console
    """

    try:
        if isinstance(what, list):
            if title:
                console.print('\n', Panel(Text(title), style="green"))
            console.print(Pretty(what))

        elif isinstance(what, dict):

            if title:
                console.print('\n', Panel(Text(title), style="green"))
            console.print(Pretty(what))

        elif isinstance(what, str):
            if exception:
                #console.print(Panel(Text(traceback.format_exc()), title=what, style="red"))
                console.print(Panel(Text(what), style="red"))
                console.print(traceback.format_exc())

            elif error:
                console.print(Text(f"[ERROR] {what}",style="bright_white on red"))

            elif level == 1:
                console.print(Panel(Text(what.upper()), style="black"))

            elif level > 1:
                console.print('\n', Panel(Text(what), style="cyan"), '\n')

            elif title:
                # console.print(Panel(Text(what), title=title))
                console.print('\n', Panel(Text(title), style="cyan"))
                console.print(what)

            else:
                console.print(Text(what))

        elif isinstance(what, Markdown):

            console.print(what)

        elif what:
            pprint(what)

    except Exception as e:
        display(f"Display: {type(e).__name__}", error=True)
        console.print_exception(show_locals=False, max_frames=1)

# ---------------------------------------------------------------------------------------------------------------------------------
# console_clear
# ---------------------------------------------------------------------------------------------------------------------------------


def console_clear():
    """
    Function to clear the Rich console
    """
    console.clear()

# ---------------------------------------------------------------------------------------------------------------------------------
# console_save
# ---------------------------------------------------------------------------------------------------------------------------------


def console_save(output):
    """
    Function to save text from Rich console into a PDF file
    """

    content = console.export_html(inline_styles=True)

    output_file = Path(output).resolve().with_suffix(".pdf")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.unlink(missing_ok=True)

    start_time = datetime.now()
    display(f"Writing pdfkit {len(content):,} bytes to {str(output_file.relative_to(Path(get_folder())))} at {start_time.strftime('%H:%M:%S')}...")

    options = {
    'orientation': 'landscape',     # Set the orientation to landscape
    'page-size': 'A4',              # Optional: Page size
    'encoding': 'UTF-8',            # Make sure to set encoding to UTF-8
    'dpi': 72,                      # Reduces the DPI for lower quality but smaller file size
    }

    pdfkit.from_string(content, str(output_file), options=options)

    duration = (datetime.now() - start_time).total_seconds()
    display(f"... completed in {duration:,.2f}s\n")

    console._record_buffer = []

# -------------------------------------------------------------------------
# load_chrome
# -------------------------------------------------------------------------


def load_chrome(url, output_file, force=False):
    """
    Function to load content of a web page through Chrome (and save it in pdf file)
    """

    output_txt = output_file.resolve().with_suffix(".txt")

    if force is True or not output_txt.exists():

        try:
            display(f'Load from {url}')

            output_pdf = output_file.resolve().with_suffix(".pdf")

            html = None

            headless = url.find('http') == -1

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
                    display(f"Clickable: {type(e).__name__}", exception=True)

            # Process PDF
            try:
                # Use Chrome DevTools Protocol (CDP) to print as PDF
                pdf_settings = {
                    "landscape": False,
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
                display(f"Failed to save [{output_pdf}]: {type(e).__name__}", exception=True)

            # Get HTML

            html = browser.page_source

        except Exception as e:
            display(f"Failed to load [{url}]: {type(e).__name__}", exception=True)

        if browser:
            browser.quit()

        try:
            output_txt.unlink(missing_ok=True)
            output_txt.write_text(BeautifulSoup(html, 'html.parser').prettify())
        except Exception as e:
            display(f"Failed to save [{output_txt}]: {type(e).__name__}", exception=True)


    else:
        display(f'Read from {output_txt}')
        html = output_txt.read_text()

    return html
