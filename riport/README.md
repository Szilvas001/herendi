# Vatera – Herendi & Zsolnay deal riport

Készült: 2026-09-17 14:35 · forrás: vatera.hu élő scrape (`python run.py --no-ai`), elemzés: Claude (Claude Code munkamenetben)

## Fájlok ebben a mappában

| Fájl | Tartalom | db |
|---|---|---:|
| [README.md](README.md) | összefoglaló + Claude válogatás (áron aluli / nyugati piac) | 45 |
| [aukcio.md](aukcio.md) | az összes aukció (licit) hirdetés, linkkel | 206 |
| [fix-aras.md](fix-aras.md) | az összes fix áras hirdetés, linkkel | 1640 |
| [alkukepes.md](alkukepes.md) | az összes alkuképes / irányáras hirdetés, linkkel | 475 |
| [kiszurt.md](kiszurt.md) | kiszűrt hirdetések (utánzat, nem porcelán…) okkal | 31 |

## Összefoglaló

Márka szerint: Herendi: 1361, Zsolnay: 960

A 2026-09-16-i élő scrape 2321 elfogadott Herendi és Zsolnay hirdetést talált: 206 aukciót, 1640 fix áras és 475 alkuképes tételt. A kínálat nagy része néhány nagy kereskedőtől jön, akik bolti árhoz közeli áron dolgoznak, így valódi áron aluli tétel kevés van. A legjobb lehetőségek a hibátlan, nagyméretű herendi figurák (sas, szajkó, foxi), a teljes méretű herendi levesestálak (Rothschild, Victoria, Apponyi Orange), az egy eladónál 20–25 ezer forintért kapható, első osztályú, jelzett Apponyi vázák, valamint néhány antik Zsolnay eozin darab (kacsás-békás tál, 1930-as eozin vázák, birkózó medvék). A nyugati továbbértékesítésnél a szállítás a fő kockázat: a nagy vázák és levesestálak törékenyek és nehezek.

## Likvid, nagy árrésű tételek nyugati eladásra – összesített táblázat

A Herendi és Zsolnay tételek mellett a Vaterán jellemző, nyugaton gyorsan forgó termékeket is átvizsgáltam: Tungsram elektroncsöveket, szovjet, NDK és japán objektíveket (Helios, Jupiter, Carl Zeiss Jena, Meyer-Optik, Takumar, Nikkor), filmes fényképezőgépeket (Rolleiflex, Contax, Olympus, Canon, Nikon, Pentax, Yashica, Lomo, Kiev, Zenit), órákat (Poljot 3133 változatok, Vostok, Raketa, Seiko, Junghans), retró elektronikát (Walkman, Game Boy, Nintendo, Sega, Commodore, Amiga, Atari), töltőtollakat (Pelikan, Parker) és Carl Zeiss Jena távcsöveket, 101 keresőszóval. A 3009 elfogadott hirdetésből 7 felelt meg minden feltételnek. A táblázatban ezek és a korábbi ajánlott Herendi/Zsolnay tételek szerepelnek, **a kezdő áron becsült eladási idő szerint rendezve, a leggyorsabbal kezdve**.

**Kiválasztási feltételek (új tételek):** csak fix áras vagy alkuképes hirdetés, mert az aukciós ár még emelkedhet. Legalább 10 hasonló aktív eBay-hirdetés, vagyis van piac. A legkisebb elfogadható ár legfeljebb a piaci medián. A nettó haszon a medián áron legalább 60% és legalább 40 USD. A **kezdő hirdetési ár** a hasonló aktív eBay-hirdetések mediánja. Az **eladási idő ezen az áron** a piac mélységétől függ: 30 vagy több aktív hirdetésnél 2–6 hét, 15–29-nél 3–8 hét, 8–14-nél 1–3 hónap. A **legkisebb elfogadható ár** és a hozzá tartozó likviditás ugyanazzal a szabállyal készült, mint a Herendi/Zsolnay tételeknél (lásd lent, „Módszer”). A **nettó haszon** a kezdő áron számolt eladási ár a piactéri díj levonása után, mínusz a Vatera-ár. A szállítást a vevő fizeti, a vámot és a Vaterán belüli postaköltséget nem vontam le. Csöveknél, ha a hirdetés több darabot tartalmaz, az eBay-összehasonlítás darabárra készült.

*Kiszűrve:* 1821 hirdetésnél nem volt felismerhető modell, 7-nél kevés az eBay-összehasonlító hirdetés, 73-nél a fedezet a piaci medián felett van, 59-nél kicsi az árrés, és 769 aukciós vagy ár nélküli.

| Tétel | Kategória | Vatera ár | Kezdő hirdetési ár · piactér | Becsült eladási idő ezen az áron | Likviditás ezen az áron | Legkisebb elfogadható ár | Eladási idő és likviditás a legkisebb áron | Becsült nettó haszon a kezdő áron | Aktív eBay-kínálat (db, medián, alsó–felső negyed) | Értékelés |
|---|---|---:|---:|---|---|---:|---|---:|---|---|
| [Herendi Rothschild Új 6 sz étkészlet](https://www.vatera.hu/herendi-rothschild-uj-6-sz-etkeszlet-3491251307.html) | Herendi porcelán | 899 000 Ft (≈ 2 276 EUR) | 4 500 EUR · Catawiki | 2–4 hét | közepes | 2 900 EUR | 2–4 hét, közepes–magas | 1 662 EUR (73%) | nincs összehasonlítható | **Ajánlott** |
| [2db ECC83 Tungsram. Legolcsóbb](https://www.vatera.hu/2db-ecc83-tungsram-legolcsobb-3530289641.html) (2 db) | Tungsram cső · Tungsram ECC83 | 8 500 Ft (≈ 25 USD) | 130 USD · eBay.com | 2–6 hét | magas | 40 USD | 1–4 hét, magas | 82 USD (333%) | 37 db, medián 63 USD (45–100) / darab | **Ajánlott** |
| [Carl Zeiss Jena DDR - Tessar f2,8/50 - M42](https://www.vatera.hu/carl-zeiss-jena-ddr-tessar-f2-8-50-m42-3450444290.html) | Objektív · Tessar 50 | 8 000 Ft (≈ 23 USD) | 100 USD · eBay.com | 2–6 hét | magas | 35 USD | 1–4 hét, magas | 59 USD (254%) | 64 db, medián 97 USD (65–140) | **Ajánlott** |
| [Zenit TTL Helios 44M 2/58 lencsével](https://www.vatera.hu/zenit-ttl-helios-44m-2-58-lencsevel-3523993349.html) | Fényképezőgép · Zenit TTL | 8 990 Ft (≈ 26 USD) | 80 USD · eBay.com | 2–6 hét | magas | 35 USD | 1–4 hét, magas | 41 USD (158%) | 80 db, medián 79 USD (52–125) | **Ajánlott** |
| [SEGA MASTER SYSTEM II](https://www.vatera.hu/sega-master-system-ii-3508181165.html) | Retró elektronika · Sega Master System | 25 000 Ft (≈ 73 USD) | 175 USD · eBay.com | 2–6 hét | magas | 95 USD | 3–8 hét, közepes–magas | 76 USD (104%) | 73 db, medián 175 USD (90–285) | **Ajánlott** |
| [Szovjet nagyon szép NOS Poljot Chronograph Mechanikus karóra](https://www.vatera.hu/szovjet-nagyon-szep-nos-poljot-chronograph-mechanikus-karora-3529930949.html) | Szovjet óra · Poljot Chronograph | 60 000 Ft (≈ 175 USD) | 340 USD · eBay.com | 2–6 hét | magas | 230 USD | 3–8 hét, közepes–magas | 109 USD (63%) | 70 db, medián 334 USD (102–470) | **Ajánlott** |
| [Szovjet nagyon szép NOS Poljot Chronograph Mechanikus karóra](https://www.vatera.hu/szovjet-nagyon-szep-nos-poljot-chronograph-mechanikus-karora-3529931729.html) | Szovjet óra · Poljot Chronograph | 60 000 Ft (≈ 175 USD) | 340 USD · eBay.com | 2–6 hét | magas | 230 USD | 3–8 hét, közepes–magas | 109 USD (63%) | 70 db, medián 334 USD (102–470) | **Ajánlott** |
| [Szovjet nagyon szép NOS Poljot Chronograph Mechanikus karóra](https://www.vatera.hu/szovjet-nagyon-szep-nos-poljot-chronograph-mechanikus-karora-3529929749.html) | Szovjet óra · Poljot Chronograph | 60 000 Ft (≈ 175 USD) | 340 USD · eBay.com | 2–6 hét | magas | 230 USD | 3–8 hét, közepes–magas | 109 USD (63%) | 70 db, medián 334 USD (102–470) | **Ajánlott** |
| [Zsolnay porcelán szecessziós névjegytál - Zsolnay eozinmázas rákos tál](https://www.vatera.hu/zsolnay-porcelan-szecesszios-nevjegytal-zsolnay-eozinmazas-rakos-tal-3483997382.html) | Zsolnay porcelán | 32 000 Ft (≈ 81 EUR) | 240 EUR · eBay.de | 3–8 hét | közepes–magas | 105 EUR | 1–4 hét, magas | 128 EUR (158%) | 16 db, medián 244 EUR (175–346) | **Ajánlott** |
| [Herendi Rothschild ovális citromfogós levesestál](https://www.vatera.hu/herendi-rothschild-ovalis-citromfogos-levesestal-3528644864.html) | Herendi porcelán | 170 000 Ft (≈ 495 USD) | 950 USD · eBay.com | 3–8 hét | közepes–magas | 650 USD | 1–4 hét, magas | 312 USD (63%) | 38 db, medián 952 USD (750–1250) | **Ajánlott** |
| [Nagyobb méretű ( 18 cm magas) herendi madár figura / hibátlan](https://www.vatera.hu/nagyobb-meretu-18-cm-magas-herendi-madar-figura-hibatlan-3464572610.html) | Herendi porcelán | 22 800 Ft (≈ 66 USD) | 160 USD · Etsy | 3–8 hét | közepes–magas | 85 USD | 2–6 hét, magas | 75 USD (114%) | 24 db, medián 160 USD (82–250) | **Ajánlott** |
| [1Z997 Régi nagyméretű Herendi porcelán foxi kutya foxterrier figura](https://www.vatera.hu/1z997-regi-nagymeretu-herendi-porcelan-foxi-kutya-foxterrier-figura-3501768152.html) | Herendi porcelán | 85 000 Ft (≈ 247 USD) | 450 USD · eBay.com | 1–3 hónap | közepes | 330 USD | 1–4 hét, magas | 136 USD (55%) | 16 db, medián 428 USD (370–585) | **Ajánlott** |
| [Ritka Antik HERENDI VÁZA 1.oszt. Bouquet de saxe (BS) KÉZZEL FESTETT HIBÁTLAN, Garancia!!](https://www.vatera.hu/ritka-antik-herendi-vaza-1-oszt-bouquet-de-saxe-bs-kezzel-festett-hibatlan-garancia-3528588389.html) | Herendi porcelán | 24 500 Ft (≈ 71 USD) | 170 USD · Etsy | 1–3 hónap | közepes | 90 USD | 3–8 hét, közepes–magas | 79 USD (111%) | 67 db, medián 154 USD (85–250) | **Ajánlott** |
| [Antik HERENDI 1. oszt. APPONYI VERT GREEN (AV) mintás kosárfonott VÁZA porcelán HIBÁTLAN, Garancia!](https://www.vatera.hu/antik-herendi-1-oszt-apponyi-vert-green-av-mintas-kosarfonott-vaza-porcelan-hibatlan-garancia-3527536409.html) | Herendi porcelán | 19 500 Ft (≈ 57 USD) | 130 USD · Etsy | 1–3 hónap | közepes | 75 USD | 3–8 hét, közepes–magas | 57 USD (100%) | 66 db, medián 110 USD (48–247) | **Ajánlott** |
| [Antik 1.oszt. HERENDI APPONYI VERT GREEN (AV) MINTÁS VÁZA porcelán HIBÁTLAN, Garancia!](https://www.vatera.hu/antik-1-oszt-herendi-apponyi-vert-green-av-mintas-vaza-porcelan-hibatlan-garancia-3524724029.html) | Herendi porcelán | 24 500 Ft (≈ 71 USD) | 150 USD · Etsy | 1–3 hónap | közepes | 90 USD | 3–8 hét, közepes–magas | 61 USD (86%) | 66 db, medián 110 USD (48–247) | **Ajánlott** |
| [Antik HERENDI APPONYI PURPUR (AP) mintás porcelán VÁZA Hibátlan, Garancia!](https://www.vatera.hu/antik-herendi-apponyi-purpur-ap-mintas-porcelan-vaza-hibatlan-garancia-3524920469.html) | Herendi porcelán | 24 500 Ft (≈ 71 USD) | 150 USD · Etsy | 1–3 hónap | közepes | 90 USD | 3–8 hét, közepes–magas | 61 USD (86%) | 66 db, medián 136 USD (75–245) | **Ajánlott** |
| [Antik HERENDI HADIK HUSZÁR porcelán szobor Garancia HIBÁTLAN!!](https://www.vatera.hu/antik-herendi-hadik-huszar-porcelan-szobor-garancia-hibatlan-3526894709.html) | Herendi porcelán | 39 500 Ft (≈ 115 USD) | 250 USD · eBay.com | 1–3 hónap | közepes | 150 USD | 3–8 hét, közepes–magas | 98 USD (85%) | 34 db, medián 192 USD (129–300) | **Ajánlott** |
| [1L654 Hibátlan 12 személyes Zsolnay Pompadour porcelán süteményes készlet](https://www.vatera.hu/1l654-hibatlan-12-szemelyes-zsolnay-pompadour-porcelan-sutemenyes-keszlet-3487247150.html) | Zsolnay porcelán | 72 000 Ft (≈ 182 EUR) | 380 EUR · eBay.de | 1–3 hónap | közepes | 240 EUR | 3–8 hét, közepes–magas | 149 EUR (82%) | nincs összehasonlítható | **Ajánlott** |
| [Herendi Viktória levesestál](https://www.vatera.hu/herendi-viktoria-levesestal-3528645125.html) | Herendi porcelán | 140 000 Ft (≈ 408 USD) | 750 USD · eBay.com | 1–3 hónap | közepes | 530 USD | 3–8 hét, közepes–magas | 230 USD (56%) | 20 db, medián 735 USD (342–1100) | **Ajánlott** |
| [Herendi Apponyi Orange 12 személyes levesestál](https://www.vatera.hu/herendi-apponyi-orange-12-szemelyes-levesestal-3527661473.html) | Herendi porcelán | 160 000 Ft (≈ 466 USD) | 850 USD · eBay.com | 1–3 hónap | közepes | 610 USD | 3–8 hét, közepes–magas | 256 USD (55%) | 65 db, medián 750 USD (400–1200) | **Ajánlott** |
| [ANTIK ZSOLNAY BÍRKÓZÓ MEDVÉK Markup Béla porcelán szobor garancia, Hibátlan!!](https://www.vatera.hu/antik-zsolnay-birkozo-medvek-markup-bela-porcelan-szobor-garancia-hibatlan-3528589049.html) | Zsolnay porcelán | 32 500 Ft (≈ 82 EUR) | 350 EUR · eBay.de | 2–4 hónap | közepes–alacsony | 105 EUR | 1–4 hét, magas | 222 EUR (271%) | nincs összehasonlítható | **Ajánlott** |
| [Herendi Rothschild madaras, 12 személyes, jubileumi, különleges levesestál](https://www.vatera.hu/herendi-rothschild-madaras-12-szemelyes-jubileumi-kulonleges-levesestal-3526021535.html) | Herendi porcelán | 260 000 Ft (≈ 757 USD) | 1 450 USD · eBay.com | 2–5 hónap | alacsony–közepes | 980 USD | 1–3 hónap, közepes | 476 USD (63%) | 38 db, medián 952 USD (750–1250) | **Ajánlott** |

**Fontos:** a Vatera-hirdetések fotóit és állapotleírását vásárlás előtt egyenként ellenőrizd. Objektíveknél a lencse tisztasága (gomba, pára, karc), óráknál a működés és az eredeti alkatrészek, csöveknél a mért érték határozza meg a tényleges árat. A likviditás az aktív kínálatból becsült érték, lezárt eBay-eladásokat nem lehetett lekérni. Az öt Poljot Chronograph ugyanattól az eladótól, „NOS” (új, használatlan) megjelöléssel szerepel: vásárlás előtt kérj fotót a szerkezetről és a hátlapról, mert sok felújított vagy vegyes alkatrészű példány van forgalomban, ezek jóval kevesebbet érnek. A 100 USD alatti tételeknél (Zenit, Tungsram csövek) az USA-ba küldés költsége a vevő szemében drágítja a tételt: ezeket érdemes eBay.de-n, EU-n belül, vagy több darabot egy csomagban eladni.

## Claude válogatás

A válogatás mind a 2321 hirdetés címe, ára és eladási típusa alapján készült. A kb. 90 legígéretesebb jelöltnél elolvastam a hirdetés saját leírását és a „Termék sajátosságai” adatokat (állapot, jelzés, formaszám, méret), ezekből 45 tétel maradt. Az EUR-sávok a nyugati (eBay US/DE, Etsy, Replacements) reálisan elérhető eladási árát becsülik, kb. 395 Ft/EUR árfolyammal. Ezek szakértői becslések, nem valós idejű piaci adatok. Aukcióknál a kikiáltási árat mutatjuk, az aktuális licitet és a lejáratot vásárlás előtt a linken érdemes ellenőrizni.

Összesen **45** javaslat, eladási típus szerint szétválasztva.

### Aukció (licit) (7 tétel)

#### [Herendi Porcelán Sas (33 cm magas, sorozatszámmal ellátott)](https://www.vatera.hu/herendi-porcelan-sas-33-cm-magas-sorozatszammal-ellatott-3526209827.html)

- **Nyugati piacon jól eladható** · bizalom: **kozepes** · Herendi
- Ár: **100 000 Ft** (kikialtasi ar, 3 licit, vége: 2026.09.26. 00:11) · becsült nyugati ár: **600–1000 EUR**
- Indoklás: Nagyméretű, 33 cm-es herendi sas az 5056-os formaszámmal, hibátlan, jelzett, az 1960-as évekből, a Herendi márkabolt becslésével. A 100 000 Ft-os kikiáltási ár kb. 255 EUR, a nagy herendi madárfigurák nyugaton ennek többszöröséért kelnek el.
- Kockázat: Aukció, a végső ár még emelkedhet. Nagy, törékeny figura, a nemzetközi szállításhoz gondos csomagolás kell.
- Link: <https://www.vatera.hu/herendi-porcelan-sas-33-cm-magas-sorozatszammal-ellatott-3526209827.html>

#### [Herendi kávés , mokkás készlet zöld Nanking mintával , koronás címerrel](https://www.vatera.hu/herendi-kaves-mokkas-keszlet-zold-nanking-mintaval-koronas-cimerrel-3523977383.html)

- **Nyugati piacon jól eladható** · bizalom: **kozepes** · Herendi
- Ár: **80 000 Ft** (kikialtasi ar, 2 licit, vége: 2026.09.19. 17:45) · becsült nyugati ár: **400–800 EUR**
- Állapot jelzők a hirdetésben: repedes
- Indoklás: 1945-ös herendi kávés-mokkás készlet zöld Nanking mintával és koronás címerrel: nagy kanna és 12 csésze aljjal. A címeres, régi herendi készletek nyugaton gyűjtői érdeklődést keltenek. A 80 000 Ft-os kikiáltási ár kb. 200 EUR.
- Kockázat: Egy csészén néhány mm-es tűzrepedés van, egy csésze pótolt és nem koronás. Az eladó csak magánszemélynek értékesít. Aukció, vége 2026-09-19.
- Link: <https://www.vatera.hu/herendi-kaves-mokkas-keszlet-zold-nanking-mintaval-koronas-cimerrel-3523977383.html>

#### [Régebbi Herendi porcelán áttört kosár tál 29,5 x 19 cm](https://www.vatera.hu/regebbi-herendi-porcelan-attort-kosar-tal-29-5-x-19-cm-3526390832.html)

- **Nyugati piacon jól eladható** · bizalom: **kozepes** · Herendi
- Ár: **64 999 Ft** (kikialtasi ar, 3 licit, vége: 2026.09.26. 18:26) · becsült nyugati ár: **250–450 EUR**
- Indoklás: Régi, ritka, áttört herendi gyümölcskosár (29,5 x 19 cm), plasztikus szirmokkal és ágakkal, hibátlan, masszába nyomott jelzéssel, bevizsgálva. 64 999 Ft-os kikiáltási ár (kb. 165 EUR).
- Kockázat: A jelzés elmosódott. Az áttört, plasztikus díszek miatt a szállítás kényes. Aukció.
- Link: <https://www.vatera.hu/regebbi-herendi-porcelan-attort-kosar-tal-29-5-x-19-cm-3526390832.html>

#### [Herendi váza Waldstein körmös porcelán hibátlan 14,8 cm ajándék minőség](https://www.vatera.hu/herendi-vaza-waldstein-kormos-porcelan-hibatlan-14-8-cm-ajandek-minoseg-3527579480.html)

- **Nyugati piacon jól eladható** · bizalom: **kozepes** · Herendi
- Ár: **29 999 Ft** (kikialtasi ar, 2 licit, vége: 2026.09.29. 22:25) · becsült nyugati ár: **120–220 EUR**
- Indoklás: Régebbi herendi Waldstein mintás, körmös lábú váza, 14 cm, hibátlan, minden jelzéssel. A Waldstein ritkábban előforduló minta, a 29 999 Ft-os kikiáltási ár (kb. 76 EUR) jó kiindulás.
- Kockázat: Aukció, a végső ár emelkedhet.
- Link: <https://www.vatera.hu/herendi-vaza-waldstein-kormos-porcelan-hibatlan-14-8-cm-ajandek-minoseg-3527579480.html>

#### [Régebbi herendi orange victoria váza 12,5 cm](https://www.vatera.hu/regebbi-herendi-orange-victoria-vaza-12-5-cm-3528941372.html)

- **Áron aluli + nyugati piac** · bizalom: **kozepes** · Herendi
- Ár: **11 999 Ft** (kikialtasi ar, 2 licit, vége: 2026.10.03. 21:56) · becsült nyugati ár: **90–160 EUR**
- Indoklás: Kézzel festett, régebbi herendi Victoria Orange váza, 12,5 cm, hibátlan, jelzett. A 11 999 Ft-os kikiáltási ár (kb. 30 EUR) a hazai piacon is alacsony.
- Kockázat: Aukció, a licit emelkedhet. Kis darab.
- Link: <https://www.vatera.hu/regebbi-herendi-orange-victoria-vaza-12-5-cm-3528941372.html>

#### [HERENDI PAPAGÁJ (111015)](https://www.vatera.hu/herendi-papagaj-111015-3528647255.html)

- **Áron aluli + nyugati piac** · bizalom: **kozepes** · Herendi
- Ár: **13 500 Ft** (kikialtasi ar, 3 licit, vége: 2026.10.03. 06:56) · becsült nyugati ár: **80–150 EUR**
- Indoklás: 10,8 cm-es hibátlan, kézzel festett, jelzett herendi papagáj 13 500 Ft-os kikiáltási áron (kb. 34 EUR).
- Kockázat: Aukció. Kis figura, alacsony abszolút haszon.
- Link: <https://www.vatera.hu/herendi-papagaj-111015-3528647255.html>

#### [HERENDI NŐI PORCELÁN AKT- LUK ELEK](https://www.vatera.hu/herendi-noi-porcelan-akt-luk-elek-3528306179.html)

- **Nyugati piacon jól eladható** · bizalom: **alacsony** · Herendi
- Ár: **120 000 Ft** (kikialtasi ar, 3 licit, vége: 2026.10.02. 05:30) · becsült nyugati ár: **400–700 EUR**
- Indoklás: Herendi női akt Lux Elek mélynyomott jelzéssel, hibátlan. A Lux Elek-tervek gyűjtők körében keresettek, a 120 000 Ft-os kikiáltási ár (kb. 305 EUR) ehhez képest mérsékelt.
- Kockázat: Nagyon rövid leírás, méret nélkül. Aukció, a végső ár emelkedhet.
- Link: <https://www.vatera.hu/herendi-noi-porcelan-akt-luk-elek-3528306179.html>

### Fix áras (31 tétel)

#### [Herendi Rothschild madaras, 12 személyes, jubileumi, különleges levesestál](https://www.vatera.hu/herendi-rothschild-madaras-12-szemelyes-jubileumi-kulonleges-levesestal-3526021535.html)

- **Áron aluli + nyugati piac** · bizalom: **magas** · Herendi
- Ár: **260 000 Ft** · becsült nyugati ár: **1200–2000 EUR**
- Indoklás: A legnagyobb, 12 személyes herendi levesestál madaras Rothschild (RO) mintával, a 175 éves jubileumi kiadásból (formaszám: 2005/RO), soha nem használt, hibátlan aranyozással. 260 000 Ft (kb. 660 EUR) a jelenlegi bolti ár töredéke.
- Kockázat: 38 cm széles, nehéz darab, a nemzetközi szállítás drága és kockázatos. Az eladó szigorú átvételi határidőt kér.
- Link: <https://www.vatera.hu/herendi-rothschild-madaras-12-szemelyes-jubileumi-kulonleges-levesestal-3526021535.html>

#### [Herendi Viktória levesestál](https://www.vatera.hu/herendi-viktoria-levesestal-3528645125.html)

- **Áron aluli + nyugati piac** · bizalom: **magas** · Herendi
- Ár: **140 000 Ft** · becsült nyugati ár: **600–1000 EUR**
- Indoklás: Herendi Victoria (VBO) mintás, indafogós levesestál, hibátlan, soha nem használt, ép aranyozással. A Queen Victoria minta nyugaton a legkeresettebb herendi dekor, a 140 000 Ft (kb. 355 EUR) jó beszerzési ár.
- Kockázat: 28 cm-es, ezért a méret (6 vagy 12 személyes) a fotókon ellenőrizendő. Szállítási kockázat.
- Link: <https://www.vatera.hu/herendi-viktoria-levesestal-3528645125.html>

#### [1Z996 Nagyméretű Herendi porcelán madár szajkó figura 33 cm](https://www.vatera.hu/1z996-nagymeretu-herendi-porcelan-madar-szajko-figura-33-cm-3501767960.html)

- **Áron aluli + nyugati piac** · bizalom: **magas** · Herendi
- Ár: **120 000 Ft** · becsült nyugati ár: **500–900 EUR**
- Indoklás: 33 cm-es, hibátlan herendi szajkó hecsedlis ágon (formaszám: 5072), kék márkajellel. 120 000 Ft-ért (kb. 305 EUR) a bolti ár töredéke, a nagy herendi madarak nyugaton keresettek.
- Kockázat: Vékony ágak és farok: szállításnál törésveszély.
- Link: <https://www.vatera.hu/1z996-nagymeretu-herendi-porcelan-madar-szajko-figura-33-cm-3501767960.html>

#### [1L654 Hibátlan 12 személyes Zsolnay Pompadour porcelán süteményes készlet](https://www.vatera.hu/1l654-hibatlan-12-szemelyes-zsolnay-pompadour-porcelan-sutemenyes-keszlet-3487247150.html)

- **Áron aluli + nyugati piac** · bizalom: **magas** · Zsolnay
- Ár: **72 000 Ft** · becsült nyugati ár: **350–600 EUR**
- Indoklás: Hibátlan, 12 személyes, gazdagon aranyozott, kék szegélyes Zsolnay Pompadour süteményes készlet (29 cm-es kínáló és 12 tányér), jelzett. 72 000 Ft (kb. 180 EUR), a teljes, 12 személyes Pompadour készletek ritkák.
- Kockázat: 4,2 kg, a szállítás csomagolásigényes.
- Link: <https://www.vatera.hu/1l654-hibatlan-12-szemelyes-zsolnay-pompadour-porcelan-sutemenyes-keszlet-3487247150.html>

#### [1U154 Hibátlan lila Apponyi mintás Herendi porcelán váza 33 cm](https://www.vatera.hu/1u154-hibatlan-lila-apponyi-mintas-herendi-porcelan-vaza-33-cm-3487346153.html)

- **Áron aluli + nyugati piac** · bizalom: **magas** · Herendi
- Ár: **75 000 Ft** · becsült nyugati ár: **300–500 EUR**
- Indoklás: 33 cm-es, kézzel festett, aranyozott, lila Apponyi mintás herendi füles amfóra váza (formaszám: 7176/AP), hibátlan. 75 000 Ft (kb. 190 EUR) ekkora méretű jelzett herendi vázáért kedvező.
- Kockázat: A lejárat 2026-09-16 18:11, ellenőrizni kell, hogy elérhető-e még.
- Link: <https://www.vatera.hu/1u154-hibatlan-lila-apponyi-mintas-herendi-porcelan-vaza-33-cm-3487346153.html>

#### [Antik HERENDI HADIK HUSZÁR porcelán szobor Garancia HIBÁTLAN!!](https://www.vatera.hu/antik-herendi-hadik-huszar-porcelan-szobor-garancia-hibatlan-3526894709.html)

- **Áron aluli + nyugati piac** · bizalom: **magas** · Herendi
- Ár: **39 500 Ft** · becsült nyugati ár: **250–450 EUR**
- Állapot jelzők a hirdetésben: hibas
- Indoklás: 23 cm-es antik herendi Hadik huszár (formaszám: 5526), hibátlan, garanciával. 39 500 Ft (kb. 100 EUR), ugyanez a figura egy másik hirdetésben 98 000 Ft. Egyértelműen áron aluli.
- Kockázat: Csak masszába nyomott jelzés van, kék márkajel nincs említve, a festettséget a fotókon ellenőrizni kell.
- Link: <https://www.vatera.hu/antik-herendi-hadik-huszar-porcelan-szobor-garancia-hibatlan-3526894709.html>

#### [ANTIK ZSOLNAY BÍRKÓZÓ MEDVÉK Markup Béla porcelán szobor garancia, Hibátlan!!](https://www.vatera.hu/antik-zsolnay-birkozo-medvek-markup-bela-porcelan-szobor-garancia-hibatlan-3528589049.html)

- **Áron aluli + nyugati piac** · bizalom: **magas** · Zsolnay
- Ár: **32 500 Ft** · becsült nyugati ár: **250–450 EUR**
- Indoklás: Antik Zsolnay birkózó medvék Markup Béla terve alapján, 32 cm, szép festéssel, hibátlan, jelzett, garanciával. 32 500 Ft (kb. 82 EUR) egy ismert tervezős, nagy Zsolnay szoborért kifejezetten áron aluli.
- Kockázat: A 32 cm lehet hosszúság is, ezt meg kell kérdezni. Nehéz, törékeny darab.
- Link: <https://www.vatera.hu/antik-zsolnay-birkozo-medvek-markup-bela-porcelan-szobor-garancia-hibatlan-3528589049.html>

#### [Ritka Antik HERENDI VÁZA 1.oszt. Bouquet de saxe (BS) KÉZZEL FESTETT HIBÁTLAN, Garancia!!](https://www.vatera.hu/ritka-antik-herendi-vaza-1-oszt-bouquet-de-saxe-bs-kezzel-festett-hibatlan-garancia-3528588389.html)

- **Áron aluli + nyugati piac** · bizalom: **magas** · Herendi
- Ár: **24 500 Ft** · becsült nyugati ár: **130–220 EUR**
- Indoklás: 1. osztályú, kézzel festett herendi Bouquet de Saxe (BS) váza, 18 cm, hibátlan (piros formaszám: 7012 BS). 24 500 Ft (kb. 62 EUR), a párja (Indiai kosár mintás) ugyanennél az eladónál szintén megvan.
- Kockázat: Párban értékesebb, érdemes a párjával együtt megvenni.
- Link: <https://www.vatera.hu/ritka-antik-herendi-vaza-1-oszt-bouquet-de-saxe-bs-kezzel-festett-hibatlan-garancia-3528588389.html>

#### [Antik 1.oszt. HERENDI APPONYI VERT GREEN (AV) MINTÁS VÁZA porcelán HIBÁTLAN, Garancia!](https://www.vatera.hu/antik-1-oszt-herendi-apponyi-vert-green-av-mintas-vaza-porcelan-hibatlan-garancia-3524724029.html)

- **Áron aluli + nyugati piac** · bizalom: **magas** · Herendi
- Ár: **24 500 Ft** · becsült nyugati ár: **120–200 EUR**
- Indoklás: 1. osztályú, kézzel festett herendi Apponyi Vert (AV) váza, 17 cm, hibátlan aranyozással (piros formaszám: 7027 AV). 24 500 Ft (kb. 62 EUR), a nyugati ár ennek két-háromszorosa.
- Kockázat: Kis méret, alacsony abszolút haszon. Ugyanattól az eladótól több hasonló darab érdemes egy csomagban.
- Link: <https://www.vatera.hu/antik-1-oszt-herendi-apponyi-vert-green-av-mintas-vaza-porcelan-hibatlan-garancia-3524724029.html>

#### [Antik HERENDI APPONYI PURPUR (AP) mintás porcelán VÁZA Hibátlan, Garancia!](https://www.vatera.hu/antik-herendi-apponyi-purpur-ap-mintas-porcelan-vaza-hibatlan-garancia-3524920469.html)

- **Áron aluli + nyugati piac** · bizalom: **magas** · Herendi
- Ár: **24 500 Ft** · becsült nyugati ár: **120–200 EUR**
- Indoklás: Kézzel festett herendi Apponyi Purpur (AP) váza, 16 cm, hibátlan, garanciával (formaszám: 7052 AP). 24 500 Ft (kb. 62 EUR).
- Kockázat: A leírás nem írja, hogy 1. osztályú. Kis méret, alacsony abszolút haszon.
- Link: <https://www.vatera.hu/antik-herendi-apponyi-purpur-ap-mintas-porcelan-vaza-hibatlan-garancia-3524920469.html>

#### [Antik HERENDI 1. oszt. APPONYI VERT GREEN (AV) mintás kosárfonott VÁZA porcelán HIBÁTLAN, Garancia!](https://www.vatera.hu/antik-herendi-1-oszt-apponyi-vert-green-av-mintas-kosarfonott-vaza-porcelan-hibatlan-garancia-3527536409.html)

- **Áron aluli + nyugati piac** · bizalom: **magas** · Herendi
- Ár: **19 500 Ft** · becsült nyugati ár: **100–180 EUR**
- Indoklás: 1. osztályú Apponyi Vert (AV) kosárfonott herendi váza, 14,5 cm, hibátlan (formaszám: 6963 AV). 19 500 Ft (kb. 50 EUR).
- Kockázat: Kis méret, alacsony abszolút haszon.
- Link: <https://www.vatera.hu/antik-herendi-1-oszt-apponyi-vert-green-av-mintas-kosarfonott-vaza-porcelan-hibatlan-garancia-3527536409.html>

#### [Herendi Rothschild Új 6 sz étkészlet](https://www.vatera.hu/herendi-rothschild-uj-6-sz-etkeszlet-3491251307.html)

- **Áron aluli + nyugati piac** · bizalom: **kozepes** · Herendi
- Ár: **899 000 Ft** · becsült nyugati ár: **3500–5500 EUR**
- Indoklás: Új, hibátlan, 6 személyes, 26 darabos herendi Rothschild étkészlet: lapos, mély és süteményes tányérok, levesestál, pecsenyés tál, szószos stb. 899 000 Ft (kb. 2275 EUR), ami messze a bolti ár alatt van, a Rothschild étkészletek nyugaton nagyon keresettek.
- Kockázat: Nagy tőkeigény. Sok darab, nehéz csomag, a darabonkénti ellenőrzés és a szállítás időigényes.
- Link: <https://www.vatera.hu/herendi-rothschild-uj-6-sz-etkeszlet-3491251307.html>

#### [Herendi Rothschild mintás 6sz teás garnitúra](https://www.vatera.hu/herendi-rothschild-mintas-6sz-teas-garnitura-3493100438.html)

- **Nyugati piacon jól eladható** · bizalom: **kozepes** · Herendi
- Ár: **385 000 Ft** · becsült nyugati ár: **1500–2500 EUR**
- Indoklás: Herendi Rothschild mintás 6 személyes teás garnitúra: kiöntő, cukortartó, tejkiöntő, 6 csésze és alj, hibátlan. 385 000 Ft (kb. 975 EUR), a teljes Rothschild teáskészletek nyugaton ennek másfél-kétszereséért kelnek el.
- Kockázat: Fix ár. Az eladónak több hasonló készlete is van, ezért érdemes összevetni őket.
- Link: <https://www.vatera.hu/herendi-rothschild-mintas-6sz-teas-garnitura-3493100438.html>

#### [Zsolnay eozin - Bordázott nagyváza -1930](https://www.vatera.hu/zsolnay-eozin-bordazott-nagyvaza-1930-3273802046.html)

- **Nyugati piacon jól eladható** · bizalom: **kozepes** · Zsolnay
- Ár: **265 000 Ft** · becsült nyugati ár: **900–1600 EUR**
- Indoklás: Zsolnay eozin bordázott nagyváza 1930 körülről, hibátlan, jelzett, régiségboltból. Az 1930-as eozin vázák a nyugati Art Deco piacon jól értékesíthetők, a 265 000 Ft (kb. 670 EUR) jó beszerzési ár.
- Kockázat: A leírás csak általános bolti szöveg, méret nélkül, ezért a méretet és a jelzést meg kell kérdezni.
- Link: <https://www.vatera.hu/zsolnay-eozin-bordazott-nagyvaza-1930-3273802046.html>

#### [Zsolnay eozin - Díszváza 1930](https://www.vatera.hu/zsolnay-eozin-diszvaza-1930-3274129457.html)

- **Nyugati piacon jól eladható** · bizalom: **kozepes** · Zsolnay
- Ár: **220 000 Ft** · becsült nyugati ár: **800–1400 EUR**
- Indoklás: Zsolnay eozin díszváza 1930-ból, hibátlan, jelzett, ugyanabból a régiségboltból. 220 000 Ft (kb. 555 EUR), antik eozin darabként nyugaton kétszeres áron is eladható.
- Kockázat: Méret és pontos jelzés nincs megadva, rákérdezni kell.
- Link: <https://www.vatera.hu/zsolnay-eozin-diszvaza-1930-3274129457.html>

#### [Herendi Rothschild ovális citromfogós levesestál](https://www.vatera.hu/herendi-rothschild-ovalis-citromfogos-levesestal-3528644864.html)

- **Áron aluli + nyugati piac** · bizalom: **kozepes** · Herendi
- Ár: **170 000 Ft** · becsült nyugati ár: **700–1100 EUR**
- Indoklás: Herendi Rothschild ovális, citromfogós levesestál (formaszám: 1014/RO), soha nem használt, hibátlan. 170 000 Ft-ért (kb. 430 EUR) ritka forma.
- Kockázat: Ugyanattól a kereskedőtől, mint a többi levesestál. Szállítási kockázat, szigorú átvételi feltételek.
- Link: <https://www.vatera.hu/herendi-rothschild-ovalis-citromfogos-levesestal-3528644864.html>

#### [Herendi Apponyi Orange 12 személyes levesestál](https://www.vatera.hu/herendi-apponyi-orange-12-szemelyes-levesestal-3527661473.html)

- **Áron aluli + nyugati piac** · bizalom: **kozepes** · Herendi
- Ár: **160 000 Ft** · becsült nyugati ár: **600–1000 EUR**
- Indoklás: 12 személyes herendi Apponyi Orange levesestál indafogóval (formaszám: 16/AOC), hibátlan, új állapotú, 24 karátos aranyozással. 160 000 Ft (kb. 405 EUR).
- Kockázat: Az Apponyi Orange kevésbé keresett, mint a Rothschild vagy a Victoria. Szállítási kockázat.
- Link: <https://www.vatera.hu/herendi-apponyi-orange-12-szemelyes-levesestal-3527661473.html>

#### [Zsolnay eozin - Bölény 1937](https://www.vatera.hu/zsolnay-eozin-boleny-1937-3273802028.html)

- **Nyugati piacon jól eladható** · bizalom: **kozepes** · Zsolnay
- Ár: **140 000 Ft** · becsült nyugati ár: **450–800 EUR**
- Indoklás: Zsolnay eozin bölény 1937-ből, hibátlan, jelzett. A régi eozin állatfigurák a gyűjtők körében keresettek, a 140 000 Ft (kb. 355 EUR) mérsékelt.
- Kockázat: Méret nincs megadva. A modern eozin bölényektől el kell különíteni a jelzés alapján.
- Link: <https://www.vatera.hu/zsolnay-eozin-boleny-1937-3273802028.html>

#### [1E489 Viktória mintás Herendi porcelán váza 34.5 cm](https://www.vatera.hu/1e489-viktoria-mintas-herendi-porcelan-vaza-34-5-cm-3487243616.html)

- **Nyugati piacon jól eladható** · bizalom: **kozepes** · Herendi
- Ár: **145 000 Ft** · becsült nyugati ár: **400–700 EUR**
- Indoklás: 34,5 cm-es, lila Apponyi (AP) mintás herendi díszváza (formaszám: 6651/AP), hibátlan, kopásmentes aranyozással. A cím Viktória mintát ír, de a leírás szerint Apponyi. 145 000 Ft (kb. 365 EUR).
- Kockázat: A minta a címben és a leírásban eltér, a fotókon ellenőrizendő.
- Link: <https://www.vatera.hu/1e489-viktoria-mintas-herendi-porcelan-vaza-34-5-cm-3487243616.html>

#### [Hatalmas Herendi porcelán figura - " Akt zöld lepellel " -   35 cm.-es hibátlan, jelzett szépség...](https://www.vatera.hu/hatalmas-herendi-porcelan-figura-akt-zold-lepellel-35-cm-es-hibatlan-jelzett-szepseg-3272242091.html)

- **Áron aluli + nyugati piac** · bizalom: **kozepes** · Herendi
- Ár: **79 800 Ft** · becsült nyugati ár: **350–600 EUR**
- Indoklás: Hatalmas, 35 cm-es herendi figura (Akt zöld lepellel), hibátlan és jelzett a cím szerint. 79 800 Ft (kb. 200 EUR) ekkora méretű herendi aktért kedvező.
- Kockázat: A leírás csak az üzlet általános szövegét tartalmazza, az állapotot és a jelzést a fotókon ellenőrizni kell. Szállítási kockázat.
- Link: <https://www.vatera.hu/hatalmas-herendi-porcelan-figura-akt-zold-lepellel-35-cm-es-hibatlan-jelzett-szepseg-3272242091.html>

#### [1F470 Antik Zsolnay porcelánfajansz váza családi jelzéssel ~1880](https://www.vatera.hu/1f470-antik-zsolnay-porcelanfajansz-vaza-csaladi-jelzessel-1880-3487243697.html)

- **Nyugati piacon jól eladható** · bizalom: **kozepes** · Zsolnay
- Ár: **75 000 Ft** · becsült nyugati ár: **300–600 EUR**
- Indoklás: Antik, kézzel festett, virág- és pillangódíszes vajszínű Zsolnay fajansz váza 1880 körülről, öttornyú kék családi jelzéssel (ZSOLNAY PÉCS T.J.M.). A korai, családi jelzéses darabok gyűjtői tárgyak, 75 000 Ft (kb. 190 EUR).
- Kockázat: Kis méret (12 cm). Az állapot nincs részletezve. A lejárat 2026-09-16 18:11, ellenőrizni kell.
- Link: <https://www.vatera.hu/1f470-antik-zsolnay-porcelanfajansz-vaza-csaladi-jelzessel-1880-3487243697.html>

#### [1N564 Antik Herendi óherendi Lúdas Matyi LUX ELEK porcelán figura 24.5 cm](https://www.vatera.hu/1n564-antik-herendi-oherendi-ludas-matyi-lux-elek-porcelan-figura-24-5-cm-3487249883.html)

- **Áron aluli + nyugati piac** · bizalom: **kozepes** · Herendi
- Ár: **72 000 Ft** · becsült nyugati ár: **300–550 EUR**
- Indoklás: Hibátlan, kézzel festett, talapzatos Lúdas Matyi óherendi jelzéssel, a talapzaton LUX ELEK tervezői névvel, 24,5 cm. A Lux Elek-féle régi figurák gyűjtői tárgyak, 72 000 Ft (kb. 180 EUR) kedvező ár.
- Kockázat: A lejárat 2026-09-16 18:11 volt, a hirdetés addigra lezárulhatott vagy újraindulhatott, a linken ellenőrizendő.
- Link: <https://www.vatera.hu/1n564-antik-herendi-oherendi-ludas-matyi-lux-elek-porcelan-figura-24-5-cm-3487249883.html>

#### [1Z997 Régi nagyméretű Herendi porcelán foxi kutya foxterrier figura](https://www.vatera.hu/1z997-regi-nagymeretu-herendi-porcelan-foxi-kutya-foxterrier-figura-3501768152.html)

- **Nyugati piacon jól eladható** · bizalom: **kozepes** · Herendi
- Ár: **85 000 Ft** · becsült nyugati ár: **300–500 EUR**
- Indoklás: Régi, nagyméretű (33,5 cm hosszú), festett herendi foxterrier, hibátlan, jelzett. A kutyafigurák az angolszász piacon különösen jól fogynak, a 85 000 Ft (kb. 215 EUR) ehhez képest kedvező.
- Kockázat: Formaszám nincs megadva, a festés minőségét a fotókon érdemes ellenőrizni.
- Link: <https://www.vatera.hu/1z997-regi-nagymeretu-herendi-porcelan-foxi-kutya-foxterrier-figura-3501768152.html>

#### [1Z775 Régi nagyméretű Herendi porcelán madár szajkó figura 19.7 cm](https://www.vatera.hu/1z775-regi-nagymeretu-herendi-porcelan-madar-szajko-figura-19-7-cm-3499799522.html)

- **Nyugati piacon jól eladható** · bizalom: **kozepes** · Herendi
- Ár: **85 000 Ft** · becsült nyugati ár: **250–400 EUR**
- Indoklás: 19,7 cm-es, kézzel festett, hibátlan herendi szajkó (formaszám: 5108), jelzett. 85 000 Ft (kb. 215 EUR) mellett nyugati eladásnál van árrés.
- Kockázat: Kisebb a haszon, a szállítási és platformköltség jelentős része elvisz belőle.
- Link: <https://www.vatera.hu/1z775-regi-nagymeretu-herendi-porcelan-madar-szajko-figura-19-7-cm-3499799522.html>

#### [Herendi papagáj](https://www.vatera.hu/herendi-papagaj-3493102247.html)

- **Áron aluli + nyugati piac** · bizalom: **kozepes** · Herendi
- Ár: **25 000 Ft** · becsült nyugati ár: **120–220 EUR**
- Indoklás: 13 cm-es hibátlan, jelzett herendi papagáj 25 000 Ft-ért (kb. 63 EUR). Ugyanez az eladó egy 14 cm-es papagájt 45 000 Ft-ért kínál, ez a darab ehhez képest is olcsó.
- Kockázat: Formaszám és festési változat nincs megadva.
- Link: <https://www.vatera.hu/herendi-papagaj-3493102247.html>

#### [Nagyobb méretű ( 18 cm magas) herendi madár figura / hibátlan](https://www.vatera.hu/nagyobb-meretu-18-cm-magas-herendi-madar-figura-hibatlan-3464572610.html)

- **Áron aluli + nyugati piac** · bizalom: **kozepes** · Herendi
- Ár: **22 800 Ft** · becsült nyugati ár: **120–200 EUR**
- Indoklás: 18 cm-es, hibátlan herendi madárfigura 22 800 Ft-ért (kb. 58 EUR). Ekkora méretű festett herendi madár nyugaton kétszer-háromszor ennyiért is eladható.
- Kockázat: A faj, a festés és a formaszám nincs megadva. Magánszemély, korlátozott átvétel.
- Link: <https://www.vatera.hu/nagyobb-meretu-18-cm-magas-herendi-madar-figura-hibatlan-3464572610.html>

#### [RITKA Antik HERENDI SZENT LÁSZLÓ porcelán szobor Garancia, Hibátlan!!](https://www.vatera.hu/ritka-antik-herendi-szent-laszlo-porcelan-szobor-garancia-hibatlan-3527136749.html)

- **Áron aluli** · bizalom: **kozepes** · Herendi
- Ár: **14 500 Ft** · becsült nyugati ár: **80–150 EUR**
- Indoklás: Antik, jelzett herendi Szent László szobor, hibátlan, garanciával, mindössze 14 500 Ft-ért (kb. 37 EUR). Ritkán előforduló téma, a hazai árhoz képest is olcsó.
- Kockázat: Csak 10 cm-es, így a nyugati eladási érték korlátozott.
- Link: <https://www.vatera.hu/ritka-antik-herendi-szent-laszlo-porcelan-szobor-garancia-hibatlan-3527136749.html>

#### [Antik Zsolnay, Nikelszky szőlős váza](https://www.vatera.hu/antik-zsolnay-nikelszky-szolos-vaza-3526996043.html)

- **Nyugati piacon jól eladható** · bizalom: **alacsony** · Zsolnay
- Ár: **220 000 Ft** · becsült nyugati ár: **700–1200 EUR**
- Indoklás: Antik Zsolnay alapmázas szőlőmotívumos váza, Nikelszky Géza terve (1930), 35 cm, hibátlan. A nagy szecessziós, illetve art deco Zsolnay vázák nyugaton keresettek, a 220 000 Ft (kb. 555 EUR) ehhez képest mérsékelt.
- Kockázat: A hirdetés szerint nem jelzett, ezért az eredetiség és a tervező szakértői ellenőrzést igényel.
- Link: <https://www.vatera.hu/antik-zsolnay-nikelszky-szolos-vaza-3526996043.html>

#### [Herendi ANTIK 1890- 1900 6db tányér garnitúra](https://www.vatera.hu/herendi-antik-1890-1900-6db-tanyer-garnitura-3502089875.html)

- **Nyugati piacon jól eladható** · bizalom: **alacsony** · Herendi
- Ár: **125 000 Ft** · becsült nyugati ár: **400–700 EUR**
- Indoklás: 6 darabos antik herendi tányérsor 1890 és 1900 közöttről, 25 cm, hibátlan. A 19. századi herendi tányérok nyugati aukciókon keresettek, a 125 000 Ft (kb. 315 EUR) mérsékelt ár.
- Kockázat: A minta nincs megnevezve, a kor és a jelzés a fotókon ellenőrizendő.
- Link: <https://www.vatera.hu/herendi-antik-1890-1900-6db-tanyer-garnitura-3502089875.html>

#### [Antik Ritka ZSOLNAY SÁRKÁNYGYÍKOS KÍNÁLÓ Nagyméretű EOZIN kosártál Alapmázas 27 cm!](https://www.vatera.hu/antik-ritka-zsolnay-sarkanygyikos-kinalo-nagymeretu-eozin-kosartal-alapmazas-27-cm-3527645609.html)

- **Áron aluli + nyugati piac** · bizalom: **alacsony** · Zsolnay
- Ár: **44 500 Ft** · becsült nyugati ár: **250–500 EUR**
- Állapot jelzők a hirdetésben: repedes
- Indoklás: Nagyméretű (27 cm) antik Zsolnay eozin kosártál két harcoló sárkánygyík fogantyúval, törés- és repedésmentes. Ritka, gyűjtői forma 44 500 Ft-ért (kb. 113 EUR).
- Kockázat: Nincs rajta jelzés, ezért az eredetiség nem igazolt. Égetés közbeni mázhálósodás (hárisz) látható.
- Link: <https://www.vatera.hu/antik-ritka-zsolnay-sarkanygyikos-kinalo-nagymeretu-eozin-kosartal-alapmazas-27-cm-3527645609.html>

#### [Zsolnay porcelán szecessziós névjegytál - Zsolnay eozinmázas rákos tál](https://www.vatera.hu/zsolnay-porcelan-szecesszios-nevjegytal-zsolnay-eozinmazas-rakos-tal-3483997382.html)

- **Áron aluli + nyugati piac** · bizalom: **alacsony** · Zsolnay
- Ár: **32 000 Ft** · becsült nyugati ár: **150–300 EUR**
- Indoklás: Zsolnay eozin mázas szecessziós rákos névjegytál, jelzett. 32 000 Ft-ért (kb. 80 EUR) a figurális eozin névjegytálak nyugaton jóval drágábbak.
- Kockázat: A leírás csak általános bolti szöveg, a kor, a méret és az állapot nem ismert.
- Link: <https://www.vatera.hu/zsolnay-porcelan-szecesszios-nevjegytal-zsolnay-eozinmazas-rakos-tal-3483997382.html>

### Alkuképes / irányáras (7 tétel)

#### [Herendi Indiai Óriás Váza](https://www.vatera.hu/herendi-indiai-orias-vaza-3496021163.html)

- **Áron aluli** · bizalom: **kozepes** · Herendi
- Ár: **335 000 Ft** · becsült nyugati ár: **1500–2500 EUR**
- Indoklás: 65 cm-es herendi Indiai kosár mintás óriás váza, hibátlan, a hirdetés szerint 670 000 Ft-os bolti áron. Alkuképes 335 000 Ft-os irányár (kb. 850 EUR), miközben ugyanez az eladó egy hasonló vázát fix 550 000 Ft-ért kínál. Van egy második, azonos hirdetés is (3496026254).
- Kockázat: 65 cm-es, nagyon nehéz és törékeny, nemzetközileg szinte csak raklapon szállítható. Inkább hazai továbbértékesítésre vagy személyes átvételre való.
- Link: <https://www.vatera.hu/herendi-indiai-orias-vaza-3496021163.html>

#### [Antik Zsolnay kacsa és béka Multicolor eozin tál 260808](https://www.vatera.hu/antik-zsolnay-kacsa-es-beka-multicolor-eozin-tal-260808-3517637429.html)

- **Áron aluli + nyugati piac** · bizalom: **kozepes** · Zsolnay
- Ár: **130 000 Ft** · becsült nyugati ár: **600–1100 EUR**
- Indoklás: Antik Zsolnay eozin tál kacsa- és békadísszel, az 1920–30-as évekből, ritka indigókék, labrador hatású mázzal, jelzett, a peremén tervezői szignóval. A 130 000 Ft-os alkuképes ár (kb. 330 EUR) a nyugati Art Nouveau/eozin piac árainak töredéke.
- Kockázat: A kacsa fején tűhegynyi kopás van. A körpecsétnek csak a helye látszik, a jelzést fotón ellenőrizni kell.
- Link: <https://www.vatera.hu/antik-zsolnay-kacsa-es-beka-multicolor-eozin-tal-260808-3517637429.html>

#### [Herendi táncoló csikósok.](https://www.vatera.hu/herendi-tancolo-csikosok-3337061861.html)

- **Nyugati piacon jól eladható** · bizalom: **kozepes** · Herendi
- Ár: **150 000 Ft** · becsült nyugati ár: **500–900 EUR**
- Indoklás: Kézzel festett herendi táncoló csikós pár, darabonként 30 cm, teljesen hibátlan. Alkuképes, 150 000 Ft a párra (kb. 380 EUR), a magyaros herendi figurák párban nyugaton jól értékesíthetők.
- Kockázat: Formaszám és jelzés részletei nincsenek megadva. Két nagy figura szállítása.
- Link: <https://www.vatera.hu/herendi-tancolo-csikosok-3337061861.html>

#### [Herendi, Lux Elek - Madonna](https://www.vatera.hu/herendi-lux-elek-madonna-3506808263.html)

- **Áron aluli + nyugati piac** · bizalom: **kozepes** · Herendi
- Ár: **80 000 Ft** · becsült nyugati ár: **400–700 EUR**
- Indoklás: 36 cm magas, kézzel festett herendi Madonna, hibátlan, 1960-as évek, jelzett. Nagy méretű vallási témájú herendi figura, alkuképes 80 000 Ft-os áron (kb. 200 EUR).
- Kockázat: A cím Lux Elek tervet említ, de a leírás ezt nem igazolja. A méret miatt drága és kockázatos a szállítás.
- Link: <https://www.vatera.hu/herendi-lux-elek-madonna-3506808263.html>

#### [Ritka Ophélia Herendi porcelán szobor - 53272](https://www.vatera.hu/ritka-ophelia-herendi-porcelan-szobor-53272-3487483862.html)

- **Áron aluli + nyugati piac** · bizalom: **kozepes** · Herendi
- Ár: **80 000 Ft** · becsült nyugati ár: **350–600 EUR**
- Indoklás: 28 cm-es herendi Ophélia figura (karcolt formaszám: 5875), hibátlan, XX. század második feléből. Alkuképes, 80 000 Ft-os irányár (kb. 200 EUR), lealkudható.
- Kockázat: A hirdetés lejárata 2026-09-16 19:56, gyorsan kell dönteni. Festetlen vagy festett változat a fotókon ellenőrizendő.
- Link: <https://www.vatera.hu/ritka-ophelia-herendi-porcelan-szobor-53272-3487483862.html>

#### [Herendi, Lux Elek - Fésülködő](https://www.vatera.hu/herendi-lux-elek-fesulkodo-3506808083.html)

- **Áron aluli + nyugati piac** · bizalom: **kozepes** · Herendi
- Ár: **60 000 Ft** · becsült nyugati ár: **350–600 EUR**
- Indoklás: 38 cm magas, kézzel festett herendi Fésülködő nőalak, hibátlan, mélynyomott jelzéssel. Ugyanannál az eladónál, mint a Madonna, alkuképes 60 000 Ft-os áron (kb. 150 EUR).
- Kockázat: A Lux Elek tervezői hivatkozást ellenőrizni kell. Nagy figura, szállítási kockázat.
- Link: <https://www.vatera.hu/herendi-lux-elek-fesulkodo-3506808083.html>

#### [Nikelszky Géza Zsolnay körpecsétes madaras váza - 53870](https://www.vatera.hu/nikelszky-geza-zsolnay-korpecsetes-madaras-vaza-53870-3515048009.html)

- **Nyugati piacon jól eladható** · bizalom: **alacsony** · Zsolnay
- Ár: **580 000 Ft** · becsült nyugati ár: **1500–3000 EUR**
- Indoklás: Zsolnay madaras váza Nikelszky Géza terve alapján, domború, öttornyos körpecséttel és ZSOLNAY PÉCS körirattal (formaszám: 5330), 18,5 cm. A körpecsétes korai Zsolnay darabok nemzetközi aukciókon magas áron kelnek el.
- Kockázat: Már az 580 000 Ft-os irányár (kb. 1470 EUR) is magas. Az állapot nincs leírva. A haszon csak alkuval reális.
- Link: <https://www.vatera.hu/nikelszky-geza-zsolnay-korpecsetes-madaras-vaza-53870-3515048009.html>

## Hol, mennyiért és milyen gyorsan adhatók el a fix áras tételek

Csak a válogatás 31 fix áras tétele. A táblázat 2026-09-16-i piaci kutatáson alapul: az aktív eBay-kínálaton (eBay.com és eBay.de, a PicClick tükrén keresztül) és a webes keresővel talált lezárt eladásokon, aukciós eredményeken. **A fenti válogatás EUR-becslései a kutatás előtt készültek. Ahol eltérnek, ez a táblázat az irányadó.** Több tételnél a kutatás lefelé módosította a becslést, például egy nagy herendi szajkó (5072) az eBay-en 224 USD-ért kelt el.

### Módszer

- **Kezdő hirdetési ár:** az az ár, amelyen érdemes feltölteni a hirdetést. Az aktív összehasonlítható hirdetések mediánjához igazodik, ha az a fedezet felett van. Etsyn és eBay-en ajánlattétellel együtt, Catawikin ez a kért becsérték.
- **Legkisebb elfogadható ár (fedezet + 10%):** a Vatera-ár átváltva (1 EUR = 395 Ft, 1 EUR = 1,15 USD), elosztva (1 − piactéri díj)-jal, plusz 10% minimális haszon, felfelé kerekítve. Díjak: eBay.com 15%, eBay.de 13%, Etsy 12%, Catawiki 12,5%. A szállítást a vevő fizeti.
- **Likviditás és eladási idő:** az ár helye az aktív összehasonlítható eBay-hirdetések között. A legolcsóbb negyedben (≤ alsó kvartilis) **magas**, jellemzően 1–4 hét. Az alsó kvartilis és a medián között **közepes–magas**, 3–8 hét. A medián és a felső kvartilis között **közepes**, 1–3 hónap. A felső kvartilis felett **alacsony**, 3–6+ hónap, vagy nem kel el. Ahol kevés az összehasonlító hirdetés, vagy azok nem ugyanolyan tárgyak, ott a besorolást kézzel, a talált eladási adatok alapján módosítottam, ezt a megjegyzés jelzi.
- **Catawiki:** kurált aukció. Az idő a befogadás (kb. 1 hét) és a 7 napos aukció együtt. A „legkisebb elfogadható” itt a minimálár, a likviditás pedig annak az esélye, hogy a licit eléri.
- **Korlát:** az eBay, a Catawiki, az Etsy és a WorthPoint lezárt eladási oldalait nem lehetett közvetlenül lekérni (403 / captcha). Ezért a kereslet oldalát csak a keresővel talált szórványos eladások mutatják, a likviditás becslés. Feltöltés előtt érdemes saját eBay-fiókból a „Sold items” szűrővel ellenőrizni.

**Értékelés:** *Ajánlott* = a legkisebb elfogadható ár a piaci medián alatt vagy körül van, reálisan 3 hónapon belül haszonnal eladható. *Szűk árrés* = eladható, de kevés a haszon vagy lassú. *Nem ajánlott* = a piaci ár nem fedezi a Vatera-árat, a díjat és a minimális hasznot, vagy nincs igazolt kereslet ezen az áron.

### A javasolt piacterek

- **eBay.com (USA):** A legnagyobb Herendi-gyűjtői vevőkör, sok „sold” referenciaár. Díj: kb. 13–15% értékesítési díj a teljes összegre (szállítással együtt), plusz nemzetközi díj. Nagy értékű figurákhoz, levesestálakhoz, teáskészlethez. Az USA-ba küldött csomagokra 2025 óta vám van, a kis értékűekre is (EU-áru: kb. 15%). Az eBay International Shipping ezt a vevőnél beszedi, de a teljes ár emiatt magasabb lesz a vevőnek.
- **eBay.de (Németország/EU):** Az osztrák és német vevők ismerik a Zsolnayt és a Pompadourt. Az EU-n belül nincs vám, és a szállítás olcsóbb. Díj külföldi eladóként kb. 11–13% plusz nemzetközi díj. Zsolnay figurákhoz, készletekhez, a jelzés nélküli darabokhoz („Zsolnay zugeschrieben”).
- **Etsy (USA/EU):** Vintage lakberendezési vevők, alacsonyabb díjak: 0,20 USD feltöltési díj, 6,5% tranzakciós díj és kb. 3–4% fizetési díj. Az Etsy offsite hirdetései miatt ehhez eseti 12–15% jöhet. Kisebb, 50–250 USD-s tárgyakhoz. Szabály: vintage kategóriában a tárgynak legalább 20 évesnek kell lennie, ezt feltöltés előtt ellenőrizd a jelzés alapján.
- **Catawiki (EU, kurált aukció):** Szakértő ellenőrzi és fogadja be a tételt, ami a jelzés nélküli vagy antik daraboknál hitelességet ad. Az európai vevők a Zsolnay eozint és az antik herendi darabokat jól fizetik. Eladói jutalék 12,5%, a szállítást a vevő fizeti. Minimálárral indítható, így nem kel el áron alul.

**Összesítés:** Ajánlott: 15 tétel · Szűk árrés: 8 tétel · Nem ajánlott: 8 tétel

### eBay.com (13 tétel)

| Tétel | Vatera ár | Kezdő hirdetési ár | Becsült eladási idő ezen az áron | Likviditás ezen az áron | Legkisebb elfogadható ár | Eladási idő és likviditás a legkisebb áron | Aktív eBay-kínálat (db, medián, alsó–felső negyed) | Értékelés | Megjegyzés |
|---|---:|---:|---|---|---:|---|---|---|---|
| [Herendi Rothschild madaras, 12 személyes, jubileumi, különleges levesestál](https://www.vatera.hu/herendi-rothschild-madaras-12-szemelyes-jubileumi-kulonleges-levesestal-3526021535.html) | 260 000 Ft (≈ 757 USD) | 1 450 USD | 2–5 hónap | alacsony–közepes | 980 USD | 1–3 hónap, közepes | 38 db, medián 952 USD (750–1250) | **Ajánlott** | A legnagyobb, 12 személyes jubileumi forma, ezért a medián felett is indokolt. Kézi korrekció: a konkurencia többsége kisebb tál. |
| [Herendi Viktória levesestál](https://www.vatera.hu/herendi-viktoria-levesestal-3528645125.html) | 140 000 Ft (≈ 408 USD) | 750 USD | 1–3 hónap | közepes | 530 USD | 3–8 hét, közepes–magas | 20 db, medián 735 USD (342–1100) | **Ajánlott** | Queen Victoria tál, új ára 1 645 USD (2 qt). A 28 cm-es méret miatt valószínűleg a kisebb változat. |
| [Antik HERENDI HADIK HUSZÁR porcelán szobor Garancia HIBÁTLAN!!](https://www.vatera.hu/antik-herendi-hadik-huszar-porcelan-szobor-garancia-hibatlan-3526894709.html) | 39 500 Ft (≈ 115 USD) | 250 USD | 1–3 hónap | közepes | 150 USD | 3–8 hét, közepes–magas | 34 db, medián 192 USD (129–300) | **Ajánlott** | Sok konkurens (34 aktív). Egy 2017-es aukciós becslés 50–100 USD volt, ezért a hirdetési árból lehet, hogy engedni kell. |
| [Herendi Rothschild ovális citromfogós levesestál](https://www.vatera.hu/herendi-rothschild-ovalis-citromfogos-levesestal-3528644864.html) | 170 000 Ft (≈ 495 USD) | 950 USD | 3–8 hét | közepes–magas | 650 USD | 1–4 hét, magas | 38 db, medián 952 USD (750–1250) | **Ajánlott** | A legjobb arány: a legkisebb elfogadható ár a konkurens Rothschild levesestálak alsó negyedében van. Új ár 1 945–2 205 USD, aukción 1 722 USD. |
| [Herendi Apponyi Orange 12 személyes levesestál](https://www.vatera.hu/herendi-apponyi-orange-12-szemelyes-levesestal-3527661473.html) | 160 000 Ft (≈ 466 USD) | 850 USD | 1–3 hónap | közepes | 610 USD | 3–8 hét, közepes–magas | 65 db, medián 750 USD (400–1200) | **Ajánlott** | Nagy a kínálat (65 aktív Chinese Bouquet/Rust tál), a címben a „12 person / large” méretet emeld ki. |
| [1Z997 Régi nagyméretű Herendi porcelán foxi kutya foxterrier figura](https://www.vatera.hu/1z997-regi-nagymeretu-herendi-porcelan-foxi-kutya-foxterrier-figura-3501768152.html) | 85 000 Ft (≈ 247 USD) | 450 USD | 1–3 hónap | közepes | 330 USD | 1–4 hét, magas | 16 db, medián 428 USD (370–585) | **Ajánlott** | Az aktív foxterrier-figurák 370–585 USD között vannak, a legkisebb elfogadható ár ezek alatt. |
| [1Z996 Nagyméretű Herendi porcelán madár szajkó figura 33 cm](https://www.vatera.hu/1z996-nagymeretu-herendi-porcelan-madar-szajko-figura-33-cm-3501767960.html) | 120 000 Ft (≈ 349 USD) | 595 USD | 2–4 hónap | alacsony–közepes | 460 USD | 1–3 hónap, közepes | 7 db, medián 595 USD (320–595) | **Szűk árrés** | Csak 7 aktív konkurens, és egy ugyanilyen 5072-es szajkó 224 USD-ért kelt el. A korábbi 500–900 EUR-s becslés túlzó volt. |
| [1U154 Hibátlan lila Apponyi mintás Herendi porcelán váza 33 cm](https://www.vatera.hu/1u154-hibatlan-lila-apponyi-mintas-herendi-porcelan-vaza-33-cm-3487346153.html) | 75 000 Ft (≈ 218 USD) | 450 USD | 3–6 hónap | alacsony | 290 USD | 2–4 hónap, alacsony–közepes | 66 db, medián 136 USD (75–245) | **Szűk árrés** | Az aktív Apponyi Purple vázák többsége kicsi, így egy 33 cm-es amfórával kevés a közvetlen konkurencia, de kevés a vevő is. |
| [Herendi Rothschild mintás 6sz teás garnitúra](https://www.vatera.hu/herendi-rothschild-mintas-6sz-teas-garnitura-3493100438.html) | 385 000 Ft (≈ 1 121 USD) | 1 950 USD | 3–6+ hónap | alacsony | 1 500 USD | 3–6 hónap, alacsony | 27 db, medián 500 USD (345–650) | **Szűk árrés** | Az aktív Rothschild teáskészletek többsége hiányos vagy 2 személyes (medián 500 USD), teljes 6 személyes készletre kevés az adat. Kockázatos. |
| [1E489 Viktória mintás Herendi porcelán váza 34.5 cm](https://www.vatera.hu/1e489-viktoria-mintas-herendi-porcelan-vaza-34-5-cm-3487243616.html) | 145 000 Ft (≈ 422 USD) | 750 USD | 3–6+ hónap | alacsony | 550 USD | 3–6+ hónap, alacsony | 66 db, medián 136 USD (75–245) | **Nem ajánlott** | A fedezethez szükséges 550 USD messze az aktív Apponyi Purple vázák felső negyede (245 USD) felett van. Nagy váza, de igazolt kereslet ezen az áron nincs. |
| [Hatalmas Herendi porcelán figura - " Akt zöld lepellel " -   35 cm.-es hibátlan, jelzett szépség...](https://www.vatera.hu/hatalmas-herendi-porcelan-figura-akt-zold-lepellel-35-cm-es-hibatlan-jelzett-szepseg-3272242091.html) | 79 800 Ft (≈ 232 USD) | 450 USD | 3–6+ hónap | alacsony | 310 USD | 2–4 hónap, alacsony | nincs összehasonlítható | **Nem ajánlott** | Nincs összehasonlítható aktív hirdetés. Herendi aktokra talált aukciós becslések 20–300 USD. |
| [1N564 Antik Herendi óherendi Lúdas Matyi LUX ELEK porcelán figura 24.5 cm](https://www.vatera.hu/1n564-antik-herendi-oherendi-ludas-matyi-lux-elek-porcelan-figura-24-5-cm-3487249883.html) | 72 000 Ft (≈ 210 USD) | 320 USD | 3–6+ hónap | alacsony | 280 USD | 3–6+ hónap, alacsony | 99 db, medián 130 USD (70–215) | **Nem ajánlott** | 99 aktív Lúdas Matyi-hirdetés, medián 130 USD. Egy Lux Elek-jelzésű példány Magyarországon 26 000 Ft-ért kelt el aukción. A Vatera-ár túl magas. Piactér eBay.com-ra módosítva. |
| [1Z775 Régi nagyméretű Herendi porcelán madár szajkó figura 19.7 cm](https://www.vatera.hu/1z775-regi-nagymeretu-herendi-porcelan-madar-szajko-figura-19-7-cm-3499799522.html) | 85 000 Ft (≈ 247 USD) | 395 USD | 3–6+ hónap | alacsony | 330 USD | 3–6 hónap, alacsony | 7 db, medián 595 USD (320–595) | **Nem ajánlott** | A kisebb (5108) szajkó a nagy változatnál is olcsóbban kel el, az pedig 224 USD-ért. A fedezet nem teljesül. |

### eBay.de (5 tétel)

| Tétel | Vatera ár | Kezdő hirdetési ár | Becsült eladási idő ezen az áron | Likviditás ezen az áron | Legkisebb elfogadható ár | Eladási idő és likviditás a legkisebb áron | Aktív eBay-kínálat (db, medián, alsó–felső negyed) | Értékelés | Megjegyzés |
|---|---:|---:|---|---|---:|---|---|---|---|
| [1L654 Hibátlan 12 személyes Zsolnay Pompadour porcelán süteményes készlet](https://www.vatera.hu/1l654-hibatlan-12-szemelyes-zsolnay-pompadour-porcelan-sutemenyes-keszlet-3487247150.html) | 72 000 Ft (≈ 182 EUR) | 380 EUR | 1–3 hónap | közepes | 240 EUR | 3–8 hét, közepes–magas | nincs összehasonlítható | **Ajánlott** | Kézi besorolás: egy 12 darabos Pompadour tányérkészlet C$400-ért, egy 6+1-es süteményes készlet 371 USD-ért volt hirdetve. |
| [ANTIK ZSOLNAY BÍRKÓZÓ MEDVÉK Markup Béla porcelán szobor garancia, Hibátlan!!](https://www.vatera.hu/antik-zsolnay-birkozo-medvek-markup-bela-porcelan-szobor-garancia-hibatlan-3528589049.html) | 32 500 Ft (≈ 82 EUR) | 350 EUR | 2–4 hónap | közepes–alacsony | 105 EUR | 1–4 hét, magas | nincs összehasonlítható | **Ajánlott** | Kézi besorolás: a nagy (kb. 30 cm) Markup-féle birkózó medvék eBay-en és Etsyn is aktívak, de lezárt ár nem volt elérhető. A legkisebb elfogadható ár a kis medvefigurák mediánja körül van, így könnyen eladható. |
| [Zsolnay porcelán szecessziós névjegytál - Zsolnay eozinmázas rákos tál](https://www.vatera.hu/zsolnay-porcelan-szecesszios-nevjegytal-zsolnay-eozinmazas-rakos-tal-3483997382.html) | 32 000 Ft (≈ 81 EUR) | 240 EUR | 3–8 hét | közepes–magas | 105 EUR | 1–4 hét, magas | 16 db, medián 244 EUR (175–346) | **Ajánlott** | A legnagyobb arányos árrés: hasonló eozin rák/homár tálak 199–420 USD, az eBay.de medián 244 EUR. A méretet és a jelzést meg kell kérdezni. |
| [Antik Ritka ZSOLNAY SÁRKÁNYGYÍKOS KÍNÁLÓ Nagyméretű EOZIN kosártál Alapmázas 27 cm!](https://www.vatera.hu/antik-ritka-zsolnay-sarkanygyikos-kinalo-nagymeretu-eozin-kosartal-alapmazas-27-cm-3527645609.html) | 44 500 Ft (≈ 113 EUR) | 290 EUR | 3–6 hónap | alacsony | 145 EUR | 1–3 hónap, közepes–alacsony | nincs összehasonlítható | **Szűk árrés** | Jelzés nélküli darab, mindössze 1 aktív hasonló eBay.de-hirdetés van. Csak „Zsolnay zugeschrieben” megnevezéssel adható el. |
| [Zsolnay eozin - Bölény 1937](https://www.vatera.hu/zsolnay-eozin-boleny-1937-3273802028.html) | 140 000 Ft (≈ 354 EUR) | 450 EUR | 3–6+ hónap | alacsony | 450 EUR | 3–6+ hónap, alacsony | 25 db, medián 144 EUR (93–438) | **Nem ajánlott** | Eozin bölény aukciós becslés 200–400 USD, az eBay.de medián 144 EUR. A fedezet nem teljesül. |

### Etsy (7 tétel)

| Tétel | Vatera ár | Kezdő hirdetési ár | Becsült eladási idő ezen az áron | Likviditás ezen az áron | Legkisebb elfogadható ár | Eladási idő és likviditás a legkisebb áron | Aktív eBay-kínálat (db, medián, alsó–felső negyed) | Értékelés | Megjegyzés |
|---|---:|---:|---|---|---:|---|---|---|---|
| [Ritka Antik HERENDI VÁZA 1.oszt. Bouquet de saxe (BS) KÉZZEL FESTETT HIBÁTLAN, Garancia!!](https://www.vatera.hu/ritka-antik-herendi-vaza-1-oszt-bouquet-de-saxe-bs-kezzel-festett-hibatlan-garancia-3528588389.html) | 24 500 Ft (≈ 71 USD) | 170 USD | 1–3 hónap | közepes | 90 USD | 3–8 hét, közepes–magas | 67 db, medián 154 USD (85–250) | **Ajánlott** | Párban (az Indiai kosár mintás párjával) könnyebben és drágábban eladható. |
| [Antik 1.oszt. HERENDI APPONYI VERT GREEN (AV) MINTÁS VÁZA porcelán HIBÁTLAN, Garancia!](https://www.vatera.hu/antik-1-oszt-herendi-apponyi-vert-green-av-mintas-vaza-porcelan-hibatlan-garancia-3524724029.html) | 24 500 Ft (≈ 71 USD) | 150 USD | 1–3 hónap | közepes | 90 USD | 3–8 hét, közepes–magas | 66 db, medián 110 USD (48–247) | **Ajánlott** | Kis haszon. Egészen kicsi Apponyi vázák eBay-en már 35–60 EUR-tól elérhetők, ezért a 17 cm-es méretet és az 1. osztályt emeld ki. |
| [Antik HERENDI APPONYI PURPUR (AP) mintás porcelán VÁZA Hibátlan, Garancia!](https://www.vatera.hu/antik-herendi-apponyi-purpur-ap-mintas-porcelan-vaza-hibatlan-garancia-3524920469.html) | 24 500 Ft (≈ 71 USD) | 150 USD | 1–3 hónap | közepes | 90 USD | 3–8 hét, közepes–magas | 66 db, medián 136 USD (75–245) | **Ajánlott** | Kis haszon, ugyanaz a logika, mint az AV vázánál. |
| [Antik HERENDI 1. oszt. APPONYI VERT GREEN (AV) mintás kosárfonott VÁZA porcelán HIBÁTLAN, Garancia!](https://www.vatera.hu/antik-herendi-1-oszt-apponyi-vert-green-av-mintas-kosarfonott-vaza-porcelan-hibatlan-garancia-3527536409.html) | 19 500 Ft (≈ 57 USD) | 130 USD | 1–3 hónap | közepes | 75 USD | 3–8 hét, közepes–magas | 66 db, medián 110 USD (48–247) | **Ajánlott** | Kis haszon. |
| [Nagyobb méretű ( 18 cm magas) herendi madár figura / hibátlan](https://www.vatera.hu/nagyobb-meretu-18-cm-magas-herendi-madar-figura-hibatlan-3464572610.html) | 22 800 Ft (≈ 66 USD) | 160 USD | 3–8 hét | közepes–magas | 85 USD | 2–6 hét, magas | 24 db, medián 160 USD (82–250) | **Ajánlott** | Kis abszolút haszon (kb. 20–90 USD). |
| [Herendi papagáj](https://www.vatera.hu/herendi-papagaj-3493102247.html) | 25 000 Ft (≈ 73 USD) | 140 USD | 1–3 hónap | közepes | 95 USD | 1–2 hónap, közepes | 52 db, medián 124 USD (89–299) | **Szűk árrés** | Kis herendi papagájok eBay-en 20–69 USD-ért is elkeltek, a 13 cm-es méretet emeld ki. |
| [RITKA Antik HERENDI SZENT LÁSZLÓ porcelán szobor Garancia, Hibátlan!!](https://www.vatera.hu/ritka-antik-herendi-szent-laszlo-porcelan-szobor-garancia-hibatlan-3527136749.html) | 14 500 Ft (≈ 42 USD) | 95 USD | 2–4 hónap | alacsony | 55 USD | 1–2 hónap, közepes–alacsony | nincs összehasonlítható | **Szűk árrés** | Nincs összehasonlítható hirdetés, szűk vevőkör. Kis tétel, kis haszon. |

### Catawiki (6 tétel)

| Tétel | Vatera ár | Kért becsérték | Becsült eladási idő ezen az áron | Likviditás ezen az áron | Minimálár | Eladási idő és likviditás a legkisebb áron | Aktív eBay-kínálat (db, medián, alsó–felső negyed) | Értékelés | Megjegyzés |
|---|---:|---:|---|---|---:|---|---|---|---|
| [Herendi Rothschild Új 6 sz étkészlet](https://www.vatera.hu/herendi-rothschild-uj-6-sz-etkeszlet-3491251307.html) | 899 000 Ft (≈ 2 276 EUR) | 4 500 EUR | 2–4 hét | közepes | 2 900 EUR | 2–4 hét, közepes–magas | nincs összehasonlítható | **Ajánlott** | Kézi besorolás: kiterjedt Rothschild étkészlet a Bonhamsnál 8 750 USD-ért kelt el, a Doyle 2025-ös becslése 6–8 ezer USD volt. Tőkeigényes. Ha a Catawikin nem éri el a minimálárat, darabonként eBay.com-on lassabban, de magasabb összértéken eladható. |
| [1F470 Antik Zsolnay porcelánfajansz váza családi jelzéssel ~1880](https://www.vatera.hu/1f470-antik-zsolnay-porcelanfajansz-vaza-csaladi-jelzessel-1880-3487243697.html) | 75 000 Ft (≈ 190 EUR) | 350 EUR | 2–4 hét | alacsony | 240 EUR | 2–4 hét, közepes | 62 db, medián 100 USD (42–330) | **Szűk árrés** | A korai családi jelzés gyűjtői érték, de 12 cm-es kis darab, az aktív antik Zsolnay vázák mediánja 100 USD. |
| [Herendi ANTIK 1890- 1900 6db tányér garnitúra](https://www.vatera.hu/herendi-antik-1890-1900-6db-tanyer-garnitura-3502089875.html) | 125 000 Ft (≈ 316 EUR) | 600 EUR | 2–4 hét | alacsony | 400 EUR | 2–4 hét, alacsony–közepes | 69 db, medián 149 USD (99–248) | **Szűk árrés** | Az aktív antik herendi tányérok darabonként 99–248 USD-ért vannak, a minta és a jelzés ismerete nélkül bizonytalan. Ha a licit nem éri el a minimálárat, újra kell indítani. |
| [Zsolnay eozin - Bordázott nagyváza -1930](https://www.vatera.hu/zsolnay-eozin-bordazott-nagyvaza-1930-3273802046.html) | 265 000 Ft (≈ 671 EUR) | 1 100 EUR | 2–4 hét | alacsony | 850 EUR | 2–4 hét, alacsony | 81 db, medián 283 EUR (164–580) | **Nem ajánlott** | Az aktív eozin vázák felső negyede 580 EUR, a minimálár ennél magasabb. Csak akkor érdemes, ha kiderül, hogy nagy és többszínű (a többszínű eozin sokszoros értékű lehet). |
| [Zsolnay eozin - Díszváza 1930](https://www.vatera.hu/zsolnay-eozin-diszvaza-1930-3274129457.html) | 220 000 Ft (≈ 557 EUR) | 950 EUR | 2–4 hét | alacsony | 710 EUR | 2–4 hét, alacsony | 81 db, medián 283 EUR (164–580) | **Nem ajánlott** | Mint a bordázott nagyváza: a méret és a színek ismerete nélkül a minimálár a piac felett van. |
| [Antik Zsolnay, Nikelszky szőlős váza](https://www.vatera.hu/antik-zsolnay-nikelszky-szolos-vaza-3526996043.html) | 220 000 Ft (≈ 557 EUR) | 1 000 EUR | 2–4 hét | alacsony | 710 EUR | 2–4 hét, alacsony | nincs összehasonlítható | **Nem ajánlott** | Jelzés nélküli, a Nikelszky-attribúció nem igazolt. A Catawiki valószínűleg nem fogadja be, és igazolt kereslet sincs. |

A díjak és a vámszabályok a 2026 elején ismert szintek, feltöltés előtt ellenőrizd őket az adott piactéren. A szállítási költséget mindenhol a vevőre hárítsd, és a nagy darabokat (levesestálak, 30 cm feletti vázák, étkészlet) dupla dobozban, biztosítással küldd. Az árak a hibátlan, a hirdetésben leírt állapotra vonatkoznak: ha átvételkor sérülést vagy eltérő jelzést találsz, az árat ahhoz kell igazítani.

### Források

- [PicClick – aktív eBay.com-hirdetések (pl. Herend Rothschild tureen)](https://picclick.com/?q=herend+rothschild+tureen)
- [PicClick – aktív eBay.de-hirdetések (pl. Zsolnay Eosin Vase)](https://picclick.de/?q=zsolnay+eosin+vase)
- [New Orleans Auction – Herend Rothschild Bird tureen, 1 722 USD](https://www.neworleansauction.com/auction-lot/herend-rothschild-bird-soup-tureen-and-tray_A7122D1BD8)
- [1stDibs – Herend tureens](https://www.1stdibs.com/buy/herend-tureen/)
- [Nehas China – Herend Queen Victoria tureen, új ár](https://www.nehaschina.com/herend-queen-victoria-soup-tureen-with-branch-2-qt-vbo-01014-0-02/)
- [Bonhams – Herend Rothschild Bird dinner service](https://bonhams.com/auctions/22504/lot/1594)
- [Doyle – Herend Rothschild Bird dinner service (2025)](https://doyle.com/auction/lot/lot-692---herend-porcelain-rothschild-bird-pattern-dinner-service/?lot=1432373&sd=1)
- [eBay – Herend jay 5072 eladás](https://www.ebay.com/itm/405914033871)
- [Bidsquare/Kodner – Herend Hadik Hussar 5526](https://www.bidsquare.com/online-auctions/kodner/herend-hadik-hussar-soldier-porcelain-figurine-5526-724102)
- [Herend – Hadik huszár új ár](https://herend.com/en/product/hadik-hussar-05526000C)
- [eBay – Herend Apponyi Purpur 7193 váza](https://www.ebay.com/itm/285472695468)
- [eBay – Herend parrot](https://www.ebay.com/shop/herend-parrot?_nkw=herend+parrot)
- [Darabanth – Herendi Lúdas Matyi (Lux Elek) aukció](https://www.darabanth.com/en/online-auction/333/categories~Porcelain-ceramics-glassware/Chinaware-Porcelain~500008/Herendi-porcelan-Ludas-Matyi-kezzel-festett-hibatlan-jelzett-Lux-Elek-m-20-cm-h-25-cm~II1861266/)
- [Toomey & Co. – Zsolnay eozin vázák, 1 703 USD](https://www.toomeyco.com/auctions/2023/11/keramics-rookwood-american-european-art-pottery/295)
- [Invaluable – Zsolnay árak](https://www.invaluable.com/blog/inside-the-archives-zsolnay-porcelain-prices/)
- [LiveAuctioneers – Zsolnay bison](https://www.liveauctioneers.com/price-result/zsolnay-pecs-hungary-buffalo-bison-porcelain-figurine/)
- [1stDibs – Zsolnay crayfish card tray](https://www.1stdibs.com/furniture/decorative-objects/bowls-baskets/decorative-dishes-vide-poche/zsolnay-pecs-crayfish-snake-card-tray-metallic-eosin-glaze/id-f_18353612)
- [eBay – Zsolnay Fighting Bears (Markup)](https://www.ebay.com/itm/326441674153)
- [WorthPoint – Zsolnay Pompadour dessert set](https://www.worthpoint.com/worthopedia/zsolnay-pompadour-dessert-set-plate-460736266)
- [eBay Community – sell-through arányok a gyűjtői kategóriában](https://community.ebay.com/t5/Selling/What-is-a-good-Listings-90-days-sold-ratio/td-p/33118576)

## Adatminőségi korlátok

- A scraper `description` mezője a hirdetés leírása helyett az oldal kategóriamenüjét menti. A válogatott tételek leírását ezért közvetlenül a letöltött oldalak „Eladó leírása” és „Termék sajátosságai” blokkjából olvastam ki. Javítás kell a `porcelan/parsing.py` `extract_description` függvényébe.
- A minta-, sérülés- és gyanújelzések (*minta*, *sérülés*, *gyanú*) a teljes oldalszövegből jönnek, beleértve az ajánlósávot is. Ezért zajosak: pl. a „viktoria” vagy a „repedes” sok olyan hirdetésnél megjelenik, amelyre nem vonatkozik. A típusonkénti listákban tájékoztató jellegűek.
- Néhány nem porcelán tétel is átment a szűrőn (pl. „Pécs, Zsolnay kút” képeslapok, Zsolnay-emlékérmék, szakkönyv), mert a címük nem tartalmaz kizáró szót. Ezek a válogatásba nem kerültek be.
- Aukcióknál az ár a kikiáltási ár. Az aktuális licitet és a licitszámot a parser nem mindig olvassa ki megbízhatóan, ezért a linken ellenőrizendő.

---

A becsült nyugati árak szakértői becslések, nem valós idejű piaci adatok. Nagy értékű vásárlás előtt érdemes eBay „sold” listákkal és a hirdetés fotóival (jelzés, sérülés) ellenőrizni.
