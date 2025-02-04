import selenium
from selenium import webdriver

from bs4 import BeautifulSoup
from bs4 import Comment, NavigableString

import sys
import os
import re

pages = [
  'https://gw.geneanet.org/lipari?lang=fr&n=bessey&p=gabrielle+denise+josephine',
  'https://gw.geneanet.org/asempey?lang=fr&n=jantieu&p=margueritte&oc=0'
]

def read_geneanet( page ):

    content = []

    browser = webdriver.Safari()
    browser.get(page)

    try:
        soup = BeautifulSoup(browser.page_source, 'html.parser')
        perso = soup.find("div", {"id": "perso"})

        medias = perso.find_all("img", attrs={"ng-src": re.compile(r".*")} )

        if len(medias) > 0:
            content = content + [( 'Medias', medias)]

        comments = perso.find_all(string=lambda text: isinstance(text, Comment))

        for comment in comments:
            if ' ng' in comment or 'Arbre' in comment or 'Frere' in comment:
                continue

            extracted_content = []
            for sibling in comment.next_siblings:
                if isinstance( sibling, Comment ):
                    break
                extracted_content.append(str(sibling))

            content = content + [( comment.strip(), BeautifulSoup( ''.join([i for i in extracted_content if i != '\n']), 'html.parser' ) )]

            comment.extract()

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        message = f'Exception [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
        print( message )
        pass

    browser.quit()

    return content


for page in pages:
    print("#"*80)
    print(page)

    ret = read_geneanet( page )

    ret2 = []
    for block in ret:
        if isinstance( block[1], BeautifulSoup ):
            ret2.append( "%s : %d"%(block[0], len(block[1].prettify())) )
        else:
            ret2.append( "%s : %d"%(block[0], len(block[1])) )

    print( ', '.join(ret2))

    print("#"*80)

