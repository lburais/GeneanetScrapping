
from bs4 import BeautifulSoup
from bs4 import Comment, NavigableString

import sys
import os
import re
import urllib

pages = [
  'https://gw.geneanet.org/lipari?lang=fr&n=bessey&p=gabrielle+denise+josephine',
  'https://gw.geneanet.org/asempey?lang=fr&n=jantieu&p=margueritte&oc=0'
]

def read_geneanet( page ):

    import selenium
    from selenium import webdriver

    # clean queries: keep  lang
    queries = urllib.parse.parse_qs(urllib.parse.urlparse(page).query)
    queries_to_keep = [ 'nz', 'pz', 'm', 'v', 'p', 'n' ]
    query_string = urllib.parse.urlencode({k: v for k, v in queries.items() if k in queries_to_keep}, doseq=True)
    print( urllib.parse.urlunparse(urllib.parse.urlparse(page)._replace(query=query_string)) )

    print( "Removed queries: %s"%({k: v for k, v in queries.items() if k not in queries_to_keep}) )


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

    return perso, medias, contents


for page in pages:
    print("#"*80)
    print(page)

    perso, medias, contents = read_geneanet( page )

    ret = [ "Medias : %d"%(len(medias)) ]

    for content in contents:
        ret.append( "%s : %d"%(content[0], len(content[1].prettify())) )

    print( ', '.join(ret))

    print("#"*80)

    print( perso.prettify() )
    
    print("#"*80)

