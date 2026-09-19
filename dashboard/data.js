window.REPORT = {
  "checked_at": "2026-09-19T19:41:14+00:00",
  "warning": "Három ellenőrizendő exportjelölt, nem három igazolt nagy likviditású vétel. A ROI feltételes költségszámítás; az eladási ár és idő alacsony bizonyosságú forgatókönyv. Lezárt, pontosan összehasonlítható nyugati eladások hiányában az alulárazottság nincs bizonyítva.",
  "method": "Időkorlátos élő Vatera-gyűjtés, termékoldalas ellenőrzés és kézi forrásértékelés. A dashboard a kiinduló árral számol; nincs feltételezett alku. Külön fizetős LLM API-hívás nem történt.",
  "coverage": {
    "search_terms": 12,
    "pages_per_term": 2,
    "candidates": 482,
    "detail_requests": 30,
    "live_http_requests": 54,
    "failed_http_requests": 0,
    "runtime_seconds": 112.1,
    "budget_seconds": 210,
    "other_markets": "Jófogás és Galéria Savaria: csak webes kutatás, ellenőrzött shortlist nélkül",
    "verified_comparable_sales": 0
  },
  "items": [
    {
      "name": "Zsolnay birkózó medvék, 30 cm",
      "brand": "Zsolnay",
      "url": "https://www.vatera.hu/as979-regi-zsolnay-porcelan-szobor-figura-birkozo-marakodo-medve-par-3430331234.html",
      "purchase_huf": 12990,
      "checked_at": "2026-09-19: élő termékoldal, 12 990 Ft, készletjelzés; az állapot nem függetlenül ellenőrzött.",
      "sale_eur": {
        "stress": 90,
        "base": 150,
        "high": 220
      },
      "costs_huf": {
        "inbound": 2000,
        "packaging": 5000,
        "outbound": 12000,
        "testing": 3000
      },
      "days": "90–180",
      "days_high": "180–365+",
      "thesis": "Magyar gyűjtői tárgy, alacsony hazai belépőárral. A 30 cm-es változatnál a csomagolás és biztosított szállítás döntő; először EU-s eladást érdemes vizsgálni.",
      "condition": "Az eladó 30 cm-t és fellelt állapotot ír. Nincs kifejezett hibátlansági garancia: talp, mancsok, ragasztás, repedés, átfestés, jelzés és pontos modell fotós/személyes ellenőrzése kell. A 16 500 Ft-os másik medvénél talpcsorbulás szerepel, ezért annak állapota nem tekinthető hibátlan összehasonlításnak.",
      "price_basis": "A 90/150/220 EUR munkahipotézis, nem ellenőrzött nyugati piaci ársáv. Az aktív hazai 32 500 Ft-os Markup-hirdetés kínálati ár, nem eladás; a festés, méret és állapot egyezése nincs igazolva. A régi riport 350 EUR értékét nem vettük át. Ár- és likviditási bizonyíték nélkül csak további kutatásra.",
      "sources": [
        {
          "label": "Vatera — konkrét 12 990 Ft-os tétel",
          "url": "https://www.vatera.hu/as979-regi-zsolnay-porcelan-szobor-figura-birkozo-marakodo-medve-par-3430331234.html",
          "kind": "élő beszerzési hirdetés"
        },
        {
          "label": "Vatera — Markup Béla medvék, 32 500 Ft",
          "url": "https://www.vatera.hu/antik-zsolnay-birkozo-medvek-markup-bela-porcelan-szobor-garancia-hibatlan-3528589049.html",
          "kind": "hazai kínálati összevetés; nem lezárt eladás"
        }
      ],
      "computed_eu": {
        "stress": {
          "profit_huf": -9394,
          "roi_pct": -26.8,
          "capital_huf": 34990,
          "max_purchase_huf": 0
        },
        "base": {
          "profit_huf": 7670,
          "roi_pct": 21.9,
          "capital_huf": 34990,
          "max_purchase_huf": 10815
        },
        "high": {
          "profit_huf": 27578,
          "roi_pct": 78.8,
          "capital_huf": 34990,
          "max_purchase_huf": 26129
        }
      },
      "computed_us_base": {
        "profit_huf": -7330,
        "roi_pct": -14.7,
        "capital_huf": 49990,
        "max_purchase_huf": 0
      }
    },
    {
      "name": "Tungsram ECC83 / 12AX7, két cső",
      "brand": "Tungsram",
      "url": "https://www.vatera.hu/2db-ecc83-tungsram-legolcsobb-3530289641.html",
      "purchase_huf": 8500,
      "checked_at": "2026-09-19: élő termékoldal, 8 500 Ft, készletjelzés; az eladó csak a fűtőszálat mérte.",
      "sale_eur": {
        "stress": 45,
        "base": 100,
        "high": 125
      },
      "costs_huf": {
        "inbound": 2000,
        "packaging": 1500,
        "outbound": 6000,
        "testing": 6000
      },
      "days": "30–90",
      "days_high": "90–180+",
      "thesis": "Magyar gyártású audiocső; kis csomag és nemzetközi erősítőalkatrész-piac. A három közül ennek érdemes először a működését mérni, mert a sikeres vizsgálat eldöntheti, van-e egyáltalán eladható érték.",
      "condition": "Csak fűtőszálmérés történt. Személyes átvételnél hozott csőteszterrel mérhető. Külön gyártási kódok; nem igazolt matched pár és nem igazolt NOS. Mindkét triódarendszer emissziója, meredeksége, szivárgása, zaja és mikrofonikussága ellenőrizendő. Hibás csőnél a 45 EUR stresszár sem biztos; teljes leírási veszteség is lehetséges.",
      "price_basis": "A NOS Tube Store 145 EUR kínálati árat mutat mért, párosított NOS párra. A 100 EUR alapeset ettől lefelé eltérő, sikeres tesztet feltételező munkahipotézis, nem ugyanazon minőség igazolt eladási ára. A 45 EUR stresszérték működő, gyengébb/nem párosított darabokra is csak feltevés. Az ár nem bizonyít likviditást.",
      "sources": [
        {
          "label": "Vatera — két Tungsram ECC83",
          "url": "https://www.vatera.hu/2db-ecc83-tungsram-legolcsobb-3530289641.html",
          "kind": "élő beszerzési hirdetés, vizsgálati korlátokkal"
        },
        {
          "label": "NOS Tube Store — Tungsram ECC83",
          "url": "https://www.nostubestore.com/2010/04/tungsram-ecc8312ax7cv8156b339.html",
          "kind": "145 EUR/matched pár kínálati ár; eltérő minőség; nem realizált eladás"
        }
      ],
      "computed_eu": {
        "stress": {
          "profit_huf": -11202,
          "roi_pct": -46.7,
          "capital_huf": 24000,
          "max_purchase_huf": 0
        },
        "base": {
          "profit_huf": 4440,
          "roi_pct": 18.5,
          "capital_huf": 24000,
          "max_purchase_huf": 6376
        },
        "high": {
          "profit_huf": 11550,
          "roi_pct": 48.1,
          "capital_huf": 24000,
          "max_purchase_huf": 11846
        }
      },
      "computed_us_base": {
        "profit_huf": -10560,
        "roi_pct": -27.1,
        "capital_huf": 39000,
        "max_purchase_huf": 0
      }
    },
    {
      "name": "Herendi nyúlpár, 5324, 4,2 cm",
      "brand": "Herendi",
      "url": "https://www.vatera.hu/1d781-regi-herendi-porcelan-nyul-nyuszi-par-5-cm-3487242653.html",
      "purchase_huf": 7800,
      "checked_at": "2026-09-19: élő termékoldal, 7 800 Ft, készletjelzés; az eladó hibátlannak írja.",
      "sale_eur": {
        "stress": 40,
        "base": 75,
        "high": 110
      },
      "costs_huf": {
        "inbound": 2000,
        "packaging": 2500,
        "outbound": 6500,
        "testing": 1500
      },
      "days": "60–180",
      "days_high": "180–365+",
      "thesis": "Kis méretű, alacsony vételárú magyar porcelán. A tárgy azonosíthatósága jobb a megadott 5324 formaszám miatt, de a csekély értéket a külföldi szállítás könnyen felemészti.",
      "condition": "Eladói adatok: 5324 formaszám, 4,8 cm szélesség, 4,2 cm magasság, kb. 50 g, mélynyomott HEREND jelzés. Hibátlan állapot állítása ellenőrizendő. A dekor/szín nincs megbízhatóan kinyerve, ezért nem sorolható fishnet prémium kategóriába. Fülek és talp személyes ellenőrzése fontos.",
      "price_basis": "A 40/75/110 EUR nem kalibrált forgatókönyv. Az USA eBayen látott 380 USD-s Herend nyúl MPN-je SVH-15585-0-00, rust fishnet; más forma és dekor, ezért kizárt ár-összehasonlítás. Ebből a 5324 értékére nem következtetünk. A konkrét 5324 kivitel nyugati realizált ára jelenleg hiányzik.",
      "sources": [
        {
          "label": "Vatera — Herendi 5324 nyúlpár",
          "url": "https://www.vatera.hu/1d781-regi-herendi-porcelan-nyul-nyuszi-par-5-cm-3487242653.html",
          "kind": "élő beszerzési hirdetés"
        },
        {
          "label": "eBay — eltérő rust fishnet nyúl",
          "url": "https://www.ebay.com/itm/133001538909",
          "kind": "kizárt összehasonlítás: más forma/dekor; 380 USD kínálati ár"
        }
      ],
      "computed_eu": {
        "stress": {
          "profit_huf": -8924,
          "roi_pct": -44.0,
          "capital_huf": 20300,
          "max_purchase_huf": 0
        },
        "base": {
          "profit_huf": 1030,
          "roi_pct": 5.1,
          "capital_huf": 20300,
          "max_purchase_huf": 3907
        },
        "high": {
          "profit_huf": 10984,
          "roi_pct": 54.1,
          "capital_huf": 20300,
          "max_purchase_huf": 11564
        }
      },
      "computed_us_base": {
        "profit_huf": -13970,
        "roi_pct": -39.6,
        "capital_huf": 35300,
        "max_purchase_huf": 0
      }
    }
  ]
};
