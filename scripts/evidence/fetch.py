"""Explicit online acquisition. Ordinary evidence builds never access the network."""
import argparse
import datetime as dt
import gzip
import hashlib
import http.cookiejar
import io
import json
import re
import sys
import urllib.parse
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path

from pipeline import BASE, ROOT, plain_text
from common import digest, write_json

BTS_URL = 'https://www.transtats.bts.gov/DL_SelectFields.aspx?QO_fu146_anzr=N8vn6v10+f722146+gnoyr5&gnoyr_VQ=FLL'
HEADERS = {'User-Agent': 'Keepraw-Airport-History/1.0 (public historical evidence research)'}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as response:
        return response.read(), response.geturl()


class Fields(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'input' and 'name' in a and (a.get('type') == 'hidden' or a.get('type') == 'checkbox' and a['name'].isupper()):
            self.values[a['name']] = a.get('value', 'on')


def bts():
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    with opener.open(urllib.request.Request(BTS_URL, headers=HEADERS), timeout=60) as response:
        page = response.read()
    form = Fields()
    form.feed(page.decode())
    if 'AIRPORT_SEQ_ID' not in form.values or '__VIEWSTATE' not in form.values:
        raise ValueError('BTS form changed; inspect before collecting')
    form.values.update(btnDownload='Download', cboGeography='All', cboYear='All', cboPeriod='All')
    request = urllib.request.Request(BTS_URL, data=urllib.parse.urlencode(form.values).encode(), headers=HEADERS)
    with opener.open(request, timeout=60) as response:
        transport = response.read()
    with zipfile.ZipFile(io.BytesIO(transport)) as archive:
        raw = archive.read('T_MASTER_CORD.csv')
    return raw, hashlib.sha256(transport).hexdigest()


def effective_date(raw):
    # This is regulatory effectiveness ONLY, never the airport event date.
    text = ' '.join(plain_text(raw).split())
    match = re.search(r'DATES:\s*(?:This determination is effective|Effective(?: date)?(?: 0901 UTC,?)?)\s*([A-Z][a-z]+ \d{1,2}, \d{4})', text)
    return dt.datetime.strptime(match[1], '%B %d, %Y').date().isoformat() if match else None


def save_source(output, raw, **metadata):
    path = output / metadata['inputPath']
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as stream:
        with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as compressed:
            compressed.write(raw)
    sha = hashlib.sha256(raw).hexdigest()
    return {**metadata, 'originalSha256': sha, 'originalBytes': len(raw), 'version': 'sha256:' + sha,
            'inputSha256': digest(path), 'sourceType': 'primary',
            'independence': {'originalIssuer': True, 'independentOfDirectoryPublication': True,
                             'underlyingFactLineage': 'not_established_per_claim',
                             'mirrorsCountAsIndependent': False},
            'accessRestrictions': 'Public anonymous HTTP; moderate sequential requests; upstream can change or rate-limit.',
            'license': {'id': 'LicenseRef-US-Government', 'url': 'https://www.govinfo.gov/about/policies',
                        'note': 'US federal government factual publication (17 USC 105); attribution retained. Not an assertion that all third-party attachments are public domain.'}}


def discover(output, cutoff, base_commit):
    dt.date.fromisoformat(cutoff)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Discover into an empty directory; do not silently replace source locks')
    accessed = lambda: dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    raw, transport_sha = bts()
    sources = [save_source(output, raw, sourceId='bts-master-coordinate', provider='bts-master',
        publisher='US Department of Transportation, Bureau of Transportation Statistics',
        title='Aviation Support Tables: Master Coordinate', url=BTS_URL, retrievalUrl=BTS_URL,
        originalPublicationKey='usdot-bts:T_MASTER_CORD:' + hashlib.sha256(raw).hexdigest(),
        sourceFamily='usdot-bts', publicationDate=None, documentEffectiveDate=None, accessedAt=accessed(),
        inputPath='inputs/bts-master.csv.gz', transportSha256=transport_sha,
        metadataUrl='https://www.transtats.bts.gov/Fields.asp?gnoyr_VQ=FLL',
        supports=['Issuer-reported historical statistical attributes, USDOT airport code, names and coordinates.'],
        limitations=['USDOT is not IATA. Statistical attribute dates are not operational or code-allocation dates.',
                     'Publication/revision date unavailable; version is the actual content hash.'])]
    params = {'conditions[agencies][]': 'federal-aviation-administration',
              'conditions[term]': '"airport" "permanently closed"',
              'conditions[publication_date][lte]': cutoff, 'per_page': '100', 'order': 'newest'}
    url = 'https://www.federalregister.gov/api/v1/documents.json?' + urllib.parse.urlencode(params)
    search_url = url
    selected, failures = [], []
    while url:
        raw_search, _ = get(url)
        result = json.loads(raw_search)
        selected.extend(result['results'])
        url = result.get('next_page_url')
    for document in selected:
        number, date = document['document_number'], document['publication_date']
        url = f'https://www.govinfo.gov/content/pkg/FR-{date}/html/{number}.htm'
        try:
            raw, final_url = get(url)
            plain_text(raw)  # Refuse HTML error/challenge pages.
            sources.append(save_source(output, raw, sourceId='faa-fr-' + number, provider='faa-fr',
                publisher='Federal Aviation Administration; published by Office of the Federal Register/GPO',
                title=document['title'], url=document['html_url'], retrievalUrl=final_url,
                originalPublicationKey='usdot-faa:FR:' + number, sourceFamily='usdot-faa',
                publicationDate=date, documentEffectiveDate=effective_date(raw), accessedAt=accessed(),
                inputPath='inputs/fr-' + number + '.htm.gz', documentNumber=number,
                publicationType=document['type'],
                supports=['FAA statements and regulatory location blocks in the cited original paragraphs.'],
                limitations=['Proposed/final rule effectiveness is not a facility closure, opening or code allocation date.',
                             'An air traffic tower or runway closure does not establish airport closure.',
                             'Metadata search is discovery only; GovInfo contains the original agency publication.']))
        except (OSError, ValueError) as error:
            failures.append({'documentNumber': number, 'url': url, 'error': str(error)})
    write_json(output / 'source-lock.json', {'formatVersion': 1, 'preparedOn': cutoff, 'baseCommit': base_commit,
        'selection': {'searchUrl': search_url, 'documentsDiscovered': len(selected), 'scope': 'All results of a targeted closure phrase query, plus the complete BTS table; not the complete FAA corpus.'},
        'sources': sources, 'failures': failures})
    print(f'Acquired {len(sources)} primary publications; {len(failures)} failures retained. Review the new lock before adoption.')


def recover(output):
    lock = json.loads((BASE / 'source-lock.json').read_text())
    output.mkdir(parents=True, exist_ok=True)
    for source in lock['sources']:
        raw = bts()[0] if source['provider'] == 'bts-master' else get(source['retrievalUrl'])[0]
        if hashlib.sha256(raw).hexdigest() != source['originalSha256']:
            raise ValueError(f"Upstream content changed: {source['sourceId']}. Keep pinned input; discover a separately reviewed snapshot.")
        path = output / source['inputPath']
        path.parent.mkdir(parents=True, exist_ok=True)
        # GzipFile fixes the same header/OS bytes used by discovery. gzip.compress
        # differs across Python/zlib versions even when the original bytes match.
        with path.open('wb') as stream:
            with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as compressed:
                compressed.write(raw)
        if digest(path) != source['inputSha256']:
            raise ValueError('Recovered compression differs from the pinned input: ' + source['sourceId'])
    print('Recovered hash-verified originals into ' + str(output))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--discover', action='store_true')
    parser.add_argument('--cutoff', default='2026-10-28')
    parser.add_argument('--base-commit', default='d520136e82a348ff6f3429f9c879672ad1dfa5b8')
    args = parser.parse_args()
    discover(args.output, args.cutoff, args.base_commit) if args.discover else recover(args.output)
