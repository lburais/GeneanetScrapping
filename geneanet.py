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
import urllib

# https://pypi.org/project/beautifulsoup4/
# pip3 install bs4

from bs4 import BeautifulSoup, Comment

# -------------------------------------------------------------------------
#
# Internal Python Modules
#
# -------------------------------------------------------------------------

from common import display, get_folder, load_chrome
from objects import Informations, Individual, Family, Place, Date

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
        self._places = {}
        self._images = []
        self._documents = {}

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
                output_file = self.clean_query(url).replace('=', "_").replace('+', " ").replace('&', ".")

            output_file = output_folder / (output_file + ".txt")

            # force fr language

            queries = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
            if 'lang' in queries:
                if queries['lang'] != 'fr':
                    url = url.replace("lang=" + queries['lang'], "lang=fr")
            elif '?' in url:
                url = url.replace("?", "?lang=fr&")
            else:
                url = url + "?lang=fr"

            html = load_chrome(url, output_file, force)

            # Get content in perso bloc

            soup = BeautifulSoup(html, 'html.parser')
            html = soup.find("div", {"id": "perso"})

            if not html:
                html = soup.find("div", {"id": "content"})

        except Exception as e:
            display(f"_load: {type(e).__name__}", exception=True)
            html = None

        self._html = html

        return html

    # -------------------------------------------------------------------------
    # _read
    # -------------------------------------------------------------------------

    def _read(self, url, force=False):

        perso = self._load(url, force)

        contents = []
        images = []
        documents = {}

        Section = namedtuple("Section", "name content")

        try:
            # extract the images

            for img in perso.find_all('img', attrs={'ng-src': True}):
                src = img['src']  # Access the ng-src attribute
                if src not in images:
                    display(f"--> {src}")
                    images += [src]

            # extract the photos and documents

            for media in perso.find_all('div', class_=re.compile('.*block-media.*')):
                src = media.find('img').get('src')
                txt = media.find('p').get_text().strip()
                if src not in documents:
                    display(f"--> {src}: {txt}")
                    documents[src] = txt

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
            display(f"_read: {type(e).__name__}", exception=True)

        return contents, images

    # -------------------------------------------------------------------------
    # _scrap_date_place
    # -------------------------------------------------------------------------

    def _scrap_date_place(self, content, key, pattern):

        try:
            date = place = None
            exist = True

            event = re.search(pattern, content)

            display(f"{key.upper()} {content} [{event.group('date')}] [{event.group('alt')}] [{event.group('place')}]")

            try:  # first date

                date = Date(event.group('date').strip().split())

            except (IndexError, ValueError):
                try:  # second date

                    date = Date(event.group('alt').strip().split())

                except (IndexError, ValueError, AttributeError):
                    pass
                except Exception as e:
                    display(f"{key.upper()} - date 2: {type(e).__name__}", error=True)
            except Exception as e:
                display(f"{key.upper()} - date 1: {type(e).__name__}", error=True)

            try:  # place

                where = event.group('place').strip()

                if where not in self._places:
                    self._places[where] = Place(where)

                place = self._places[where]

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

        if date == '':
            date = None

        return exist, date, place

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

        # process portrait images


        # process photos and documents

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
            family.spousesref = [self.clean_query(personref), self.clean_query([a for a in soup.find_all('a') if a.get_text(strip=True)][0]['href'])]

        except IndexError:
            pass
        except Exception as e:
            display(f"Family spouses: {type(e).__name__}", error=True)
            family.spousesref = [self.clean_query(personref), None]

        # Childs
        childsref = []
        try:
            for item in soup.find("ul").find_all("li", recursive=False):
                # first <a> can be a ref to sosa
                childsref = childsref + [self.clean_query([a for a in item.find_all('a') if a.get_text(strip=True)][0]['href'])]
            family.childsref = childsref

        except AttributeError:
            pass
        except Exception as e:
            display(f"Childs: {type(e).__name__}", error=True)

        # Marriage
        try:
            event = ' '.join(soup.find("em").get_text().split()).rstrip(",")
            pattern = r"(?:^Mariée?)?(?P<date>[^,]*)\s*(?:\((?P<alt>.*)\))?\s*(?:,\s*(?P<place>.*?))?(?=, à|$)"
            family.data['marriage'], family.data['marriagedate'], family.data['marriageplace'] = self._scrap_date_place(event, "Marié", pattern)
        except AttributeError:
            if 'event' in locals() and event.find("Marié") >= 0:
                display(f"!! Marriage: [{event}]", error=True)
        except Exception as e:
            display(f"Marriage: {type(e).__name__}", error=True)

        # Divorce
        try:
            event = soup.get_text().lower()
            pattern = r"(?:.*)divorcée?\s*(?P<date>[^-(à]*)\s*(?:\((?P<alt>.*)\))?\s*(?:-\s*(?P<place>.*?))?(?=, à|$)"
            family.data['divorce'], family.data['divorcedate'], noplace = self._scrap_date_place(event, "Divorcé", pattern)
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
            person.ref = self.clean_query(url)

            # read web page

            sections, images = self._read(url, force)

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
                        person.data.birth, person.data.birthdate, person.data.birthplace = self._scrap_date_place(event, "Né", pattern)
                    except AttributeError:
                        if 'event' in locals() and event.find("Né") >= 0:
                            display(f"Birth: [{event}]", error=True)
                    except Exception as e:
                        display(f"!! Birth: {type(e).__name__}", error=True)

                    # death
                    try:
                        pattern = r"^Décédée?\s*(?P<date>[^-(à]*)\s*(?:\((?P<alt>.*)\))?\s*(?:-\s*(?P<place>.*?))?(?=, à|$)"
                        event = ' '.join(section.content.find('li', string=lambda text: "Décédé" in text if text else False).get_text().split())
                        person.data.death, person.data.deathdate, person.data.deathplace = self._scrap_date_place(event, "Décédé", pattern)
                    except AttributeError:
                        if 'event' in locals() and event.find("Décédé") >= 0:
                            display(f"!! Death: [{event}]", error=True)
                    except Exception as e:
                        display(f"Death: {type(e).__name__}", error=True)

                    # baptem
                    try:
                        pattern = r"(?:.*)Baptisée?\s*(?P<date>[^-(à,]*)\s*(?:\((?P<alt>.*)\))?\s*(?:-\s*(?P<place>.*?))?(?=, à|$)"
                        event = ' '.join(section.content.find('li', string=lambda text: "baptisé" in text.lower() if text else False).get_text().split())
                        person.data.baptem, person.data.baptemdate, person.data.baptemplace = self._scrap_date_place(event, "Baptisé", pattern)
                    except (AttributeError, IndexError):
                        if 'event' in locals() and event and event.find("aptisé") >= 0:
                            display(f"!! Baptem: [{event}]", error=True)
                    except Exception as e:
                        display(f"Baptem: {type(e).__name__}", error=True)

                    # Burial
                    try:
                        pattern = r"(?:.*)Inhumée?\s*(?P<date>[^-(à,]*)\s*(?:\((?P<alt>.*)\))?\s*(?:-\s*(?P<place>.*?))?(?=, à|$)"
                        event = ' '.join(section.content.find('li', string=lambda text: "inhumé" in text.lower() if text else False).get_text().split())
                        person.data.burial, person.data.burialdate, person.data.burialplace = self._scrap_date_place(event, "Inhumé", pattern)
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
                                display(f"** OCCUPATION: {person.data.occupation}")
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
                        person.parentsref = [self.clean_query(item['href']) for item in section.content.find_all("a") if len(item.find_all("img", {"alt": "sosa"})) == 0]
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
                                person.siblingsref = person.siblingsref + [self.clean_query(tag_a['href'])]

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
            display(f"Failed to scrap [{url}]: {type(e).__name__}", exception=True)

        return person

    # -------------------------------------------------------------------------
    # informations
    # -------------------------------------------------------------------------

    def informations(self, url, force=False):
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
                infos.lastchange = Date(infos.lastchange.find("span").get_text().split('/'))
                infos.source = "Geneanet"

                display(infos, title="Informations")

        except Exception as e:
            display(f"Failed to info [{url}]: {type(e).__name__}", exception=True)

        return infos

    # -------------------------------------------------------------------------
    # clean_query
    # -------------------------------------------------------------------------


    def clean_query(self, url):
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
    # html
    # -------------------------------------------------------------------------

    @property
    def html(self):
        """
        Function to return the perso bloc
        """
        return self._html.prettify()
