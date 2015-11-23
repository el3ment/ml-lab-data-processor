# -*- coding: utf-8 -*-

import csv
from bs4 import BeautifulSoup, Comment
import re
import sys
from mingus.core import chords as mingus_chords
import json
import music21
import pickle

csv.field_size_limit(sys.maxsize)

def find_nth(s, x, n):
    i = -1
    for _ in range(n):
        i = s.find(x, i + len(x))
        if i == -1:
            break
    return i

def Block():
    return {
        'metaData': {
            'lostCharacters': 0,
            'role': None},
        'lines': []
    }

def parseTab(tab):

    # Find newline before first chord
    beginningOfTab = max(tab[:tab[:tab.find('<u>')].rfind('<br/>')].rfind('<br/>'), 0)

    # Find second newline after last chord
    endOfTab = tab.rfind('</u>') + find_nth(tab[tab.rfind('</u>'):], '<br/>', 2) + 5

    # Grab the stuff between the first and last
    truncatedTab = tab[beginningOfTab:endOfTab]

    # Split into blocks and prepare the data structure
    blocks = re.split(r'\<br\/>\s*\<br\/>', truncatedTab.strip())
    chords = []
    lyrics = []

    embeddedLines = []

    for i, block in enumerate(blocks):

        lines = block.split('<br/>')


        chordBlock = Block()
        lyricsBlock = Block()

        for j, line in enumerate(lines):
            line = re.sub(r'[\(\[]<', '<', line)
            line = re.sub(r'>[\)\]]', '>', line)

            processed = re.findall(r'([^\<]*)?(\<u>(.*?)<\/u>)?([^\<]*)', line)
            currentChordLineIndex = 0
            lyric = ''
            chordLine = []

            for match in processed:
                currentChordLineIndex += len(match[0])
                chord = match[2]
                lyric += match[0].strip() + ' ' + match[3].strip()

                if len(chord) > 0:
                    chordLine.append((currentChordLineIndex, chord))
                    currentChordLineIndex += 1

                currentChordLineIndex += len(match[3])

            # Replace lyric lines that only describe meta-content
            roles = ['chorus', 'bridge', 'verse', 'prechorus', 'intro', 'outro', 'versei',
                     'verseii', 'verseiii', 'solo', 'final', 'refrain', 'tuning', 'interlude',
                     'introd', 'versea', 'verseb', 'verso', 'vers', 'ref', 'introx', 'refx',
                     'instl', 'riff', 'key', 'instrumental', 'ending', 'instrumentalbreak',
                     'chords', 'chorusx', 'lead', 'interlude', 'notes', 'note']

            # Replace "one" with 1, "two" with 2
            roleTest = lyric
            #[roleTest.replace(word, i) for i, word in enumerate(["zero", "one", "two", "three", "four", "five"])]

            # Strip out anything that's not an alphabetic character in preparation
            # for testing the line for roles
            roleTest = re.sub(r'([^A-Za-z])', '', roleTest.lower(), flags=re.U).strip()

            # Loop through the roles and if the entire trimmed lyric is equal to a role
            # consider it a role
            for role in roles:
                if role == roleTest:
                    # Terminate the block we've been building early
                    # If a block ends with chords but no lyrics or lyrics but no chords
                    lyricsBlock['lines'].append((None)) if len(chordBlock['lines']) > len(lyricsBlock['lines']) else None
                    chordBlock['lines'].append((None)) if len(lyricsBlock['lines']) > len(chordBlock['lines']) else None

                    # If there is something to be added
                    if (len(lyricsBlock['lines']) + len(chordBlock['lines'])) > 0:
                        lyrics.append(lyricsBlock)
                        chords.append(chordBlock)

                    # Reset the block data structure
                    chordBlock = Block()
                    lyricsBlock = Block()

                    # Set the metadata of the new block and
                    # clear the lyric
                    chordBlock['metaData']['role'] = role
                    lyric = ''

            # If a chord was detected, add it
            chordBlock['lines'].append(chordLine) if len(chordLine) > 0 else None

            # If a lyric is not the first line of a block and has some alphabetic characters
            # we are able to make this former assumption because
            # chords always follow lyrics, this may unduly delete
            # some lines of lyrics, but never lyric/chord pairs
            # len(re.sub(r'[^\w]', '', lyric, flags=re.U).strip()) >= 5 and
            if len(chordBlock['lines']) > 0 and len(re.sub(r'[^\w]|[0-9]', '', lyric, flags=re.U).strip()) > 0:
                lyricsBlock['lines'].append(lyric.rstrip())

                # If a chord and a lyric were on the same line
                # mark it as embedded, we'll delete them later unless most
                # of the song is embedded
                if len(chordLine) > 0:
                    # The embeded line indexes
                    # after being added to the data structure
                    # i != index because some blocks never get added
                    embeddedLines.append((len(lyrics), len(lyricsBlock['lines']) - 1))
            else:
                # Add any missing "deleted" to the lostCharacters metaData field
                lyricsBlock['metaData']['lostCharacters'] += len(lyric.strip())

            # if we have added a line of lyrics without a chord, we
            # must have a missing chord. This is because we assume
            # a line of chords ALWAYS comes before the paired line of lyrics
            if len(chordBlock['lines']) < len(lyricsBlock['lines']):
                chordBlock['lines'].append(None)

            # If there was a line of chords in the middle of a block
            # with no following lyrics
            lyricsBlock['lines'].append(None) if len(chordBlock['lines'])-1 > len(lyricsBlock['lines']) else None

        # Terminate the block we've been building
        # If a block ends with chords but no lyrics or lyrics but no chords
        lyricsBlock['lines'].append(None) if len(chordBlock['lines']) > len(lyricsBlock['lines']) else None
        chordBlock['lines'].append(None) if len(lyricsBlock['lines']) > len(chordBlock['lines']) else None

        # If there is something to add
        if len(lyricsBlock['lines']) > 0 or len(chordBlock['lines']) > 0:
            lyrics.append(lyricsBlock)
            chords.append(chordBlock)

    # If less than half of the tab's lines were embedded
    # Loop through and delete the "embedded" lines
    # which are almost certainly non-lyric information
    if len(embeddedLines) <= sum(len(block['lines']) for block in lyrics) * .5:
        for blockId, lineId in reversed(embeddedLines):
            lyrics[blockId]['metaData']['lostCharacters'] += len(lyrics[blockId]['lines'][lineId])

            if len(chords[blockId]['lines']) > lineId + 1 and chords[blockId]['lines'][lineId + 1] == None:
                del lyrics[blockId]['lines'][lineId]
                del chords[blockId]['lines'][lineId + 1]
            else:
                lyrics[blockId]['lines'][lineId] = None

    if sum(len(block['lines']) for block in chords) != sum(len(block['lines']) for block in lyrics):
        raise Exception('Chord and lyric array lengths do not match on: ' + data['title'] + ' by ' + data['artist'])

    # if len(lyrics) > 0:
    #     print data['url'], data['title'], data['artist']
    #     print 'Number of Blocks:', len(lyrics)
    #     for i, block in enumerate(chords):
    #         print 'Block:', i
    #         print 'Lost Characters:', lyrics[i].metaData['lostCharacters']
    #         print 'Role:', block.metaData['role']
    #         for j, line in enumerate(block.lines):
    #             print '\t', line
    #             print '\t', lyrics[i].lines[j]
    #             print

    return chords, lyrics

_chordErrors = set()
def normalizeChords(chordBlocks):
    allChords = []
    allChordNotes = []
    allStream = music21.stream.Stream()
    for chordBlock in chordBlocks:
        blockChords = []
        blockChordNotes = []
        blockStream = music21.stream.Stream()
        for line in chordBlock.lines:
            if line:
                for index, chord in line:
                    chords.append(chord)
                    try:
                        if chord in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
                            notes = [chord]
                        else:
                            notes = [note.replace('b', '-') for note in mingus_chords.from_shorthand(chord)]

                        allChordNotes.append(notes)
                        blockChordNotes.append(notes)
                    except Exception as e:
                        _chordErrors.add(str(e))

        if len(blockChords) > 0:
            [blockStream.insert(music21.chord.Chord([note.replace('b', '-') for note in notes])) for notes in blockChordNotes]
            keys = [blockStream.analyze(type).tonicPitchNameWithCase for type in ['AardenEssen', 'Simple', 'BellmanBudge', 'KrumhanslSchmuckler', 'KrumhanslKessler', 'TemperleyKostkaPayne']]
            key = max(set(keys), key=keys.count)
            consensus = keys.count(key) / float(len(keys))
            chordBlock['metaData']['key'] = key
            chordBlock['metaData']['keyConsensus'] = consensus





parsedLyrics = {}
parsedTabs = {}

print 'Processing Lyrics.net...',
with open('./output/lyricsnet.csv', 'rb') as csvfile:
    allLyrics = csv.DictReader(csvfile)
    for data in allLyrics:
        allBlocks = []
        soup = BeautifulSoup(data['lyrics'].replace('\r\n', '<br/>').replace('\n', '<br/>'), 'html.parser')
        [s.replaceWithChildren() if s else None for s in soup(['script', 'img', 'p'])]
        lyrics = (unicode('').join(unicode(content) for content in soup.find('pre').contents))
        blocks = re.split(r'\<br\/>\s*\<br\/>', lyrics.strip())
        for i, block in enumerate(blocks):
            lyrics = block.split('<br/>')
            lyricBlock = Block()
            for j, lyric in enumerate(lyrics):
                lyricBlock['lines'].append(lyric.strip())
            allBlocks.append(lyricBlock)

        parsedLyrics[data['url']] = {
            'url': data['url'],
            'artist': data['artist'],
            'title': data['title'],
            'provider': data['provider'],
            'lyrics': allBlocks
        }
print 'Finished.'

print 'Processing Metro Lyrics...',
with open('./output/metrolyrics.csv', 'rb') as csvfile:
    allLyrics = csv.DictReader(csvfile)
    for data in allLyrics:
        allBlocks = []
        soup = BeautifulSoup(data['lyrics'].replace('\r', '').replace('\n', '').replace('<br>', '\r\n'), 'html.parser')
        blocks = soup.findAll('p')
        for i, block in enumerate(blocks):
            if len(block.contents) > 0:
                lyrics = (unicode('').join(unicode(content) for content in block.contents)).split('\r\n')
                lyricBlock = Block()
                for j, lyric in enumerate(lyrics):
                    lyricBlock['lines'].append(lyric.strip())
            allBlocks.append(lyricBlock)

        parsedLyrics[data['url']] = {
            'url': data['url'],
            'artist': data['artist'],
            'title': data['title'],
            'provider': data['provider'],
            'lyrics': allBlocks
        }
print 'Finished.'

print 'Processing Song Lyrics...',
with open('./output/songlyrics.csv', 'rb') as csvfile:
    allLyrics = csv.DictReader(csvfile)
    for data in allLyrics:
        allBlocks = []
        soup = BeautifulSoup(re.sub('\r?\n', '', data['lyrics']).replace('<br>', '\r\n'), 'html.parser')
        [s.replaceWithChildren() if s else None for s in soup(['script', 'img', 'p'])]

        blocks = (unicode('').join(unicode(content) for content in soup.contents)).split('\r\n\r\n')

        for i, block in enumerate(blocks):
            lyrics = block.strip().split('\r\n')
            lyricBlock = Block()
            for j, lyric in enumerate(lyrics):
                lyricBlock['lines'].append(lyric.strip())
            allBlocks.append(lyricBlock)

        parsedLyrics[data['url']] = {
            'url': data['url'],
            'artist': data['artist'],
            'title': data['title'],
            'provider': data['provider'],
            'lyrics': allBlocks
        }
print 'Finished.'

print 'Total Lyrics:', len(parsedLyrics.keys())
print 'Saving Lyrics...',
with open('./processed/lyrics.json', 'wb') as outfile:
    json.dump(parsedLyrics, outfile)

with open('./processed/lyrics.pkl ', 'wb') as outfile:
    pickle.dump(parsedLyrics, outfile)
print 'Saved.\n\n'


print 'Processing Echords...',
with open('./output/echords.csv', 'rb') as csvfile:
     tabs = csv.DictReader(csvfile)

     for data in tabs:
        # Pull out nonsense HTML tags
        tab = data['raw_tab'].replace('\r\n', '<br/>')
        tab = BeautifulSoup('<pre>' + tab + '</pre>', 'html.parser')
        [s.extract() for s in tab.findAll(text=lambda text:isinstance(text, Comment))]
        [s.extract() for s in tab.select('.hide_tab')]
        [s.replaceWithChildren() if s else None for s in tab(['script', 'img', 'p', 'div', 'i', 'b', 'span'])]
        tab = '<br/>' + (unicode('').join(unicode(content) for content in tab.contents))

        chords, lyrics = parseTab(tab)

        parsedTabs[data['url']] = {
            'url': data['url'],
            'artist': data['artist'],
            'title': data['title'],
            'contributor': data['contributor'],
            'provider': data['provider'],
            'provider-specific': {
                'key': data['key'],
                'comments': data['comments'],
                'youtube': data['youtube'],
                'rating': data['rating'],
                'difficulty': data['difficulty'],
                'type': data['type'],
            },
            'chords': chords,
            'lyrics': lyrics
        }

print 'Finished.'

print 'Processing Ultimate Guitar...',
with open('./output/ultimate-guitar.csv', 'rb') as csvfile:
    tabs = csv.DictReader(csvfile)
    for data in tabs:
        # Pull out nonsense HTML tags
        tab = data['raw_tab'].replace('\r\n', '<br/>').replace('\n', '<br/>')
        tab = BeautifulSoup("<pre>" + tab + "</pre>", 'html.parser')
        [s.extract() for s in tab.findAll(text=lambda text:isinstance(text, Comment))]
        [s.extract() for s in tab.select('.hide_tab')]
        [s.replaceWithChildren() if s else None for s in tab(['script', 'img', 'p', 'div', 'i', 'b', 'u'])]
        tab = '<br/>' + (unicode('').join(unicode(content) for content in tab))

        tab = tab.replace('<span>', '<u>').replace('</span>', '</u>')
        chords, lyrics = parseTab(tab)

        parsedTabs[data['url']] = {
            'url': data['url'],
            'artist': data['artist'],
            'title': data['title'],
            'contributor': data['contributor'],
            'provider': data['provider'],
            'provider-specific': {
                'rating': data['rating'],
                'comments': data['comments'],
                'type': data['type'],
                'difficulty': data['difficulty'].strip()
            },
            'chords': chords,
            'lyrics': lyrics
        }
print 'Finished.'

print 'Total Tabs:', len(parsedTabs.keys())
print 'Saving Tabs...',
with open('./processed/tabs.json', 'wb') as outfile:
    json.dump(parsedTabs, outfile)

with open('./processed/tabs.pkl ', 'wb') as outfile:
    pickle.dump(parsedTabs, outfile)
print 'Saved.\n\n'



# ********************
# Load/Read Pickle Demo
# ********************
with open('./processed/tabs.pkl ', 'rb') as infile:
    parsedTabs = pickle.load(infile)

with open('./processed/lyrics.pkl ', 'rb') as infile:
    parsedLyrics = pickle.load(infile)

# What does the parsedTab data-structure look like?
for key in parsedTabs:
    # key is the URL, but for consistancy "url" is also a feature
    tab = parsedTabs[key]
    print 'Title:', tab['title']
    print 'Artist:', tab['artist']
    print 'Contributor:', tab['contributor']
    print 'Provider:', tab['provider']
    print 'URL:', tab['url']
    print '# Chord Blocks:', len(tab['chords'])
    print '# Lyric Blocks:', len(tab['lyrics'])
    for i, chordBlock in enumerate(['chords']):
        # To help make it easier to see the structure,
        # I've used tab['chords'][i] consistently throughout the example
        # but it could easily be replaced with chordBlock
        if len(tab['chords']) > 0:
            print '\tBlock #', i
            print '\tNumber of Chord Lines:', len(tab['chords'][i]['lines'])
            print '\tNumber of Lyric Lines:', len(tab['lyrics'][i]['lines'])
            print '\tMeta-Data Block Role:', tab['chords'][i]['metaData']['role']
            print '\tMeta-Data Block Lost Characters:', tab['chords'][i]['metaData']['lostCharacters']
            for j, chordLine in enumerate(tab['chords'][i]['lines']):
                print '\t  Line #', j, 'Chords:', tab['chords'][i]['lines'][j]
                print '\t  Line #', j, 'Lyrics:', tab['lyrics'][i]['lines'][j]
                print
            print
    print '\n\n'

# What does the parsedLyric data-structure look like?
for key in parsedLyrics:
    lyricRecord = parsedLyrics[key]
    print 'Title:', lyricRecord['title']
    print 'Artist:', lyricRecord['artist']
    print 'Provider:', lyricRecord['provider']
    print 'URL:', lyricRecord['url']
    for i, lyricBlock in enumerate(lyricRecord['lyrics']):
        print '\tBlock #', i
        for j, line in enumerate(lyricBlock['lines']):
            print '\t  Line #', j, 'Lyrics:', line
    print '\n\n'

print "Total Loaded Tabs:", len(parsedTabs.keys())
print "Total Loaded Lyrics:", len(parsedLyrics.keys())
