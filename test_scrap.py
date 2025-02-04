
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

    import selenium
    from selenium import webdriver

    # contents is an array of tuples
    # each tuple is the name of the bloc and content of the bloc

    contents = []
    medias = []

    browser = webdriver.Safari()
    browser.get(page)

    try:
        # Focus on perso bloc

        soup = BeautifulSoup(browser.page_source, 'html.parser')
        perso = soup.find("div", {"id": "perso"})

        # extract the medias

        medias = perso.find_all("img", attrs={"ng-src": re.compile(r".*")} )

        # extract the geneanet blocs

        comments = perso.find_all(string=lambda text: isinstance(text, Comment))

        for comment in comments:
            if ' ng' in comment or 'Arbre' in comment or 'Frere' in comment:
                continue

            extracted_content = []
            for sibling in comment.next_siblings:
                if isinstance( sibling, Comment ):
                    break
                extracted_content.append(str(sibling))

            contents = contents + [( comment.strip(), BeautifulSoup( ''.join([i for i in extracted_content if i != '\n']), 'html.parser' ) )]

            comment.extract()

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        message = f'Exception [{exc_type} - {exc_obj}] in {exc_tb.tb_frame.f_code.co_name} at {os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}.'
        print( message )
        pass

    browser.quit()

    return medias, contents


for page in pages:
    print("#"*80)
    print(page)

    medias, contents = read_geneanet( page )

    ret = [ "Medias : %d"%(len(medias)) ]

    for content in contents:
        ret.append( "%s : %d"%(content[0], len(content[1].prettify())) )

    print( ', '.join(ret))

    print("#"*80)

