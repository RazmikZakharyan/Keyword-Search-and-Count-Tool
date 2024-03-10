import argparse
from os import path
from tld import get_tld

import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from bs4 import BeautifulSoup
from bs4.element import Comment

from tqdm import tqdm
import validators

import contextlib
import sys

api_key = ""
cse_id = ""
symbols = ['|', '+', '-']

if (args_count := len(sys.argv)) != 3:
    print(f"Two argument expected, got {args_count - 1}")
    raise SystemExit(2)

search_text = sys.argv[1]
word = sys.argv[2]


class DummyFile(object):
    file = None

    def __init__(self, file):
        self.file = file

    def write(self, x):
        # Avoid print() second call (useless \n)
        if len(x.rstrip()) > 0:
            tqdm.write(x, file=self.file)


@contextlib.contextmanager
def nostdout():
    save_stdout = sys.stdout
    sys.stdout = DummyFile(sys.stdout)
    yield
    sys.stdout = save_stdout


def google_search(search_term, api_key, cse_id, **kwargs) -> dict:
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=search_term, cx=cse_id, **kwargs).execute()
    return res


def tag_visible(element):
    if element.parent.name in ['style', 'script', 'head', 'title', 'meta',
                               '[document]']:
        return False
    if isinstance(element, Comment):
        return False
    return True


def count_word_in_text_from_html(body, word):
    soup = BeautifulSoup(body, 'html.parser')
    texts = soup.findAll(text=True)
    visible_texts = filter(tag_visible, texts)
    qty = 0
    for t in visible_texts:
        qty += t.strip().lower().count(word)
    return qty


def get_urls_list(urls):
    i = 0
    while True:
        if not urls[i:i + 5]:
            break
        yield urls[i:i + 5]
        i += 5


if __name__ == '__main__':
    print('Start script:')

    if not path.exists('websites.txt'):
        print(
            "websites.txt file doesn't exist in this directory,"
            " please create one and fill it with urls."
        )
        exit()

    with open('websites.txt', 'r') as file:
        urls = [url.strip() for url in file.readlines() if url]

        urls_list = list(
            get_urls_list(
                list(filter(lambda x: validators.url(x), urls[2:]))
            )
        )

    print('Searching text:', search_text)
    print('Keyword:', word)

    i = 1
    name = f'answers.txt'
    while True:
        if not path.exists(name):
            break
        name = f'answers{i}.txt'
        i += 1

    answer_file = open(name, 'w')
    answer_file.write(f'keyword: {word}\n')

    response = None
    count = 0

    for urls in tqdm(urls_list, file=sys.stdout):
        try:
            response = google_search(
                f'intext:{word} ' + ' | '.join(
                    map(lambda x: f"inurl:{x}", urls)),
                api_key, cse_id,
                fields='items(link)'
            )
        except (requests.exceptions.HTTPError, HttpError) as e:
            print(e)
            exit()

        data = {}
        try:
            if response and response.get('items'):
                for item in response['items']:
                    if 'pdf' not in item['link'].lower():
                        res = requests.get(item['link'])
                        qty = count_word_in_text_from_html(
                            res.text, word.lower()
                        )
                        domain = get_tld(item['link'], as_object=True).fld
                        if data.get(domain):
                            data[domain] += qty
                        else:
                            data[domain] = qty

        except requests.exceptions.SSLError:
            pass

        with nostdout():
            for key, value in data.items():
                print(f"url : {key}")
                answer_file.write(f"url : {key}\n")
                message = f"number of occurrences: {value}"
                if not value:
                    message = 'blocked by firewall \n'

                print(message)
                answer_file.write(message + '\n')

    print("Finished executing. ")
