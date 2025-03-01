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
from pathlib import Path
from datetime import datetime

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

# -------------------------------------------------------------------------
# clean_query
# -------------------------------------------------------------------------


def clean_query(url):
    """
    Function to return the query part of an url without unnecessary geneanet queries
    """

    queries = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    if len(queries) > 0:
        queries_to_keep = ['m', 'v', 'p', 'n', 'oc', 'i']

        removed_queries = {k: v for k, v in queries.items() if k not in queries_to_keep + ['lang', 'pz', 'nz', 'iz']}
        if len(removed_queries) > 0:
            display(f"Removed queries: {removed_queries}")

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
# display
# -------------------------------------------------------------------------


console = Console(record=True, width=132)


def display(what=None, title=None, level=0, error=False, exception=False):
    """
    Function to print with Rich console
    """

    try:
        if exception:
            console.print_exception(show_locals=False, max_frames=1)

        elif isinstance(what, list):
            pprint(what)

        elif isinstance(what, dict):

            # console.print(Panel(Pretty(what), title=title, title_align='left'))
            if title:
                console.print('\n', Panel(Text(title), style="green"))
            console.print(Pretty(what))

        elif isinstance(what, str):
            if error:
                console.print(Text(f"[ERROR] {what}", style="bright_white on red"))

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


def console_save(output):
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

    output_file = Path(output).resolve().with_suffix(".pdf")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.unlink(missing_ok=True)

    html = html.replace("<head>", print_options)

    display(f"Starting to write {len(html)} bytes to {str(output_file)} at {datetime.now().strftime('%H:%M:%S')}...")
    HTML(string=html).write_pdf(str(output_file))
    display("... completed")

    console._record_buffer = []
