# geneanet
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
Package to process Geneanet pages
"""

# -------------------------------------------------------------------------
#
# Standard Python Modules
#
# -------------------------------------------------------------------------

import re
from collections import namedtuple
import sys
import os
import urllib
import base64

# https://pypi.org/project/beautifulsoup4/
# pip3 install bs4

from bs4 import BeautifulSoup, Comment

# https://pypi.org/project/babel/
# pip3 install babel
import babel
import babel.dates

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
#
# Internal Python Modules
#
# -------------------------------------------------------------------------

from common import display, get_folder, clean_query
from objects import Informations, Individual, Family

# -------------------------------------------------------------------------
#
# Geneanet class
#
# -------------------------------------------------------------------------


class Geneanet:
    """
    Class to process Geneanet content
    """

    # -------------------------------------------------------------------------
    # __init__
    # -------------------------------------------------------------------------
    def __init__(self):
        self._folder = get_folder()
        self._html = None

    # -------------------------------------------------------------------------
    # _load
    # -------------------------------------------------------------------------
    def _load(self, url, force=False):

        try:
            output_folder = self._folder / re.sub(r'^/', '', urllib.parse.urlparse(url).path)
            output_folder.mkdir(parents=True, exist_ok=True)

            if len(urllib.parse.urlparse(url).query) == 0:
                output_file = "repository"
            else:
                output_file = clean_query(url).replace('=', "_").replace('+', " ").replace('&', ".")

            output_txt = output_folder / (output_file + ".txt")

            # force fr language

            queries = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
            if 'lang' in queries:
                if queries['lang'] != 'fr':
                    url = url.replace("lang=" + queries['lang'], "lang=fr")
            elif '?' in url:
                url = url.replace("?", "?lang=fr&")
            else:
                url = url + "?lang=fr"

            if force is True or not output_txt.exists():

                display(f'Load from {url}')

                output_pdf = output_folder / (output_file + ".pdf")

                self._html = None
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
                            display(f"Clickable: {type(e).__name__}", error=True)

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
                        display(f"Save PDF: {type(e).__name__}", error=True)
                        display(f'Failed to save PDF: {output_pdf}', error=True)

                    # Get HTML

                    self._html = browser.page_source

                except Exception as e:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    message = f'Exception {e} [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
                    display(message, error=True)
                    display(message, exception=True)

                if browser:
                    browser.quit()

                # Get content in perso bloc

                soup = BeautifulSoup(self._html, 'html.parser')
                self._html = soup.find("div", {"id": "perso"})

                if not self._html:
                    self._html = soup.find("div", {"id": "content"})

                # process perso

                try:
                    output_txt.unlink(missing_ok=True)
                    output_txt.write_text(self._html.prettify())
                except Exception as e:
                    display(f"Save HTML: {type(e).__name__}", error=True)
                    display(f'Failed to save HTML: {output_txt}', error=True)

            else:
                display(f'Read from {output_txt}')
                self._html = BeautifulSoup(output_txt.read_text(), 'html.parser')

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            message = f'Exception {e} [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
            display(message, error=True)
            display(message, exception=True)
            self._html = None

        return self._html

    # -------------------------------------------------------------------------
    # _read
    # -------------------------------------------------------------------------

    def _read(self, url, force=False):

        perso = self._load(url, force)

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
                    if isinstance(sibling, Comment):
                        break
                    extracted_content.append(str(sibling))
                extracted_soup = BeautifulSoup(''.join([i for i in extracted_content if i != '\n']), 'html.parser')

                # Remove <a> tags with href containing "javascript"
                a_tags = extracted_soup.find_all('a')
                for a_tag in a_tags:
                    href = a_tag.get('href')
                    if href and 'javascript' in href.lower():
                        a_tag.decompose()

                contents = contents + [Section(comment.strip(), extracted_soup)]

                comment.extract()

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            message = f'Exception {e} [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
            display(message, error=True)

        return contents

    # -------------------------------------------------------------------------
    # _place
    # -------------------------------------------------------------------------

    def _place(self, place):
        """
        Function to get a place from GeoNames
        """

        return place

    # -------------------------------------------------------------------------
    # _extract_date_place
    # -------------------------------------------------------------------------

    def _extract_date_place(self, content, key, pattern):

        try:
            date = place = None
            exist = True

            event = re.search(pattern, content)

            display(f"{key.upper()} {content} [{event.group('date')}] [{event.group('alt')}] [{event.group('place')}]")

            try:  # first date

                date = self._convert_date(event.group('date').strip().split())

            except (IndexError, ValueError):
                try:  # second date

                    date = self._convert_date(event.group('alt').strip().split())

                except (IndexError, ValueError, AttributeError):
                    pass
                except Exception as e:
                    display(f"{key.upper()} - date 2: {type(e).__name__}", error=True)
            except Exception as e:
                display(f"{key.upper()} - date 1: {type(e).__name__}", error=True)

            try:  # place

                # if date:
                place = event.group('place').strip()

            except AttributeError:
                pass
            except Exception as e:
                display(f"{key.upper()} - place: {type(e).__name__}", error=True)

            if event and not date and not place:
                display(f"{key.upper()}: [{content}]", error=True)

        except (AttributeError, NameError):
            exist = None
        except Exception as e:
            display(f"{key.upper()}: {type(e).__name__}", error=True)

        return exist, date, place

    # -------------------------------------------------------------------------
    # _convert_date
    # -------------------------------------------------------------------------

    def _convert_date(self, datetab):
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
            datetab = [v.strip() for v in datetab]

            # Assuming there is just a year and last element is the year

            if len(datetab) == 1 or datetab[0] == 'en':
                # avoid a potential month
                # if datetab[-1].isalpha():
                #     return datetab[-1][0:4]

                # avoid a potential , after the year
                # elif datetab[-1].isnumeric():
                if datetab[-1].isnumeric():
                    return datetab[-1][0:4]

            # Between date

            if datetab[0] == 'entre':
                try:
                    index = datetab.index("et")
                    return convert[datetab[0]] + " " + self._convert_date(datetab[1:index]) + " " + convert[datetab[index]] + " " + self._convert_date(datetab[index + 1:])
                except ValueError:
                    pass

            # Having prefix

            if datetab[0] in convert:
                return convert[datetab[0]] + " " + self._convert_date(datetab[1:])

            # Skip 'le' prefix

            if datetab[0] == 'le':
                idx = 1

            # In case of french language remove the 'er' prefix

            if datetab[idx] == "1er":
                datetab[idx] = "1"

            months = dict(babel.dates.get_month_names(width='wide', locale='fr'))

            # Just month and year
            if datetab[idx].lower() in months.values():
                bd1 = "1" + " " + str(list(months.keys())[list(months.values()).index(datetab[idx])]) + " " + datetab[idx + 1][0:4]
                bd2 = babel.dates.parse_date(bd1, locale='fr')
                return bd2.strftime("%b %Y").upper()

            try:
                # day month year
                bd1 = datetab[idx] + " " + str(list(months.keys())[list(months.values()).index(datetab[idx + 1])]) + " " + datetab[idx + 2][0:4]
                bd2 = babel.dates.parse_date(bd1, locale='fr')
            except ValueError:
                # day monthnum year
                bd1 = datetab[idx] + " " + datetab[idx + 1] + " " + datetab[idx + 2][0:4]
                bd2 = babel.dates.parse_date(bd1, locale='fr')
            except IndexError:
                pass
            except Exception as e:
                display(f"Convert date: {type(e).__name__}", error=True)

            return bd2.strftime("%d %b %Y").upper()

        except Exception as e:
            display(f"Date error ({type(e).__name__}): {' '.join(datetab)}", error=True)
            raise ValueError from e

    # -------------------------------------------------------------------------
    # _scrap_notes
    # -------------------------------------------------------------------------
    def _scrap_notes(self, html):

        output = ''

        # stop at Photos & Documents section
        idx = html.find("Photos")
        html = html[:idx] if idx != -1 else html

        soup = BeautifulSoup(html, 'html.parser')

        try:  # H2
            tag = '\n'.join(line for line in soup.find('h2').get_text().split('\n') if line.strip() != "").strip()
            line = tag + '\n' + "=" * len(tag) + '\n' * 2
            try:  # H3
                tag = '\n'.join(line for line in soup.find('h3').get_text().split('\n') if line.strip() != "").strip()
                line = line + tag + '\n' + "-" * len(tag) + '\n' * 2
            except AttributeError:
                pass
            except Exception as e:
                display(f"Notes h3: {type(e).__name__}", error=True)
            # DIV
            tag = '\n'.join(line for line in soup.find('div').get_text().split('\n') if line.strip() != "").strip()
            if len(tag) > 0:
                output = output + line + tag + '\n' * 2
        except AttributeError:
            pass
        except Exception as e:
            display(f"Notes h2: {type(e).__name__}", error=True)

        try:  # LI - RELATED
            lines = soup.find_all('li')
            for line in lines:
                output = output + '- ' + ' '.join(line for line in line.get_text().replace('\n', ' ').split(' ') if line.strip() != "").strip() + '\n'
        except AttributeError:
            pass
        except Exception as e:
            display(f"Notes li: {type(e).__name__}", error=True)

        try:  # TABLE - TIMELINE
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
                    cleaned_html = re.sub(r'[\t]+', ' ', cleaned_html)  # Remove extra spaces (except newlines)
                    cleaned_html = re.sub(r'\n+', ' ', cleaned_html)  # Replace newlines with spaces
                    cleaned_html = re.sub(r'(<br\s*/?>)\s+', r'\1', cleaned_html)  # Remove spaces after <br>
                    cleaned_html = re.sub(r'\s+(<br\s*/?>)', r'\1', cleaned_html)  # Remove spaces before <br>
                    cleaned_html = re.sub(r'\s+([,:])', r'\1', cleaned_html)  # Remove spaces before comma or column
                    cleaned_html = re.sub(r'<br>', r'\n', cleaned_html)  # Replace <br> with new line

                    output = output + '- ' + cleaned_html + '\n'
                except AttributeError:
                    pass
                except Exception as e:
                    display(f"Notes td: {type(e).__name__}", error=True)
        except AttributeError:
            pass
        except Exception as e:
            display(f"Notes table: {type(e).__name__}", error=True)

        if len(output) > 0:
            return [output]
        else:
            return []
        return []

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
        #         print(image)
        #         print('click')
        #         image.click()
        #         print('clicked')
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
        #         print('failed action')

        # process the regular medias
        # image = browser.find_elements(By.CSS_SELECTOR, "img[ng-src]")
        # image = browser.find_elements(By.XPATH, "//img[@ng-src and not(@ng-click)]")
        pass

    # -------------------------------------------------------------------------
    # _scrap_family
    # -------------------------------------------------------------------------

    def _scrap_family(self, personref, soup):

        family = Family()

        # spouses ref
        try:
            # first <a> can be a ref to sosa
            family.spousesref = [clean_query(personref), clean_query([a for a in soup.find_all('a') if a.get_text(strip=True)][0]['href'])]

        except IndexError:
            pass
        except Exception as e:
            display(f"Family spouses: {type(e).__name__}", error=True)
            family.spousesref = [clean_query(personref), None]

        # Childs
        childsref = []
        try:
            for item in soup.find("ul").find_all("li", recursive=False):
                # first <a> can be a ref to sosa
                childsref = childsref + [clean_query([a for a in item.find_all('a') if a.get_text(strip=True)][0]['href'])]
            family.childsref = childsref

        except AttributeError:
            pass
        except Exception as e:
            display(f"Childs: {type(e).__name__}", error=True)

        # Marriage
        try:
            event = ' '.join(soup.find("em").get_text().split()).rstrip(",")
            pattern = r"(?:^Mariée?)?(?P<date>[^,]*)\s*(?:\((?P<alt>.*)\))?\s*(?:,\s*(?P<place>.*?))?(?=, à|$)"
            family.data['marriage'], family.data['marriagedate'], family.data['marriageplace'] = self._extract_date_place(event, "Marié", pattern)
        except AttributeError:
            if 'event' in locals() and event.find("Marié") >= 0:
                display(f"!! Marriage: [{event}]", error=True)
        except Exception as e:
            display(f"Marriage: {type(e).__name__}", error=True)

        # Divorce
        try:
            event = soup.get_text().lower()
            pattern = r"(?:.*)divorcée?\s*(?P<date>[^-(à]*)\s*(?:\((?P<alt>.*)\))?\s*(?:-\s*(?P<place>.*?))?(?=, à|$)"
            family.data['divorce'], family.data['divorcedate'], noplace = self._extract_date_place(event, "Divorcé", pattern)
        except AttributeError:
            if 'event' in locals() and event.find("ivorcé") >= 0:
                display(f"!! Divorce: [{event}]", error=True)
        except Exception as e:
            display(f"Divorce: {type(e).__name__}", error=True)

        # annulation date
        if 'annulé' in soup.get_text().lower():
            display("Add annulation processing")
            family.data['annulationdate'] = None

        # engagement date
        if 'annulé' in soup.get_text().lower():
            display("Add engagement processing")
            family.data['engagementdate'] = None

        # publish date
        if 'bans' in soup.get_text().lower():
            display("Add publish processing")
            family.data['publishdate'] = None

        # license date
        if 'license' in soup.get_text().lower():
            display("Add license processing")
            family.data['licensedate'] = None

        # separation date
        if 'séparé' in soup.get_text().lower():
            display("Add separation processing")
            family.data['separationdate'] = None

        return family

    # -------------------------------------------------------------------------
    # scrap
    # -------------------------------------------------------------------------

    def scrap(self, url, force=False):
        """
        Function to scrap a geneanet page
        """

        person = Individual()

        try:
            # Reference
            person.data.url = url
            person.ref = clean_query(url)

            # read web page

            sections = self._read(url, force)

            for section in sections:

                # -------------------------------------------------------------
                # Portrait section
                # -------------------------------------------------------------
                if 'portrait' in section.name.lower():

                    # first and last names
                    try:
                        names = section.content.find("div", {"id": "person-title"}).find_all_next("a")

                        person.data.firstname = names[0].get_text().replace('\n', '').strip().title()
                        person.data.lastname = names[1].get_text().replace('\n', '').strip().title()
                    except AttributeError:
                        pass
                    except Exception as e:
                        display(f"Name: {type(e).__name__}", error=True)

                    # sex: should return M or F
                    try:
                        sex = section.content.find("div", {"id": "person-title"}).find_all_next("img", alt=True)

                        person.data.sex = sex[0]['alt']
                        if person.data.sex == 'H':
                            person.data.sex = 'M'
                        if person.data.sex != 'M' and person.data.sex != 'F':
                            person.data.sex = 'U'
                    except AttributeError:
                        pass
                    except Exception as e:
                        display(f"Sex: {type(e).__name__}", error=True)

                    # birth
                    try:
                        pattern = r"^Née?\s*(?P<date>[^-(à]*)\s*(?:\((?P<alt>.*)\))?\s*(?:-\s*(?P<place>.*?))?(?=, à|$)"
                        event = ' '.join(section.content.find('li', string=lambda text: "Né" in text if text else False).get_text().split())
                        person.data.birth, person.data.birthdate, person.data.birthplace = self._extract_date_place(event, "Né", pattern)
                    except AttributeError:
                        if 'event' in locals() and event.find("Né") >= 0:
                            display(f"Birth: [{event}]", error=True)
                    except Exception as e:
                        display(f"!! Birth: {type(e).__name__}", error=True)

                    # death
                    try:
                        pattern = r"^Décédée?\s*(?P<date>[^-(à]*)\s*(?:\((?P<alt>.*)\))?\s*(?:-\s*(?P<place>.*?))?(?=, à|$)"
                        event = ' '.join(section.content.find('li', string=lambda text: "Décédé" in text if text else False).get_text().split())
                        person.data.death, person.data.deathdate, person.data.deathplace = self._extract_date_place(event, "Décédé", pattern)
                    except AttributeError:
                        if 'event' in locals() and event.find("Décédé") >= 0:
                            display(f"!! Death: [{event}]", error=True)
                    except Exception as e:
                        display(f"Death: {type(e).__name__}", error=True)

                    # baptem
                    try:
                        pattern = r"(?:.*)Baptisée?\s*(?P<date>[^-(à,]*)\s*(?:\((?P<alt>.*)\))?\s*(?:-\s*(?P<place>.*?))?"
                        event = ' '.join(section.content.find('li', string=lambda text: "baptisé" in text.lower() if text else False).get_text().split())
                        person.data.baptem, person.data.baptemdate, person.data.baptemplace = self._extract_date_place(event, "Baptisé", pattern)
                    except (AttributeError, IndexError):
                        if 'event' in locals() and event and event.find("aptisé") >= 0:
                            display(f"!! Baptem: [{event}]", error=True)
                    except Exception as e:
                        display(f"Baptem: {type(e).__name__}", error=True)

                    # Burial
                    try:
                        pattern = r"(?:.*)Inhumée?\s*(?P<date>[^-(à,]*)\s*(?:\((?P<alt>.*)\))?\s*(?:-\s*(?P<place>.*?))?(?=, à|$)"
                        event = ' '.join(section.content.find('li', string=lambda text: "inhumé" in text.lower() if text else False).get_text().split())
                        person.data.burial, person.data.burialdate, person.data.burialplace = self._extract_date_place(event, "Inhumé", pattern)
                    except (AttributeError, IndexError):
                        if 'event' in locals() and event and event.find("nhumé") >= 0:
                            display(f"!! Burial: [{event}]", error=True)
                    except Exception as e:
                        display(f"Burial: {type(e).__name__}", error=True)

                    # occupation
                    try:
                        lines = section.content.find_all('li')
                        words = ['né', 'décédé', 'baptisé', 'inhumé']
                        for line in lines:
                            if all(word not in line.get_text().lower() for word in words):
                                person.data.occupation = ' '.join(line.get_text().split())
                                display(f"OCCUPATION: {person.data.occupation}")
                                break

                    except Exception as e:
                        display(f"Occupation: {type(e).__name__}", error=True)

                    # adoption
                    try:
                        adoption = section.content.find_all('li', string=lambda text: "adopté" in text.lower() if text else False)[0].get_text()
                        display("Add adoption processing")
                        person.data.adoption = adoption

                    except IndexError:
                        pass
                    except Exception as e:
                        display(f"Adoption: {type(e).__name__}", error=True)

                # -------------------------------------------------------------
                # Parents section
                # -------------------------------------------------------------
                elif 'parents' in section.name.lower():
                    try:
                        person.parentsref = [clean_query(item['href']) for item in section.content.find_all("a") if len(item.find_all("img", {"alt": "sosa"})) == 0]
                    except Exception as e:
                        display(f"Parents: {type(e).__name__}", error=True)

                # -------------------------------------------------------------
                # Families section
                # -------------------------------------------------------------
                elif 'union' in section.name.lower():
                    try:
                        person.familiesref = []
                        unions = section.content.find('ul', class_=re.compile('.*fiche_union.*')).find_all("li", recursive=False)

                        for union in unions:
                            try:
                                person.familiesref = person.familiesref + [self._scrap_family(person.ref, union)]
                            except Exception as e:
                                display(f"Family scrap: {type(e).__name__}", error=True)

                    except AttributeError:
                        pass
                    except Exception as e:
                        display(f"Union: {type(e).__name__}", error=True)

                # -------------------------------------------------------------
                # Freres et Soeurs section
                # -------------------------------------------------------------
                elif 'freres et soeurs' in section.name.lower():
                    try:
                        person.siblingsref = []

                        for item in section.content.find("ul").find_all("li", recursive=False):
                            tag_a = item.find('a')
                            if tag_a.get_text(strip=True):
                                # first <a> can be a ref to sosa
                                person.siblingsref = person.siblingsref + [clean_query(tag_a['href'])]

                    except AttributeError:
                        pass
                    except Exception as e:
                        display(f"Siblings: {type(e).__name__}", error=True)

                # -------------------------------------------------------------
                # Famille section
                # -------------------------------------------------------------
                elif 'famille' in section.name.lower():
                    if len(section.content) > 0:
                        display(f"Add processing for section: {section.name}")

                # -------------------------------------------------------------
                # Relation, related or notes sections
                # -------------------------------------------------------------
                elif 'relation' in section.name.lower() or 'related' in section.name.lower() or 'notes' in section.name.lower():
                    if len(section.content) > 0:
                        person.data.notes = person.data.notes + self._scrap_notes(str(section.content))

                # -------------------------------------------------------------
                # Sources section
                # -------------------------------------------------------------
                elif 'sources' in section.name.lower():
                    if len(section.content) > 0:
                        try:
                            # Remove all elements before the <h2> tag
                            h2_element = section.content.find('h2')
                            if h2_element:
                                for element in h2_element.find_all_previous():
                                    element.decompose()
                            if len(section.content) > 0:
                                person.data.notes = person.data.notes + self._scrap_notes(str(section.content))
                        except Exception as e:
                            display(f"Sources: {type(e).__name__}", error=True)

                # -------------------------------------------------------------
                # Unprocess section
                # -------------------------------------------------------------
                else:
                    if len(section.content) > 0:
                        display(f"Add processing for section: {section.name}")

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            message = f'Exception {e} [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
            display(message, error=True)

        return person

    # -------------------------------------------------------------------------
    # informations
    # -------------------------------------------------------------------------

    def informations(self, url, force=True):
        """
        Function to get informations about the Geneanet owner
        """

        infos = Informations()

        try:
            parsed_url = urllib.parse.urlparse(url)

            if parsed_url.scheme != "":

                infos.url = urllib.parse.urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))

                perso = self._load(infos.url, force)

                infos.author = perso.select("div[class*='info-auteur']")[0].find("strong").get_text().strip()
                infos.nbindividuals = int(re.sub(r'\D', '', perso.select("span[class*='stats-number']")[0].get_text()))
                infos.lastchange = [p for p in perso.select("p[class*='text-light']") if 'Dernière' in p.get_text()][0]
                infos.lastchange = self._convert_date(infos.lastchange.find("span").get_text().split('/'))
                infos.source = "Geneanet"

                display(infos, title="Informations")

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            message = f'{e} within scrapping [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
            display(message, error=True)

        return infos

    # -------------------------------------------------------------------------
    # html
    # -------------------------------------------------------------------------

    @property
    def html(self):
        """
        Function to return the perso bloc
        """
        return self._html.prettify()
