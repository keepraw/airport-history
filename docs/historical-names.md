# Historical airport names: Astana

Reviewed on 2026-10-26, based on `main` at
`69352cad4d82236be1638757c259034a45ffadc2`, after confirming PR #3 was merged.
This change adds two canonical Russian official-name intervals for the existing
Astana airfield, `apt_99f19660-7609-49c5-b221-ed4a37046566`. It creates no physical
airport, code assignment or location change. The other twelve airports have no
curated name timeline yet; their static names remain reference labels.

## Independent source review

| Source ID | Source and supported claim | Limits |
| --- | --- | --- |
| `astana-name-original-2017` | [Original Government Resolution No. 381, reproduced in Kazakhstanskaya Pravda](https://kazpravda.kz/uploads/redactors/files/5949db169808b1498012438.pdf), page 1, second resolution: signed June 20, 2017; changes the airport's name and makes first official publication the effective day | The PDF also contains No. 380, which changes general naming rules. Neither the PDF file timestamp nor No. 380 is used as the airport-name boundary. No exact local-midnight instant is stated |
| `astana-name-publication` | [Adilet official publication metadata](https://old.adilet.zan.kz/rus/docs/P1700000381/info): Kazakhstanskaya Pravda, June 21, 2017, No. 117 (28496), and Egemen Qazaqstan, June 21, 2017, No. 117 (29098) | The later collected acts were signed for printing on July 20; that is not the first publication. Adoption on June 20 is a different event |
| `astana-name-observation-2006` | [Government Resolution No. 1095, November 20, 2006](https://old.adilet.zan.kz/rus/docs/P060001095_): development plan repeatedly identifies the existing Astana airport and its infrastructure under the old name | This is an observation of the name, not its original naming decision. The corporate title by itself is not treated as an airport-renaming event |
| Existing `nqz-code-change` and `nqz-implementation` | [Aviation Administration, April 6, 2020](https://caa.gov.kz/ru/blog/post/kod-aeroporta-g-nur-sultan-izmenen), and [June 7, 2020](https://caa.gov.kz/ru/blog/post/nqz-novoe-imya-na-karte-poletov), still use the new airport name while describing the later IATA change | These support later use of the name; the NQZ implementation date does not establish the name's start |
| Existing `ourairports-batch1-20261025` | Fixed OurAirports reference row for the same physical identity uses the corresponding contemporary English label | Secondary corroboration for inferred continuation to the fixed evidence horizon only; it cannot establish the 2017 rename or any earlier name |

The original 2017 text matters. The [current consolidated resolution](https://old.adilet.zan.kz/rus/docs/P1700000381)
contains a July 10, 2020 amendment to paragraph 1 concerning the joint-stock
company. Its [revision history](https://old.adilet.zan.kz/rus/docs/P1700000381/history)
distinguishes the two versions. Reading only the consolidated paragraph would
conflate corporate naming with the original airport decision. We use the original
newspaper text for the 2017 airport rename and do not create a second airport-name
event for the 2020 corporate wording.

An [official later announcement](https://www.gov.kz/memleket/entities/kds/press/news/details/5812?lang=ru)
summarizes the airport rename with the June 20 signing date, and an
[English news account](https://qazinform.com/news/astana-international-airport-to-bear-the-name-of-president-nazarbayev_a3038012)
describes publication as June 20. The original
effective clause and official publication metadata together establish **June 21,
2017**. No current name, city rename, Wikipedia list or terminal opening is used
to infer that date.

## Admitted intervals and uncertainty

| Name ID | Canonical official name (`ru`) | Start boundary | End boundary |
| --- | --- | --- | --- |
| `name-astana-before-2017` | Международный аэропорт Астана | Unknown original start; latest possible start 2006-11-21, after the November 20 observation | Effective day 2017-06-21, bounded by 2017-06-21 / 2017-06-22 |
| `name-astana-nazarbayev-2017` | Международный аэропорт Нурсултан Назарбаев | Effective day 2017-06-21, bounded by 2017-06-21 / 2017-06-22 | Unknown end; earliest possible end 2026-10-25, the existing fixed evidence horizon |

Both records are reviewed `continuity_inference` conclusions. The boundary has
direct primary evidence, but the whole continuous use between dated observations
does not. Review status describes this explicitly limited conclusion; it does not
upgrade the interval to a direct daily ledger. No historical name before the
earliest observation is added or asserted as certain. The source registry preserves
publication type separately from claim evidence type.

The existing conservative civil-date policy is retained: `day` precision does not
assert a midnight instant. Thus June 20 resolves to the old name, June 21 is
`uncertain` with both candidates, and June 22 resolves to the new name. The
effective calendar day is known; the exact instant and attribution of the whole
effective day remain unproved. Dates before 2006-11-21 or on/after 2026-10-25 are
also uncertain. The evidence horizon is not a claimed retirement date.

City changes in 2019 and 2022 and the June 8, 2020 TSE/NQZ code change are separate
subjects. They neither split this physical identity nor create name records.
English labels in prose are translations, not additional official-name periods.
The data retains the Russian original; this version has no language-preference
API or complete catalogue of simultaneous official-language forms.

## Missing information, compatibility and validation

The new `resolveAirportName` API uses only canonical `official` records. `alias`
and `translation` records can be stored with their own time/evidence/review fields,
but do not compete with official names or certify a date. City names are excluded.
The curated seed contains only the two official records; alternate-kind tests use
explicitly synthetic records rather than invented historical aliases.

Where no official-name interval can apply, `reference` returns the existing static
label with `historicallyVerified: false`, regardless of the static fact's status.
Uncertain or conflicting claims return no selected name and retain candidates and
evidence. The resolver never overwrites the airport object or changes code results.

Schema **3.0.0** requires `names`; package/data version **0.4.0** introduced it
(current data version 0.5.0 uses `dist/v0.5.0/`; no name records were added in 0.5.0). Schema 2 input must be explicitly migrated with `names: []` before
adding reviewed name records. All thirteen physical records, twenty code
assignments and twenty-six original source records are preserved. There is no
automatic promotion from static labels, language translations or city names.

Tests cover both actual name periods, signing/publication/effective-day distinctions,
the corporate amendment and IATA change, evidence horizons, exact synthetic
half-open boundaries, day/month/year uncertainty, missing timelines and gaps,
aliases/translations, pending/disputed evidence, reviewed conflicts, invalid fields,
input immutability and order-independent results. The build regression resolves
names from exported JSON, compares every artifact byte in two timezones and checks
all manifest hashes. Validation retains six code warnings and adds one expected
official-name boundary warning, with no confirmed conflict in the curated seed.

No other real rename is needed to exercise this minimal model. Earlier Astana
names, original name-adoption dates, exact intraday attribution, other airports'
name histories, localization and global candidate discovery remain future work.
There is no crawler, Keepraw-Fly change, Release, publication or automatic merge.

New sources are reference-only links with independently written factual notes;
no government document or newspaper PDF is bundled or relicensed. MIT/CC0 scopes
and existing upstream terms remain as described in `THIRD_PARTY_NOTICES.md`.
