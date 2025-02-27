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

#-------------------------------------------------------------------------
#
# Standard Python Modules
#
#-------------------------------------------------------------------------

import re
from collections import namedtuple
import sys
import os
import urllib

# https://pypi.org/project/beautifulsoup4/
# pip3 install bs4

from bs4 import BeautifulSoup, Comment

#-------------------------------------------------------------------------
#
# Internal Python Modules
#
#-------------------------------------------------------------------------

from common import display, get_folder, convert_date, clean_query, load_chrome

#-------------------------------------------------------------------------
#
# Geneanet class
#
#-------------------------------------------------------------------------

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
    # _extract_date_place
    # -------------------------------------------------------------------------

    def _extract_date_place( self, content, key, pattern ):

        try:
            date = place = None
            exist = True

            event = re.search( pattern, content )

            display( f"{key.upper()} {content} [{event.group('date')}] [{event.group('alt')}] [{event.group('place')}]" )

            try: # first date

                date = convert_date(event.group('date').strip().split())

            except (IndexError, ValueError):
                try: # second date

                    date = convert_date(event.group('alt').strip().split())

                except (IndexError, ValueError, AttributeError):
                    pass
                except Exception as e:
                    display( f"{key.upper()} - date 2: {type(e).__name__}", error=True )
            except Exception as e:
                display( f"{key.upper()} - date 1: {type(e).__name__}", error=True )

            try: # place

                if date:
                    place = event.group('place').strip()

            except AttributeError:
                pass
            except Exception as e:
                display( f"{key.upper()} - place: {type(e).__name__}", error=True )


            if event and not date and not place:
                display( f"{key.upper()}: [{content}]", error=True )

        except (AttributeError, NameError):
            exist = False
        except Exception as e:
            display( f"{key.upper()}: {type(e).__name__}", error=True )

        return exist, date, place

    # -------------------------------------------------------------------------
    # _load
    # -------------------------------------------------------------------------
    def _load( self, url, force = False ):

        try:
            output_folder = self._folder / re.sub( r'^/', '', urllib.parse.urlparse(url).path )
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

            if force is True or not output_txt.exists():

                display( f'Load from {url}' )

                self._html = load_chrome( url, output_folder / (output_file + ".pdf") )

                # Get content in perso bloc

                soup = BeautifulSoup(self._html, 'html.parser')
                self._html = soup.find("div", {"id": "perso"})

                if not self._html:
                    self._html = soup.find("div", {"id": "content"})

                # process perso

                try:
                    output_txt.unlink(missing_ok=True)
                    output_txt.write_text( self._html.prettify() )
                except Exception as e:
                    display( f"Save HTML: {type(e).__name__}", error=True )
                    display( f'Failed to save HTML: {output_txt}', error=True )

            else:
                display( f'Read from {output_txt}' )
                self._html = BeautifulSoup( output_txt.read_text(), 'html.parser' )

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            message = f'Exception {e} [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
            display( message, error=True )
            display( message, exception=True )
            self._html = None

        return self._html

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

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            message = f'Exception {e} [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
            display( message, error=True )

        return contents

    # -------------------------------------------------------------------------
    # _scrap_notes
    # -------------------------------------------------------------------------
    def _scrap_notes( self, html ):

        output = ''
        soup = BeautifulSoup(html, 'html.parser')

        try: # H2
            tag = '\n'.join(line for line in soup.find('h2').get_text().split('\n') if line.strip() != "").strip()
            line = tag + '\n' + "="*len(tag) + '\n'*2
            try: # H3
                tag = '\n'.join(line for line in soup.find('h3').get_text().split('\n') if line.strip() != "").strip()
                line = line + tag + '\n' + "-"*len(tag) + '\n'*2
            except AttributeError:
                pass
            except Exception as e:
                display( f"Notes h3: {type(e).__name__}", error=True )
            # DIV
            tag = '\n'.join(line for line in soup.find('div').get_text().split('\n') if line.strip() != "").strip()
            if len(tag) > 0:
                output = output + line + tag + '\n'*2
        except AttributeError:
            pass
        except Exception as e:
            display( f"Notes h2: {type(e).__name__}", error=True )

        try: # LI - RELATED
            lines = soup.find_all('li')
            for line in lines:
                output = output + '- ' + ' '.join(line for line in line.get_text().replace('\n',' ').split(' ') if line.strip() != "").strip() + '\n'
        except AttributeError:
            pass
        except Exception as e:
            display( f"Notes li: {type(e).__name__}", error=True )

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
                except AttributeError:
                    pass
                except Exception as e:
                    display( f"Notes td: {type(e).__name__}", error=True )
        except AttributeError:
            pass
        except Exception as e:
            display( f"Notes table: {type(e).__name__}", error=True )

        if len(output) > 0:
            return [ output ]
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

        family = {}

        # Marriage
        try:
            marriage = ' '.join( soup.find("em").get_text().split() ).rstrip(",")
            pattern = r"(?:Mariée?)?(?P<date>[^,]*)\s*(?:\((?P<alt>.*)\))?\s*(?:,\s*(?P<place>.*?))?(?=, à|$)"
            family['marriage'], family['marriagedate'], family['marriageplace'] = self._extract_date_place( marriage, "Marié", pattern)
        except AttributeError:
            pass
        except Exception as e:
            display( f"Marriage: {type(e).__name__}", error=True )

        # spouses ref
        try:
            # first <a> can be a ref to sosa
            family['spousesref'] = [ clean_query( personref ), clean_query( [a for a in soup.find_all('a') if a.get_text(strip=True)][0]['href'] ) ]

        except IndexError:
            pass
        except Exception as e:
            display( f"Family spouses: {type(e).__name__}", error=True )
            family['spousesref'] = [ clean_query( personref ), None ]

        # Divorce
        try:
            divorce = soup.get_text().lower()
            pattern = r"(?:.*)divorcéée?\s*(?P<date>[^-(à]*)\s*(?:\((?P<alt>.*)\))?\s*(?:-\s*(?P<place>.*?))?(?=, à|$)"
            family['divorce'], family['divorcedate'], noplace = self._extract_date_place( divorce, "Divorcé", pattern)
        except AttributeError:
            pass
        except Exception as e:
            display( f"Divorce: {type(e).__name__}", error=True )

        # annulation date
        if 'annulé' in soup.get_text().lower():
            display("Add annulation processing")
            family['annulationdate'] = None

        # engagement date
        if 'annulé' in soup.get_text().lower():
            display("Add engagement processing")
            family['engagementdate'] = None

        # publish date
        if 'bans' in soup.get_text().lower():
            display("Add publish processing")
            family['publishdate'] = None

        # license date
        if 'license' in soup.get_text().lower():
            display("Add license processing")
            family['licensedate'] = None

        # separation date
        if 'séparé' in soup.get_text().lower():
            display("Add separation processing")
            family['separationdate'] = None

        # Childs
        childsref = []
        try:
            for item in soup.find("ul").find_all( "li", recursive=False ):
                # first <a> can be a ref to sosa
                childsref = childsref + [ clean_query( [a for a in item.find_all('a') if a.get_text(strip=True)][0]['href'] ) ]
            family['childsref'] = childsref

        except AttributeError:
            pass
        except Exception as e:
            display( f"Childs: {type(e).__name__}", error=True )

        # clean
        family = {k: v for k, v in family.items() if v is not None}

        return family

    # -------------------------------------------------------------------------
    # scrap
    # -------------------------------------------------------------------------

    def scrap( self, url, force = False ):
        """
        Function to scrap a geneanet page
        """

        person = {}

        try:
            # Reference
            person['ref'] = clean_query( url )

            # read web page

            sections = self._read( url, force )

            for section in sections:

                # -------------------------------------------------------------
                # Portrait section
                # -------------------------------------------------------------
                if 'portrait' in section.name.lower():

                    person['portrait'] = {}

                    # first and last names
                    try:
                        names = section.content.find("div", {"id" : "person-title"}).find_all_next("a")

                        person['portrait']['firstname'] = names[0].get_text().replace('\n', '').strip().title()
                        person['portrait']['lastname'] = names[1].get_text().replace('\n', '').strip().title()
                    except AttributeError:
                        pass
                    except Exception as e:
                        display( f"Name: {type(e).__name__}", error=True )

                    # sex: should return M or F
                    try:
                        sex = section.content.find("div", {"id" : "person-title"}).find_all_next("img", alt=True)

                        person['portrait']['sex'] = sex[0]['alt']
                        if person['portrait']['sex'] == 'H':
                            person['portrait']['sex'] = 'M'
                    except AttributeError:
                        pass
                    except Exception as e:
                        display( f"Sex: {type(e).__name__}", error=True )
                        person['portrait']['sex'] = 'U'

                    # birth
                    try:
                        pattern = r"(?:.*)Née?\s*(?P<date>[^-(à]*)\s*(?:\((?P<alt>.*)\))?\s*(?:-\s*(?P<place>.*?))?(?=, à|$)"
                        event = ' '.join( section.content.find('li', string=lambda text: "Né" in text if text else False).get_text().split() )
                        person['portrait']['birth'], person['portrait']['birthdate'], person['portrait']['birthplace'] = self._extract_date_place( event, "Né", pattern)
                    except AttributeError:
                        pass
                    except Exception as e:
                        display( f"Birth: {type(e).__name__}", error=True )

                    # death
                    try:
                        pattern = r"(?:.*)Décédée?\s*(?P<date>[^-(à]*)\s*(?:\((?P<alt>.*)\))?\s*(?:-\s*(?P<place>.*?))?(?=, à|$)"
                        event = ' '.join( section.content.find('li', string=lambda text: "Décédé" in text if text else False).get_text().split() )
                        person['portrait']['death'], person['portrait']['deathdate'], person['portrait']['deathplace'] = self._extract_date_place( event, "Décédé", pattern)
                    except AttributeError:
                        pass
                    except Exception as e:
                        display( f"Death: {type(e).__name__}", error=True )

                    # baptem
                    try:
                        baptem = section.content.find_all('li', string=lambda text: "baptisé" in text.lower() if text else False)[0].get_text()
                        display("Processing baptem ")

                        try:
                            person['portrait']['baptemdate'] = convert_date(baptem.split('-')[0].split()[1:])

                            try:
                                person['portrait']['baptemplace'] = baptem[baptem.find('-') + 1:].strip()
                                person['portrait']['baptemplace'] = ",".join( item.strip() for item in person['portrait']['baptemplace'].split(",") )
                            except Exception as e:
                                display( f"Baptem place: {type(e).__name__}", error=True )

                        except IndexError:
                            person['portrait']['baptemtext'] = baptem
                        except Exception as e:
                            display( f"Baptem date: {type(e).__name__}", error=True )

                    except IndexError:
                        pass
                    except Exception as e:
                        display( f"Baptem: {type(e).__name__}", error=True )

                    # Burial
                    try:
                        pattern = r"(?:.*)Inhumée?\s*(?P<date>[^-(à,]*)\s*(?:\((?P<alt>.*)\))?\s*(?:-\s*(?P<place>.*?))?(?=, à|$)"
                        event = ' '.join( section.content.find('li', string=lambda text: "inhumé" in text.lower() if text else False).get_text().split() )
                        person['portrait']['burial'], person['portrait']['burialdate'], person['portrait']['burialplace'] = self._extract_date_place( event, "Inhumé", pattern)
                    except (AttributeError, IndexError):
                        pass
                    except Exception as e:
                        display( f"Burial: {type(e).__name__}", error=True )

                    # occupation
                    try:
                        lines = section.content.find_all('li')
                        words = [ 'né', 'décédé', 'baptisé', 'inhumé' ]
                        for line in lines:
                            if all(word not in line.get_text().lower() for word in words):
                                person['portrait']['occupation'] = ' '.join( line.get_text().split() )
                                display( f"OCCUPATION: {person['portrait']['occupation']}" )
                                break

                    except Exception as e:
                        display( f"Occupation: {type(e).__name__}", error = True )

                    # adoption
                    try:
                        adoption = section.content.find_all('li', string=lambda text: "adopté" in text.lower() if text else False)[0].get_text()
                        display( "Add adoption processing" )
                        person['portrait']['adoption'] = adoption

                    except IndexError:
                        pass
                    except Exception as e:
                        display( f"Adoption: {type(e).__name__}", error=True )

                    # clean
                    person['portrait'] = {k: v for k, v in person['portrait'].items() if v is not None}

                # -------------------------------------------------------------
                # Parents section
                # -------------------------------------------------------------
                elif 'parents' in section.name.lower():
                    try:
                        person['parentsref'] = [clean_query( item['href'] ) for item in section.content.find_all("a") if len( item.find_all("img", {"alt" : "sosa"}) ) == 0]
                    except Exception as e:
                        display( f"Parents: {type(e).__name__}", error=True )

                # -------------------------------------------------------------
                # Families section
                # -------------------------------------------------------------
                elif 'union' in section.name.lower():
                    try:
                        person['families'] = []
                        unions = section.content.find('ul', class_=re.compile('.*fiche_union.*') ).find_all( "li", recursive=False )

                        for union in unions:
                            try:
                                person['families'] = person['families'] + [ self._scrap_family( person['ref'], union ) ]
                            except Exception as e:
                                display( f"Family scrap: {type(e).__name__}", error=True )

                    except AttributeError:
                        pass
                    except Exception as e:
                        display( f"Union: {type(e).__name__}", error=True )

                # -------------------------------------------------------------
                # Freres et Soeurs section
                # -------------------------------------------------------------
                elif 'freres et soeurs' in section.name.lower():
                    try:
                        person['siblingsref'] = []

                        for item in section.content.find("ul").find_all( "li", recursive=False ):
                            tag_a = item.find('a')
                            if tag_a.get_text(strip=True):
                                # first <a> can be a ref to sosa
                                person['siblingsref'] = person['siblingsref'] + [ clean_query( tag_a['href'] ) ]

                    except AttributeError:
                        pass
                    except Exception as e:
                        display( f"Siblings: {type(e).__name__}", error=True )

                # -------------------------------------------------------------
                # Famille section
                # -------------------------------------------------------------
                elif 'famille' in section.name.lower():
                    if len(section.content) > 0:
                        display( f"Add processing for section: {section.name}" )

                # -------------------------------------------------------------
                # Relation, related or notes sections
                # -------------------------------------------------------------
                elif 'relation' in section.name.lower() or 'related' in section.name.lower() or 'notes' in section.name.lower():
                    if len(section.content) > 0:
                        if 'notes' in person['portrait']:
                            person['portrait']['notes'] = person['portrait']['notes'] + self._scrap_notes( str(section.content) )
                        else:
                            person['portrait']['notes'] = self._scrap_notes( str(section.content) )

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
                                if 'notes' in person['portrait']:
                                    person['portrait']['notes'] = person['portrait']['notes'] + self._scrap_notes( str(section.content) )
                                else:
                                    person['portrait']['notes'] = self._scrap_notes( str(section.content) )
                        except Exception as e:
                            display( f"Sources: {type(e).__name__}", error=True )

                # -------------------------------------------------------------
                # Unprocess section
                # -------------------------------------------------------------
                else:
                    if len(section.content) > 0:
                        display( f"Add processing for section: {section.name}" )

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            message = f'Exception {e} [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
            display( message, error=True )

        return person

    # -------------------------------------------------------------------------
    # informations
    # -------------------------------------------------------------------------

    def informations( self, url, force = False ):
        """
        Function to get informations about the Geneanet owner
        """

        informations = {}

        try:
            parsed_url = urllib.parse.urlparse(url)

            if parsed_url.scheme != "":

                informations['url'] = urllib.parse.urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))

                perso = self._load( informations['url'], force )

                informations['author'] = perso.select( "div[class*='info-auteur']" )[0].find("strong").get_text().strip()
                informations['persons'] = int(re.sub(r'\D', '', perso.select( "span[class*='stats-number']" )[0].get_text()))
                informations['lastchange'] = [ p for p in perso.select( "p[class*='text-light']" ) if 'Dernière' in p.get_text() ][0]
                informations['lastchange'] = convert_date( informations['lastchange'].find("span").get_text().split( '/' ) )

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            message = f'{e} within scrapping [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
            display( message, error=True )

        return informations

    # -------------------------------------------------------------------------
    # html
    # -------------------------------------------------------------------------

    @property
    def html( self ):
        """
        Function to return the perso bloc
        """

        if hasattr( self, '_html' ):
            return self._html.prettify()
        else:
            return ""
