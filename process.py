import os
import csv
import collections
import re
from bs4 import BeautifulSoup
from itertools import groupby

def convert(data):
    if isinstance(data, basestring):
        return str(data)
    elif isinstance(data, collections.Mapping):
        return dict(map(convert, data.iteritems()))
    elif isinstance(data, collections.Iterable):
        return type(data)(map(convert, data))
    else:
        return data

headers = ['provider', 'filename', 'title', 'artist', 'contributor', 'type', 'key',
           'rating', 'difficulty', 'url', 'chords_only',
           'chords_newlines', 'chords_newlines_structure', 'tab']

with open('output.tsv', 'w') as fp:
    output = csv.writer(fp, delimiter='\t')
    output.writerow(headers)

    sites = [{'chord_tag': 'u', 'folder': 'music/echords', 'structure_tag': 'i'},
             {'chord_tag': 'span', 'folder': 'music/ultimate-guitar', 'structure_tag': 'unknown'}]

    for site in sites:
        for filename in os.listdir(site['folder']):
            with open(site['folder'] + '/' + filename) as f:

                try:
                    content = convert(f.read()[4:])

                    array = content.split(" %%%%\n%%%% ")
                    data = collections.defaultdict(lambda: '')

                    data['filename'] = filename

                    for field in array:
                        if field != '\n' and field != '':
                            field = field.split(':', 1)
                            data[field[0].strip().lower()] = re.sub(r'\r?\n', '<br \>', field[1].strip())
                            data[field[0].strip().lower()] = re.sub(r'\t', '<tab \>', data[field[0].strip().lower()])

                    soup = BeautifulSoup(data['tab'], 'html.parser')

                    data['chords_newlines'] = [g[0]
                                       for g in
                                       groupby(['BR' if tag.name == 'br' else (tag.contents[0] if len(tag.contents) > 0 else '')
                                                for tag in soup.find_all([site['chord_tag'], 'br'])])]
                    data['chords_only'] = [tag.contents[0] for tag in soup.find_all([site['chord_tag']])]
                    data['chords_newlines_structure'] = [g[0]
                                       for g in
                                       groupby(['BR' if tag.name == 'br' else (tag.contents[0] if len(tag.contents) > 0 else '')
                                                for tag in soup.find_all([site['chord_tag'], 'br', site['structure_tag']])])]

                    output.writerow([data[header] for header in headers])

                except:
                    print('Error parsing file:', filename)
                    continue