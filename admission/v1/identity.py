"""Physical identity predicates and rule-authorized, idempotent UUID allocation."""
from copy import deepcopy
import datetime as dt
import math
import re
import uuid
from urllib.parse import urlparse, parse_qs

from runtime import authorize, checked_bindings, digest, require, sha

AUTO = 'AUTO_ELIGIBLE'
MANUAL = 'MANUAL_REVIEW'
INSUFFICIENT = 'INSUFFICIENT_EVIDENCE'


def risk_screen(candidate, evidence, store, times, p):
    """Independent physical-risk review; it neither uses nor grants code authority."""
    import json
    from zoneinfo import ZoneInfo
    from evidence import source_data, old
    timezone = ZoneInfo(p['rules']['observationTimezone'])
    start = dt.datetime.combine(times[0].astimezone(timezone).date() + dt.timedelta(days=1), dt.time(), timezone)
    end = dt.datetime.combine(times[-1].astimezone(timezone).date(), dt.time(), timezone)
    code = candidate.get('observedCode')
    require(code, 'Airport notice discovery locator required; it is not identity proof')
    rows, found_airport = [], False
    for entry in evidence['sources']:
        query = parse_qs(urlparse(entry['url']).query)
        location = query.get('sch_airport', [None])[0]
        if location != code:
            continue
        if query.get('sch_from_date', ['9999'])[0] > start.date().isoformat() or query.get('sch_to_date', ['0000'])[0] < end.date().isoformat():
            continue
        require(urlparse(entry['url']).hostname in p['scope']['aipHosts'], 'Unofficial risk source')
        data = json.loads(source_data(entry, store))
        require(data['Total'] == len(data['DATA']), 'Incomplete physical-risk NOTAM coverage')
        found_airport = True
        for i, item in enumerate(data['DATA']):
            old.original_notice(item)
            require(item['LOCATION'] == code, 'Wrong physical-risk airport query')
            rows.append(old.research.metadata(item, entry['sourceId'], i))
    require(found_airport, 'Missing complete official airport notice coverage')
    signals = []
    for row in rows:
        if row['noticeType'] == 'C':
            continue
        beginning = old.research.instant(row['b']['raw'])
        hard_end = old.research.instant(row['c']['raw']) if not row['estimatedEnd'] else None
        successors = [r for r in rows if r['replacesOrCancels'] == row['seriesBaseNo']]
        ends = [hard_end] if hard_end else []
        for successor in successors:
            b, issued = old.research.instant(successor['b']['raw']), old.research.instant(successor['issued']['raw'])
            if b and issued: ends.append(max(b, issued))
        ending = min(ends) if ends else None
        if beginning and beginning >= end or ending and ending <= start:
            continue
        if not beginning or ending is None or (row['replacesOrCancels'] and not any(r['seriesBaseNo'] == row['replacesOrCancels'] for r in rows)):
            signals.append('unresolved_physical_notice_lifecycle')
        if row['identityChangeSignal'] or row['qcode'] == 'QFALC':
            signals.append('physical_identity_change_or_whole_airport_closure')
    return sorted(set(signals))


def metres(a, b):
    for point in (a, b):
        require(set(point) == {'latitude', 'longitude'} and
                all(isinstance(v, (float, int)) and math.isfinite(v) for v in point.values()) and
                -90 <= point['latitude'] <= 90 and -180 <= point['longitude'] <= 180, 'Invalid coordinates')
    lat1, lat2 = map(math.radians, (a['latitude'], b['latitude']))
    dlat = lat2-lat1
    dlon = math.radians(b['longitude']-a['longitude'])
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371008.8 * 2 * math.asin(min(1, math.sqrt(h)))


def arp(value):
    match = re.fullmatch(r'(\d{2})(\d{2})(\d{2})([NS]) (\d{3})(\d{2})(\d{2})([EW])', value)
    require(match, 'Unknown ARP coordinate representation')
    d, m, s, ns, d2, m2, s2, ew = match.groups()
    require(max(int(m), int(s), int(m2), int(s2)) < 60, 'Invalid DMS coordinate')
    point = {'latitude': (int(d)+int(m)/60+int(s)/3600) * (-1 if ns == 'S' else 1),
             'longitude': (int(d2)+int(m2)/60+int(s2)/3600) * (-1 if ew == 'W' else 1)}
    metres(point, point)
    return point


def site_key(candidate):
    # An operator's durable facility locator is independent of ICAO/name/ARP.
    # Proximity checks below also catch changed locators and grid-boundary aliases.
    return 'site_' + sha([candidate['country'], candidate['independent']['facilityKey']])


def original(source_id, evidence, store, hosts):
    entry = next((s for s in evidence['sources'] if s['sourceId'] == source_id), None)
    require(entry is not None and 'originalSha256' in entry, 'Missing necessary original: ' + source_id)
    host = urlparse(entry['url']).hostname
    require(urlparse(entry['url']).scheme == 'https' and host in hosts and
            urlparse(entry.get('finalUrl', entry['url'])).hostname == host, 'Unqualified source host')
    observed = dt.datetime.fromisoformat(entry['observedAt'])
    require(observed.utcoffset() is not None and observed <= dt.datetime.now(dt.timezone.utc), 'Invalid observation time')
    data = store.read(entry['originalSha256'])
    require(len(data) == entry['originalBytes'], 'Original size mismatch')
    from evidence import extract
    return ' '.join(extract(data).split()), entry


def classify(candidate, p, evidence, store, inventory):
    """Classification never grants authority and never creates an ID."""
    reasons, missing = [], []
    point, key = None, None
    try:
        scope, rules = p['scope'], p['rules']
        require(candidate['country'] in scope['countries'] and candidate['issuerFamily'] in scope['issuerFamilies'], 'Outside identity rule scope')
        require(candidate.get('synthetic', False) is False, 'Synthetic evidence is never production evidence')
        observations = candidate['observations']
        require(len(observations) >= rules['minimumObservations'], 'Two controlled observations required')
        times = [dt.datetime.fromisoformat(o['effectiveUtc']) for o in observations]
        require(all(t.utcoffset() == dt.timedelta(0) for t in times) and times == sorted(set(times)) and
                0 < (times[-1]-times[0]).total_seconds() <= rules['maximumObservationGapDays']*86400,
                'Unknown, reversed or excessive observation interval')
        point = arp(observations[0]['arpDms'])
        names = {o['aipName'] for o in observations}
        if len(names) != 1:
            reasons.append('name_conflict')
        adapter = p['controlledAipAdapter']
        for observation, effective in zip(observations, times):
            if metres(point, arp(observation['arpDms'])) > rules['maximumArpMovementMetres']:
                reasons.append('relocation_or_changed_arp')
            text, source = original(observation['sourceId'], evidence, store, scope['aipHosts'])
            edition = re.fullmatch(adapter['urlPattern'], source['url'])
            final_edition = re.fullmatch(adapter['urlPattern'], source.get('finalUrl', source['url']))
            require(edition and final_edition and edition.groupdict() == final_edition.groupdict() and
                    edition['edition'] == effective.date().isoformat() and
                    edition['code'] == candidate.get('observedCode') and
                    effective.strftime('%H:%M:%S') == adapter['effectiveClockUtc'] and
                    dt.datetime.fromisoformat(source['observedAt']) >= effective,
                    'AIP original/edition/effective-time association unproved')
            reported = re.search(r'ARP coordinates and site at AD\s+(\d{6}[NS] \d{7}[EW])', text)
            if reported and reported[1] != observation['arpDms']:
                reasons.append('conflicting_original_arp')
            require(candidate.get('observedCode') in text and observation['aipName'] in text and observation['arpDms'] in text,
                    'Original does not establish named airport and ARP')
        controls = candidate['editionControl']
        require(controls['fromUtc'] == observations[0]['effectiveUtc'] and
                controls['toUtc'] == observations[-1]['effectiveUtc'] and
                controls['expectedIntermediateEditions'] == [e['edition'] for e in controls['intermediateEditions']],
                'Intermediate edition coverage is incomplete')
        require(len(set(controls['expectedIntermediateEditions'])) == len(controls['expectedIntermediateEditions']), 'Duplicate amendment control')
        # The official index and amendment originals must substantiate the
        # closed edition list. An unchecked caller-supplied boolean is insufficient.
        for control in [controls['index'], *controls['intermediateEditions']]:
            text, _ = original(control['sourceId'], evidence, store, scope['aipHosts'])
            require(control['tokens'] and all(token in text for token in control['tokens']), 'Unreproduced edition control')
        index_text, _ = original(controls['index']['sourceId'], evidence, store, scope['aipHosts'])
        anchor_pattern = r'(\d{2} [A-Z]{3} \d{4})\s*(\d{2} [A-Z]{3} \d{4})\s*AIRAC AIP AMDT \d+/\d+\s*\(WEF (\d{4}) UTC (\d{2} [A-Z]{3} \d{4})\)'
        anchors = {(dt.datetime.strptime(effective, '%d %b %Y').date().isoformat(), clock)
                   for effective, published, clock, stated in re.findall(anchor_pattern, index_text)
                   if effective == stated}
        require(all((time.date().isoformat(), time.strftime('%H%M')) in anchors for time in (times[0], times[-1])),
                'Official AIRAC index does not establish both observation instants')
        pattern = r'(\d{2} [A-Z]{3} \d{4})\s*(\d{2} [A-Z]{3} \d{4})\s*((?:AIRAC )?AIP AMDT \d+/\d+)'
        parsed = []
        for effective, published, edition in re.findall(pattern, index_text):
            date = dt.datetime.strptime(effective, '%d %b %Y').date()
            if times[0].date() < date < times[-1].date():
                parsed.append(edition)
        require(sorted(set(parsed)) == sorted(controls['expectedIntermediateEditions']), 'Official index has omitted intermediate editions')
        support = candidate['independent']
        profiles = [v for v in p['independentSourceProfiles'] if v['host'] == urlparse(support['facilityKey']).hostname]
        require(len(profiles) == 1, 'No qualified independent source lineage')
        profile = profiles[0]
        require(candidate['issuerFamily'] not in profile['upstreamFamilies'] and
                profile['factOrigin'] == 'operator-own-facility-address' and
                support['sourceId'] != observations[0]['sourceId'], 'Sources share the AIP upstream')
        text, entry = original(support['sourceId'], evidence, store, [profile['host']])
        require(entry['url'] == support['facilityKey'], 'Facility locator not bound to independent original')
        require(support['addressTokens'] and all(token in text for token in support['addressTokens']),
                'Independent original lacks the named site address')
        require(support['siteNameToken'] in text, 'Independent original does not identify the airport')
        # Link the operator's own street address to the AIP administrative address.
        # NOAA vicinity, a shared code, or a shared name cannot satisfy this join.
        require(support['aipAddressTokens'], 'Independent address not linked to AIP location')
        for observation in observations:
            aip_text, _ = original(observation['sourceId'], evidence, store, scope['aipHosts'])
            aliases = p.get('addressAliases', {})
            require(all(token.casefold() in aip_text.casefold() and
                        any(alias.casefold() in text.casefold() for alias in [token, *aliases.get(token, [])])
                        for token in support['aipAddressTokens']), 'AIP/operator street address linkage unproved')
        key = site_key(candidate)
        require(candidate['riskReview']['coverageSourceIds'] and
                set(candidate['riskReview']['coverageSourceIds']) <= {s['sourceId'] for s in evidence['sources']},
                'Missing reproducible risk coverage')
        for sid in candidate['riskReview']['coverageSourceIds']:
            risk_text, _ = original(sid, evidence, store, scope['aipHosts'])
            if re.search(r'(?:AIRPORT|AERODROME)\s+(?:RELOCAT\w*|PERMANENTLY CLOSED)|(?:ARP COORDINATES?|LOCATION INDICATOR)\s+(?:CHANGED|REASSIGNED)', risk_text, re.I):
                reasons.append('original_identity_change_signal')
        reasons.extend(candidate['riskReview']['signals'])
        require(candidate['competitionInventorySha256'] == sha(inventory), 'Stale formal/pending/historical site competition inventory')
        reasons.extend(risk_screen(candidate, evidence, store, times, p))
        for existing in inventory:
            near = metres(point, existing['coordinates']) <= rules['duplicateSearchRadiusMetres']
            same_key = existing.get('siteKey') == key
            same_code = candidate.get('observedCode') and candidate.get('observedCode') in existing.get('codes', [])
            if existing.get('status') == 'reference':
                # Directory rows only suggest competition. A previously
                # unverified same-site row may be matched AFTER independent
                # named-site/address/AIP proof, never by code/proximity alone.
                if (same_code and not existing.get('historical') and
                        metres(point, existing['coordinates']) <= rules['referenceVicinityMetres']):
                    continue
                if same_code or near:
                    reasons.append('unresolved_reference_site_competition')
                continue
            if same_key and not near:
                reasons.append('facility_locator_reused_at_different_site')
            elif near and not same_key:
                reasons.append('competing_or_duplicate_physical_site')
            elif same_code and not near:
                reasons.append('same_code_different_physical_site')
            if same_key and existing.get('status') == 'historical':
                reasons.append('historical_site_reuse')
    except (ValueError, KeyError, TypeError, FileNotFoundError) as error:
        if 'conflict' in str(error).lower():
            reasons.append(str(error))
        else:
            missing.append(str(error))
    state = MANUAL if reasons else INSUFFICIENT if missing else AUTO
    return {'candidateKey': candidate.get('candidateKey'), 'siteKey': key, 'coordinates': point,
            'classification': state, 'reasons': sorted(set(reasons)), 'evidenceGaps': missing,
            'candidateSha256': sha(candidate), 'evidenceVersionSha256': sha(evidence),
            'policyKey': p['policyKey'], 'authorizationRequired': True}


def queue(results, previous=()):
    """One durable exception per site/candidate and category, with evidence revisions."""
    entries = {r['taskId']: deepcopy(r) for r in previous}
    for result in results:
        if result['classification'] == AUTO:
            continue
        key = 'exception_' + sha([result['siteKey'] or result['candidateKey'], result['classification']])
        entry = entries.setdefault(key, {'taskId': key, 'candidateKey': result['candidateKey'],
                                        'classification': result['classification'], 'revisions': []})
        revision = {k: result[k] for k in ('candidateSha256', 'evidenceVersionSha256', 'reasons', 'evidenceGaps')}
        if revision not in entry['revisions']:
            entry['revisions'].append(revision)
    return sorted(entries.values(), key=lambda r: r['taskId'])



def classify_batch(candidates, p, evidence, store, inventory):
    results = [classify(c, p, evidence, store, inventory) for c in candidates]
    # Check the entire batch BEFORE the first allocation. Encounter order must
    # never let one side of a competing-site pair slip through.
    for i, left in enumerate(results):
        for j, right in enumerate(results[i+1:], i+1):
            if left['coordinates'] is None or right['coordinates'] is None:
                continue
            near = metres(left['coordinates'], right['coordinates']) <= p['rules']['duplicateSearchRadiusMetres']
            same_site = left['siteKey'] == right['siteKey'] and left['siteKey'] is not None
            same_code = candidates[i].get('observedCode') and candidates[i].get('observedCode') == candidates[j].get('observedCode')
            if (near and not same_site) or (same_site and not near) or (same_code and not near):
                for result in (left, right):
                    result['classification'] = MANUAL
                    result['reasons'].append('batch_competing_physical_site')
    return results


def allocate(candidates, p, grants, evidence, store, inventory, registry):
    grant = authorize(p, grants)  # No UUID, output, or registry mutation before live authorization.
    checked_bindings(p)
    require(registry['formatVersion'] == 1, 'Unsupported permanent site registry')
    output = deepcopy(registry)
    require(len({r['siteKey'] for r in output['identities']}) == len(output['identities']) and
            len({r['airportId'] for r in output['identities']}) == len(output['identities']), 'Duplicate registry identity')
    results = classify_batch(candidates, p, evidence, store, inventory)
    # Legacy credentials are verified before the first UUID allocation.
    from provenance import revalidate_registry
    output = revalidate_registry(output, candidates, p, grants, evidence, store, inventory)
    accepted = []
    current_inventory = deepcopy(inventory)
    for candidate, result in zip(candidates, results):
        # Competition inventory is frozen by the batch; allocations in this
        # same batch are additionally checked, without rewriting that snapshot.
        if result['classification'] == AUTO:
            for existing in current_inventory[len(inventory):]:
                if metres(result['coordinates'], existing['coordinates']) <= p['rules']['duplicateSearchRadiusMetres'] and existing['siteKey'] != result['siteKey']:
                    result['classification'] = MANUAL
                    result['reasons'].append('batch_competing_physical_site')
            prior = next((r for r in output['identities'] if r['siteKey'] == result['siteKey']), None)
            if prior:
                require(metres(prior['coordinates'], result['coordinates']) <= p['rules']['maximumArpMovementMetres'], 'Existing permanent site moved')
            if result['classification'] == AUTO:
                entry = prior or {'siteKey': result['siteKey'], 'airportId': 'apt_' + str(uuid.uuid4()),
                    'coordinates': result['coordinates'], 'policyKey': p['policyKey'], 'bindings': checked_bindings(p),
                    'authorizationSha256': sha(grant), 'candidateSha256': sha(candidate),
                    'evidenceVersionSha256': sha(evidence), 'sourceIds': sorted({o['sourceId'] for o in candidate['observations']} | {candidate['independent']['sourceId']})}
                if prior is None:
                    output['identities'].append(entry)
                    current_inventory.append({**entry, 'codes': [], 'status': 'pending'})
                else:
                    attestation = {'candidateSha256': sha(candidate), 'evidenceVersionSha256': sha(evidence),
                                   'bindings': checked_bindings(p), 'authorizationSha256': sha(grant)}
                    if not any(all(a.get(k) == v for k, v in attestation.items())
                               for a in entry.setdefault('revalidations', [])):
                        entry['revalidations'].append(attestation)
                accepted.append({'candidate': candidate, 'identity': entry, 'decision': result})
    return {'registry': output, 'accepted': accepted, 'decisions': results, 'exceptions': queue(results)}
