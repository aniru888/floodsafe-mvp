# Verified Flood Event Dates — All 5 Cities

> Date: 2026-03-07
> Purpose: Temporal contrast analysis (Part B of city XGBoost profiling)
> Status: Research compilation
> Method: Web search + existing project data files, source-checked

---

## How to Read This Document

Each event includes:
- **Date**: YYYY-MM-DD (or YYYY-MM if exact day unknown)
- **Confidence**: HIGH (exact date + multiple sources), MEDIUM (date from single source), LOW (approximate/month-level)
- **Source**: News outlet or database with URL where available
- **Sentinel-1 era**: Events from 2014+ are usable for SAR temporal analysis

### Tiered Analysis Thresholds (from design doc)
- **<8 unique dates**: Descriptive statistics only
- **8-14 unique dates**: Mixed-effects model
- **15+ unique dates**: Constrained XGBoost

---

## 1. Delhi — 45+ Events (6 post-2014 with exact dates)

### Source: `apps/backend/data/delhi_historical_floods.json` (IFI-Impacts database)

The IFI-Impacts dataset contains 45 events from 1969-2023. For temporal contrast analysis, we need post-2014 events (Sentinel-1 era).

#### Post-2014 Events (HIGH confidence, exact dates)

| # | Date | Districts/Areas | Severity | Rainfall | Source |
|---|------|----------------|----------|----------|--------|
| 1 | **2020-07-19** | New Delhi | Moderate | Heavy rain + urban flooding | IFI-Impacts database |
| 2 | **2021-07-19** | New Delhi | Moderate | Record monsoon rainfall | IFI-Impacts database |
| 3 | **2022-10-09** | Central | Moderate | Unseasonal heavy rain | IFI-Impacts database |
| 4 | **2023-07-09** | North, North East, West | Severe | 153mm in single day (highest July daily in 40 years), Yamuna overflow | IFI-Impacts database; [SANDRP Parliamentary Report](https://sandrp.in/2024/02/20/delhi-july-2023-floods-parliamentary-committee-report-raises-more-questions/); [Wikipedia - 2023 North India floods](https://en.wikipedia.org/wiki/2023_North_India_floods) |
| 5 | **2024-06-28** | South Delhi (Sangam Vihar), citywide | Severe | 228.1mm in 24h (highest single June day in 88 years). 11 deaths, 4 drowned in underpasses | [CNN](https://www.cnn.com/2024/07/01/climate/india-delhi-floods-extreme-rain-intl-hnk); [Down to Earth](https://www.downtoearth.org.in/water/why-does-delhi-flood-the-answer-lies-in-our-urban-stormwater-management); [ReliefWeb Situation Report](https://reliefweb.int/report/india/situation-report-2-delhi-ncr-rains-waterlogging-date-01st-aug-2024-thu-time-0300-pm-ist) |
| 6 | **2024-07-31** | Old Rajinder Nagar, Ghazipur, citywide | Severe | Heavy rainfall. Schools closed Aug 1. Woman + toddler drowned in Ghazipur | [Outlook India](https://www.outlookindia.com/national/delhi-rains-traffic-advisory-schools-closed-death-injury-waterlogging-weather-updates) |

**Post-2014 unique dates: 6** → Tier: Descriptive statistics only

#### Pre-2014 Events (useful for non-SAR static feature analysis)

39 additional events from IFI-Impacts (1969-2013). Notable:
- 1978-09-01: Severe (multi-district)
- 1983-04-15, 1983-07-26: Moderate (all districts)
- 1995-09-04 through 1995-09-09: Three events in 5 days
- 2003-07-05, 2003-07-09: Two events in 4 days
- 2013-06-16: Moderate

Full list in `apps/backend/data/delhi_historical_floods.json`.

---

## 2. Bangalore — 17 Events (all post-2014)

### Sources: Web search (FloodList, Deccan Herald, The Watchers, ORF, Scroll.in, research papers)

| # | Date | Areas Affected | Severity | Rainfall | Confidence | Source |
|---|------|---------------|----------|----------|------------|--------|
| 1 | **2014-09-26** | Widespread | Cloudburst | 89.6mm in ~70 minutes | HIGH | [Tandfonline research paper](https://www.tandfonline.com/doi/full/10.1080/19475683.2016.1144649) |
| 2 | **2017-08-15** | Koramangala, HSR Layout, Shantinagar, Wilson Garden, KR Puram | Severe | HAL: 144mm, City: 129mm in 24h | HIGH | [Scroll.in](https://scroll.in/latest/847311/in-photos-overnight-rain-wreaks-havoc-in-bengaluru-inundates-several-parts-of-the-city) |
| 3 | **2018-08-14** | Karnataka-wide including Bengaluru | Severe (state-level) | Severe flooding and landslides | MEDIUM | [FloodList](https://floodlist.com/asia/india-floods-landslides-karnataka-august-2018) |
| 4 | **2019-08-08** | Statewide (peak of Aug 1-14 event) | Severe | 658mm cumulative Aug 1-14. 40+ dead, 400K displaced | MEDIUM | [FloodList](https://floodlist.com/asia/india-floods-karnataka-august-2019) |
| 5 | **2019-10-19** | Karnataka-wide including Bengaluru | Moderate | 140mm/24h at some gauges | MEDIUM | [FloodList](https://floodlist.com/asia/india-karnataka-floods-october-2019) |
| 6 | **2020-10-23** | Koramangala (96mm), HSR Layout, Bommanahalli, Ejipura | Severe | 80mm+ in 24h. 700 houses damaged, NDRF deployed | HIGH | [FloodList](https://floodlist.com/asia/india-bangalore-floods-october-2020) |
| 7 | **2021-11-22** | Widespread (lakes overflowed) | Severe | 131.6mm in 12h. Knee-to-waist-deep water | HIGH | [Phys.org](https://phys.org/news/2021-11-india-bangalore-heavy.html) |
| 8 | **2022-06-18** | Widespread (monsoon onset) | Moderate | 951% excess rainfall week of Jun 16-22 | LOW | [Down to Earth](https://www.downtoearth.org.in/climate-change/multiple-troughs-la-nina-why-bengaluru-is-flooding-repeatedly-this-monsoon-84742) |
| 9 | **2022-08-29** | ORR, Mahadevapura, Bellandur, SE Bangalore | Severe | City underwater for 2 days. Aug total: 370mm | HIGH | [ORF](https://www.orfonline.org/expert-speak/the-bengaluru-floods); [Sigma Earth](https://sigmaearth.com/the-bangalore-floods-of-2022/) |
| 10 | **2022-08-30** | ORR (massive flooding, thousands stranded) | Severe | Continuation of Aug 29 event | HIGH | [ORF](https://www.orfonline.org/expert-speak/the-bengaluru-floods) |
| 11 | **2022-09-04** | Bellandur, Sarjapur Road, Whitefield, ORR, BEML Layout | Severe | 131.6mm in 24h (highest Sep daily since 2014) | HIGH | [India.com](https://www.india.com/karnataka/bengaluru-rain-live-updates-bellandur-sarjapura-road-whitefield-outer-ring-road-and-beml-flooded-check-latest-rain-photos-videos-bangalore-rain-5601313/) |
| 12 | **2024-08-12** | KR Market, Jakkur underpass, ORR (Nagawara-Hebbal), Yelahanka | Severe | Doddabommasandra Lake overflowed, 6ft flooding | HIGH | [The South First](https://thesouthfirst.com/karnataka/overnight-rains-cause-widespread-waterlogging-in-bengaluru-traffic-advisory-issued/) |
| 13 | **2024-09-19** | Low-lying areas citywide | Moderate | Heavy overnight rain, widespread waterlogging | MEDIUM | [National Herald](https://www.nationalheraldindia.com/amp/story/national/overnight-rain-leaves-bengaluru-waterlogged-imd-predicts-more-showers) |
| 14 | **2024-10-21** | Yelahanka, Kodigehalli, Kendriya Vihar, Bellandur, Manyata Tech Park | Severe | Start of 3-day event | HIGH | [Deccan Herald](https://www.deccanherald.com/india/karnataka/bengaluru/bengaluru-rains-live-updates-traffic-jam-death-toll-karnataka-flood-bangalore-rain-news-imd-weather-waterlogging-imd-3548824) |
| 15 | **2024-10-22** | Same as above (peak) | Severe | 157mm in 6h at Yelahanka. 5-7 dead, 1000+ homes flooded | HIGH | [The Watchers](https://watchers.news/2024/10/22/5-reported-dead-after-widespread-floods-hit-bengaluru-india/) |
| 16 | **2025-05-18** | Koramangala, Indiranagar, Silk Board, HSR Layout, BTM Layout, Electronic City | Severe | 130mm in 12h (pre-monsoon). 3 dead, 500+ homes flooded | HIGH | [The Watchers](https://watchers.news/2025/05/21/bengaluru-flooding-three-dead-500-homes-damaged/) |

**Unique dates: 16** (deduplicating multi-day events to first day = ~13 independent storm systems)
**Tier: Constrained XGBoost viable (15+ dates)**

Note: 2022 was Bengaluru's wettest year in 122 years (1,957mm). 2017 was wettest in 127 years (1,696mm).

---

## 3. Yogyakarta — 34 Events (all post-2017)

### Source: `34 latest floods in Yogyakarta.md` (project file, compiled from Indonesian news)

All events have verified news sources (detikJogja, Kompas, ANTARA News, CNN Indonesia).

| # | Date (approx) | Location | Severity | News Source | Confidence |
|---|---------------|----------|----------|-------------|------------|
| 1 | **2026-03** | Cawas-Gunungkidul Highway | Severe (1m deep, road cut off) | [detikJateng](https://www.detik.com/jateng/berita/d-8383134/banjir-parah-terjang-jalan-raya-klaten-gunungkidul-di-cawas-imbas-tanggul-jebol) | MEDIUM |
| 2 | **2026-02-25** | Kokap + Sentolo, Kulon Progo | Moderate (landslides, sinkholes) | [Kompas](https://yogyakarta.kompas.com/read/2026/02/25/165941678/hujan-deras-kulon-progo-tanah-ambles-di-kalibawang-muncul-lagi) | HIGH |
| 3 | **2025-11-10** | Yogyakarta City (emergency declaration) | City-wide emergency status | [Kompas](https://yogyakarta.kompas.com/read/2025/11/10/170805578/masuk-musim-hujan-yogyakarta-tetapkan-siaga-darurat-banjir-talud-longsor) | HIGH |
| 4 | **2025-08** | Jl. Menteri Supeno, Umbulharjo | Moderate (street flooding) | [detikJogja](https://www.detik.com/tag/banjir-di-jogja) | LOW |
| 5 | **2025-05** | Kasihan, Bantul | Moderate (BPBD deployed) | [ANTARA](https://jogja.antaranews.com/berita/745793/bpbd-hujan-menyebabkan-banjir-di-bantul) | LOW |
| 6 | **2025-03** | Bumi Progo Sejahtera, Kulon Progo | Severe (flash flood, house destroyed, hundreds evacuated) | [detikJogja](https://www.detik.com/jogja/berita/d-7846876/banjir-bandang-terjang-perumahan-di-kulon-progo-1-rumah-ambruk) | MEDIUM |
| 7 | **2025-03-29** | 19 locations in Kulon Progo | Severe (simultaneous flash floods + landslides) | [Kompas](https://yogyakarta.kompas.com/read/2025/03/29/143540978/banjir-dan-tanah-longsor-terjang-kulon-progo-19-lokasi-terdampak-mana) | HIGH |
| 8 | **2025-03** | Imogiri + Wukirsari, Bantul | Severe (60cm in homes, police stations flooded) | [detikJogja](https://www.detik.com/jogja/berita/d-7846597/banjir-di-sejumlah-wilayah-bantul-dan-gunungkidul-hingga-15-orang-terjebak) | MEDIUM |
| 9 | **2025-03-30** | Umbulharjo + Wirobrajan, Yogyakarta City | Moderate (urban flooding, roads cut off) | [CNN Indonesia](https://www.cnnindonesia.com/nasional/20250330130928-20-1214578/fakta-banjir-dan-longsor-di-yogyakarta-rendam-4-wilayah) | HIGH |
| 10 | **2025-03** | Wonosari, Playen, Semanu, Gunungkidul | Severe (15 people trapped, 70+ homes submerged) | [detikJogja](https://www.detik.com/jogja/berita/d-7846597/banjir-di-sejumlah-wilayah-bantul-dan-gunungkidul-hingga-15-orang-terjebak) | MEDIUM |
| 11 | **2024-12** | Lendah, Kulon Progo | Moderate (school flooded) | [detikJogja](https://www.detik.com/jogja/berita/d-7686275/rumah-sd-di-lendah-kulon-progo-terendam-banjir) | LOW |
| 12 | **2024-12** | Underpass Kulur, Kulon Progo | Severe (2m deep, closed to traffic) | [detikJogja](https://www.detik.com/jogja/berita/d-7674245/underpass-kulur-kulon-progo-ditutup-gegara-kerap-banjir-selama-musim-hujan) | LOW |
| 13 | **2024-11** | Underpass Kentungan, Sleman | Moderate (recurring waterlogging) | [detikJogja](https://www.detik.com/tag/banjir-di-jogja) | LOW |
| 14 | **2023-05** | Dongkelan, Bantul | Moderate (50 houses flooded) | [detikJateng](https://www.detik.com/jateng/jogja/d-6698636/hujan-deras-50-rumah-di-dongkelan-bantul-tergenang-banjir) | LOW |
| 15 | **2023-05** | Underpass Kentungan + Pasar Pasty, Sleman | Moderate (4 flood points) | [detikJateng](https://www.detik.com/tag/banjir-di-jogja) | LOW |
| 16 | **2023-01-26** | 3 schools in Kulon Progo | Moderate (schools closed) | [Kompas](https://yogyakarta.kompas.com/read/2023/01/26/202837878/terdampak-banjir-3-sekolah-di-kulon-progo-diliburkan) | HIGH |
| 17 | **2022-12-05** | Jalan Nasional to YIA Airport, Kulon Progo | Moderate (road flooded, traffic jammed) | [Kompas](https://yogyakarta.kompas.com/read/2022/12/05/225458478/banjir-di-jalan-nasional-menuju-bandara-yia-kendaraan-memadat-dan-sempat) | HIGH |
| 18 | **2022-12** | 7 sub-districts, Kulon Progo | Severe (rivers overflowed, national road submerged) | [ANTARA](https://www.antaranews.com/berita/3287495/tujuh-kecamatan-di-kulon-progo-tergenang-banjir-akibat-hujan-deras) | LOW |
| 19 | **2022-11** | Gondokusuman, Yogyakarta City | Moderate (residential flooding) | [detikJateng](https://www.detik.com/tag/banjir-di-jogja) | LOW |
| 20 | **2022-10-13** | Agricultural areas, Kulon Progo | Severe (dozens of hectares destroyed, homes flooded) | [Kompas](https://yogyakarta.kompas.com/read/2022/10/13/230508878/banjir-di-kulon-progo-puluhan-rumah-terendam-20-hektar-tanaman-palawija) | HIGH |
| 21 | **2022-05** | Dusun Plampang II, Kulon Progo | Severe (flash flood, viral video) | [detikJateng](https://www.detik.com/jateng/jogja/d-6085833/viral-video-banjir-bandang-terjang-kulon-progo-begini-faktanya) | LOW |
| 22 | **2021-12** | Sleman (cold lava flood from Merapi) | Severe (emergency status, water networks destroyed) | [ANTARA](https://www.antaranews.com/berita/2564553/sleman-tetapkan-status-tanggap-darurat-banjir-lahar-dingin-merapi) | LOW |
| 23 | **2021-11** | Pelabuhan Sadeng + Ngawen, Gunungkidul | Severe (1m deep, landslides) | [detikNews](https://news.detik.com/berita-jawa-tengah/d-5807055/kondisi-dan-data-terkini-longsor-banjir-di-gunungkidul) | LOW |
| 24 | **2021-01-31** | Girisubo, Gunungkidul | Severe (bridge destroyed, homes flooded) | [Kompas](https://regional.kompas.com/read/2021/01/31/13444301/banjir-di-gunungkidul-putus-jembatan-warga-harus-memutar-ke-jateng) | HIGH |
| 25 | **2020-03-08** | Nglindur Kulon, Gunungkidul | Moderate (lake overflow, homes flooded) | [Kompas](https://regional.kompas.com/read/2020/03/08/23515521/diguyur-hujan-deras-puluhan-rumah-di-gunungkidul-terendam-banjir) | HIGH |
| 26 | **2020-03** | Kali Doso + Perengan rivers, Sleman | Moderate (intersections flooded 50cm) | [detikNews](https://www.detik.com/tag/banjir-di-sleman) | LOW |
| 27 | **2020-02-22** | Sempor River, Sleman | Severe (flash flood during school trip, fatalities) | [Kompas](https://regional.kompas.com/read/2020/02/22/07281041/detik-detik-banjir-bandang-sapu-siswa-peserta-susur-sungai-di-sleman) | HIGH |
| 28 | **2019-03-18** | Imogiri, Bantul | Severe (5 fatalities, 4000 evacuees) | [detikNews](https://news.detik.com/berita-jawa-tengah/d-4476423/dampak-banjir-dan-longsor-bantul-5-orang-meninggal-dunia) | HIGH |
| 29 | **2019-03-18** | Purwosari + Semanu, Gunungkidul | Severe (2m deep, 13 sub-districts) | [Kompas](https://regional.kompas.com/read/2019/03/18/00475191/banjir-di-gunungkidul-terjang-sekolah-dan-permukiman) | HIGH |
| 30 | **2019-03-18** | Pantai Baron, Gunungkidul | Severe (underground river overflow) | [Kompas](https://regional.kompas.com/read/2019/03/18/16491391/6-fakta-banjir-dan-longsor-di-diy-bantul-paling-parah-hingga-terjang) | HIGH |
| 31 | **2019-03** | Serang River embankment, Kulon Progo | Severe (580 displaced) | [detikNews](https://www.detik.com/tag/banjir-kulon-progo) | MEDIUM |
| 32 | **2019-03-06** | Gedangsari, Gunungkidul | Severe (school flooded, bridge severed) | [Kompas](https://regional.kompas.com/read/2019/03/06/22590481/banjir-dan-tanah-longsor-terjang-gunungkidul-belasan-orang-mengungsi) | HIGH |
| 33 | **2017-11** | Bantul + Gunungkidul (Opak/Winongo rivers) | Severe (1m deep, settlements + rice fields) | [detikNews](https://news.detik.com/foto-news/d-3747846/terdampak-cuaca-ekstrem-ini-potret-banjir-dan-longsor-di-yogya) | LOW |
| 34 | **2017-11** | Gunungkidul (Cyclone Cempaka) | Severe (districts isolated, valleys became lakes) | [detikNews](https://news.detik.com/foto-news/d-3747846/terdampak-cuaca-ekstrem-ini-potret-banjir-dan-longsor-di-yogya) | LOW |

**Unique dates (HIGH/MEDIUM confidence): ~18 independent storm systems**
**Tier: Constrained XGBoost viable (15+)**

Note: Many March 2019 events (28-32) are from the same storm system. Similarly, March 2025 events (6-10) share a weather pattern. For temporal analysis, these count as ~2 unique temporal observations, not 5 each.

**Effective unique temporal observations: ~15-18** (accounting for same-storm clustering)

---

## 4. Singapore — 8 Post-2014 Events

### Sources: Web search (FloodList, Mothership.sg, The Watchers, PUB, Singapore-Flood-Data-Sources.md project file)

| # | Date | Areas Affected | Severity | Rainfall | Confidence | Source |
|---|------|---------------|----------|----------|------------|--------|
| 1 | **2021-04-17** | Ulu Pandan, Bukit Timah, Jurong East, Dunearn Road | Severe | 161.4mm in 3h (heaviest April in 40 years, top 0.5% of all daily records since 1981) | HIGH | [FloodList](https://floodlist.com/asia/singapore-flash-floods-april-2021); [The Watchers](https://watchers.news/2021/04/19/heaviest-rainfall-in-40-years-triggers-flash-flooding-in-singapore/); [Mothership.sg](https://mothership.sg/2021/04/singapore-floods-april-17/) |
| 2 | **2023-11-28** | Boon Lay Way, Jurong | Moderate | Flash flood, subsided within 20 min | MEDIUM | [Mothership.sg](https://mothership.sg/2023/11/heavy-rain-jurong-flash-floods/) |
| 3 | **2024-11-22** | Multiple locations (19 warnings) | Moderate | Northeast Monsoon flash floods | MEDIUM | [Mothership.sg](https://mothership.sg/2024/11/flash-floods-monsoon-warnings-pub/) |
| 4 | **2024-12-29** | Bukit Timah Road, Dunearn Road, King Albert Park | Moderate | 134-140mm (~40% of December average). Subsided <1 hour | HIGH | Singapore-Flood-Data-Sources project file |
| 5 | **2025-02-15** | Jurong West, Pioneer, Jurong East, Katong | Moderate | Chinese New Year flash flood warnings | MEDIUM | [Mothership.sg](https://mothership.sg/2025/02/pub-feb-15-flash-flood-warnings/) |
| 6 | **2025-04-20** | Kings Road, Bukit Timah Road, Coronation Walk, Stevens/Balmoral | Moderate | Flash floods in 4 areas (5-6 PM) | HIGH | [Mothership.sg](https://mothership.sg/2025/04/flash-flood-singapore-heavy-rain/) |
| 7 | **2025-12-04** | Pandan Road, Boon Lay Ave, Boon Lay Way/Corporation Rd, Pesawat Drive | Moderate | 113mm (~36% of December average). 8 areas affected, subsided in 30 min | HIGH | Singapore-Flood-Data-Sources project file |
| 8 | **2026-02** | Jurong West, Pioneer, Jurong East, Katong | Moderate | PUB flash flood warnings during Chinese New Year | LOW | Singapore-Flood-Data-Sources project file |

#### Pre-2014 Major Events (not usable for SAR, but useful context)

| Year | Event | Deaths | Source |
|------|-------|--------|--------|
| 1954 | Two major episodes (Oct + Dec) | 5 | Lin et al. 2021; BiblioAsia |
| 1969 | "Great Flood" — 75% of Singapore submerged | 5 | Lin et al. 2021; Aon deck |
| 1978 | Dec 2-3: 512.4mm in 24h (all-time record) | 7-9 | Lin et al. 2021; Straits Times |
| 2010-06 | Orchard Road flash flood | 0 | PUB Expert Panel Report |
| 2011-06 | Orchard Road repeat flooding | 0 | PUB Expert Panel Report |

**Post-2014 unique dates: 8**
**Tier: Mixed-effects model (8-14 dates)**

Note: Singapore flash floods are characteristically short-lived (typically 20-60 minutes), localized, and non-fatal post-2000. This rapid subsidence may make SAR temporal analysis challenging — Sentinel-1 overpasses may miss the flood window entirely.

---

## 5. Indore — 15 Events (all post-2014)

### Sources: Web search (Free Press Journal, Knocksense, FloodList, Skymet, ANI, NDTV, Ground Report, ReliefWeb)

| # | Date | Areas Affected | Severity | Rainfall | Confidence | Source |
|---|------|---------------|----------|----------|------------|--------|
| 1 | **2014-07-23** | MP-wide including Indore region | Moderate | Regional monsoon. 1 dead, 2000 displaced in MP | MEDIUM | [FloodList](https://floodlist.com/asia/july-2014-madhya-pradesh-floods) |
| 2 | **2014-09-08** | Indore district | Moderate | 9cm+ rainfall | MEDIUM | [ReliefWeb](https://reliefweb.int/report/india/southwest-monsoon-2014-daily-flood-situation-report-summary-important-events-08092014) |
| 3 | **2018-07-22** | Western MP: Indore, Bhopal, Devas, Ujjain | Moderate-Severe | Low-pressure from Bay of Bengal | MEDIUM | [Skymet](https://www.skymetweather.com/content/weather-news-and-analysis/heavy-monsoon-rain-in-madhya-pradesh-to-return-floods-to-worsen/) |
| 4 | **2019-08-14** | Citywide | Moderate | Sustained 48h+ rain | MEDIUM | [Skymet](https://www.skymetweather.com/content/weather-news-and-analysis/rain-lashes-indore-activity-to-persist-for-another-48-hours/) |
| 5 | **2019-08-25** | Citywide | Moderate | Heavy rain 24h, flood-like situation | MEDIUM | [Skymet](https://www.skymetweather.com/content/weather-news-and-analysis/heavy-rains-to-lash-indore-for-next-24-hrs-water-logging-traffic-chaos-flood-like-situation-expected/) |
| 6 | **2019-09-13** | Western MP including Indore | Moderate | Extended heavy rain through Sep 16 | MEDIUM | [Skymet](https://www.skymetweather.com/content/weather-news-and-analysis/heavy-rain-lashes-indore-again-showers-to-continue/) |
| 7 | **2020-08-23** | Pardeshipura, Bangana, Sikandarabad Colony (worst). Citywide | Severe | **263.4mm in 24h** (broke 39-year record of 212.6mm from 1981). 10,000 affected, 2,500 rescued, 100+ trees uprooted | HIGH | [Knocksense](https://www.knocksense.com/indore/indore-news/record-high-in-39-years-heavy-rains-flood-the-city-of-indore); [FloodList](https://floodlist.com/asia/india-floods-uttar-pradesh-madhya-pradesh-august-2020) |
| 8 | **2022-08-09** | Dwarkapuri, Annapurna, Rajendra Nagar, Vaishali Nagar, Prajapat Nagar | Severe | Seasonal total crossed 26 inches. Cars swept away | HIGH | [Knocksense](https://www.knocksense.com/indore/rainfall-in-indore-crosses-26-inches-mark-causes-waterlogging-traffic-snarls-in-the-city); [Free Press Journal](https://www.freepressjournal.in/indore/indore-heavy-rain-throws-life-out-of-gear) |
| 9 | **2023-09-15** | Luv Kush Square, Chhawani, Krishnapura Chhatri, Juni Indore, Sanwer, Rau | Severe | **10 inches in ~30h**. IMD Red Alert. 89 rescue ops, 8,718 rescued, 2,637 livestock rescued. Schools closed, slums evacuated | HIGH | [ANI](https://www.aninews.in/news/national/general-news/mp-heavy-rain-leads-to-waterlogging-in-indore-rescue-operations-on20230916180701/); [Free Press Journal](https://www.freepressjournal.in/indore/indore-rains-incessant-downpour-since-24-hours-leaves-residential-areas-waterlogged-slums-evacuated-check-helpline-numbers) |
| 10 | **2023-09-17** | Western MP including Indore | Severe | IMD Red Alert continuation | MEDIUM | [Ganga News Today](https://today.ganganews.com/india/red-alert-issued-for-extremely-heavy-rainfall-in-indore/) |
| 11 | **2024-08-24** | Citywide. Kairwa Dam + Yashwant Sagar gates opened | Severe | 3 inches in 9h. Orange alert for 26 districts | HIGH | [NDTV on X](https://x.com/ndtv/status/1827065724877062616) |
| 12 | **2025-05-05** | Citywide (70% power outage) | Moderate | Pre-monsoon cyclonic storm. 400/426 feeders shut down | HIGH | [Ground Report](https://groundreport.in/latest/indore-rainstorm-exposes-gaps-in-smart-city-planning-9036010) |
| 13 | **2025-08-29** | Super Corridor (2km), Gandhi Nagar Metro Depot | Moderate | 2-2.5 ft water on Super Corridor. Metro debris blocked drainage | HIGH | [Free Press Journal](https://www.freepressjournal.in/indore/indore-metro-debris-blamed-for-super-corridor-flooding) |
| 14 | **2025-08-31** | Roads citywide, low-lying areas | Severe | Roads became rivers. Ganesh idol + car washed away | HIGH | [ETV Bharat](https://www.etvbharat.com/hi/!state/indore-heavy-rain-waterlogging-roads-flood-water-entered-houses-ganesh-idol-car-washed-away-madhya-pradesh-news-mps25083100441) |
| 15 | **2025-09-05** | Ban Ganga, Gangaur Ghat | Moderate | 7 inches in first 4 days of September (exceeded monthly average of 6 inches) | HIGH | [Free Press Journal](https://www.freepressjournal.in/indore/watch-heavy-rains-turn-indore-roads-into-rivers-netizens-flood-internet-with-reels) |

**Unique dates: 15** (deduplicating Sep 2023 to one event = ~13 independent storm systems)
**Tier: Mixed-effects model (8-14) to Constrained XGBoost (15+)**

---

## Summary: Event Date Availability by City

| City | Total Events | Post-2014 (Sentinel-1 era) | HIGH confidence dates | Effective independent storms | Part B Scope |
|------|-------------|---------------------------|----------------------|------------------------------|-------------|
| **Delhi** | 45 | 6 | 6 | 6 | Part A only (too few post-2014) |
| **Bangalore** | 16 | 16 | 12 | ~13 | **Part B primary** |
| **Yogyakarta** | 34 | 34 | ~15 | ~15-18 | **Part B primary** |
| **Singapore** | 8 | 8 | 5 | 8 | Part A only (floods too brief for SAR) |
| **Indore** | 15 | 15 | 10 | ~13 | Part B stretch goal |

### Key Observations

1. **Delhi paradox**: Most historical data (45 events) but fewest in Sentinel-1 era (6). IFI-Impacts dataset ends at 2023; web search found 2 more for 2024. Could search for 2025 monsoon events to add more.

2. **Bangalore is strongest candidate**: 16 events with excellent source quality (FloodList, Deccan Herald). 2022 alone provides 3 major events. Good geographic specificity (Bellandur, ORR, Yelahanka corridors).

3. **Yogyakarta has most events but date precision varies**: Many events only have month-level dates (LOW confidence). The 15 HIGH/MEDIUM confidence dates are sufficient. Same-storm clustering (March 2019, March 2025) reduces effective sample size.

4. **Singapore floods are too short for SAR**: Typical 20-60 minute subsidence. Sentinel-1 has 6-12 day revisit time. SAR temporal analysis may not capture these events. Consider using only static features for Singapore.

5. **Indore has good recent coverage**: 2020 record-breaking event (263.4mm) and 2023 rescue event (8,718 rescued) are well-documented anchor points.

### Revised Scope Decision (2026-03-07)

**Part B requires SAR** — without it, temporal features (precipitation, soil moisture) just confirm "it floods when it rains" (circular). SAR captures actual surface water presence, the only non-tautological temporal feature.

**Part B runs for Bangalore + Yogyakarta only** (strongest post-2014 date coverage + SAR viability). Indore is a stretch goal. Delhi and Singapore are Part A only.

**Singapore deferred to independent study** using PUB's 208 water level sensors, which provide ground-truth temporal data far richer than SAR. Different methodology, separate design doc.

### Recommendations for Next Steps

1. **Begin GEE feature extraction trial** (Phase 0) with Bangalore first (strongest data, 16 events)
2. **Pin exact dates for LOW-confidence Yogyakarta events** by checking Indonesian news archives
3. **Define "dry reference dates"** for Part B cities: same month, no rain events in 7-day window
4. **Check Sentinel-1 availability** on GEE for anchor dates (Bangalore 2022-09-04, Yogyakarta 2019-03-18)
5. **Future: Singapore PUB study** — design separate methodology using water level sensor data

---

## Data Quality Notes

### What "verified" means in this document
- **HIGH confidence**: Exact date from a named news article with URL. Multiple sources confirm.
- **MEDIUM confidence**: Date from a single source, or date inferred from article publication date.
- **LOW confidence**: Month-level only. Article exists but exact flood date not extractable from headline.

### What this document does NOT verify
- Exact rainfall amounts (reported by news, not independently verified against IMD/BMKG/NEA station data)
- Exact affected locations (news reports may exaggerate or omit areas)
- Whether Sentinel-1 imagery actually captured these events (requires GEE availability check)

### Sources used
- **IFI-Impacts database**: India Flood Inventory (academic dataset in project files)
- **FloodList.com**: International flood reporting aggregator (reliable, cited in academic papers)
- **Indonesian news**: detikJogja, Kompas, ANTARA, CNN Indonesia (reputable national outlets)
- **Indian news**: Deccan Herald, Times of India, NDTV, Free Press Journal, Knocksense (local Indore outlet)
- **Singapore**: Mothership.sg, PUB official, The Watchers, FloodList
- **Weather services**: Skymet, IMD, BMKG (official meteorological agencies)
- **Academic**: Lin et al. 2021, Chow et al. 2016, Tandfonline vulnerability assessment
