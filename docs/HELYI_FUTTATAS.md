# Adatgyűjtés futtatása a saját gépen (útmutató a helyi Claude-nak)

Ez az útmutató annak a helyi (asztali) Claude Code-nak szól, amely a felhasználó saját Windows-gépén futtatja a Herendi–Zsolnay vételkereső adatgyűjtését. A lépéseket sorban hajtsd végre, és a végén jelentsd az eredményt (lásd „Mit kell visszajelezni”).

## Miért a saját gépen

A Vatera a felhős adatközponti IP-címekről érkező kéréseket AWS WAF bot-ellenőrzésre küldi (HTTP 202, `x-amzn-waf-action: challenge`), a felhasználó otthoni gépéről viszont kiszolgálja az oldalakat. A kód mindenhol ugyanaz, a különbség csak a hálózati hely.

**Szabály:** ha a Vatera nálad is kihívást (CAPTCHA, WAF challenge, 403, 429) ad, a crawler `blocked` állapotban leáll. Ezt ne próbáld megkerülni (se böngészőautomatizálással, se a kihívás megoldásával, se proxyval). Jelezd a felhasználónak, és várj.

## 1. Előfeltételek

- Windows 10/11, **Python 3.11 vagy újabb** (`python --version`), **Git** (`git --version`).
- Kb. 5 GB szabad hely (torch + CLIP-súlyok + képek).
- Internetkapcsolat. GPU nem kell.

## 2. Telepítés (PowerShell)

```powershell
cd $HOME\Documents
git clone https://github.com/Szilvas001/herendi.git
cd herendi
git checkout claude/pensive-hopper-vbd0td
git pull

python -m venv .venv
.\.venv\Scripts\Activate.ps1
# ha a szkriptfuttatás tiltott: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

python -m pip install --upgrade pip
# csak CPU-s torch (kisebb, GPU nélkül is fut):
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

python -m porcelan setup-models      # CLIP-súlyok (~600 MB, GitHub, SHA-256 ellenőrzés)
python -m pytest -q tests            # mind zöld kell legyen (hálózat nélküli tesztek)
```

## 3. Kezdő adatok importja

```powershell
python -m porcelan import-repo       # a repóban lévő 2026-09-i Vatera-adatok (2321 hirdetés)
```

## 4. Próbafutás a Vaterán (5 kérés)

```powershell
python -m porcelan crawl --source vatera --no-resume --max-requests 5
```

Értelmezés:
- `"status": "interrupted"` és `"index_pages"` > 0: **működik**, jöhet a teljes gyűjtés.
- `"status": "blocked"`: a Vatera bot-ellenőrzést adott. Állj meg, és jelezd (lásd a szabályt fent).
- `"status": "failed"`, hálózati hiba: ellenőrizd az internetkapcsolatot.

## 5. Teljes gyűjtés

```powershell
# Herendi/Zsolnay kínálat: 55 névváltozat, teljes lapozás, termékoldalak, képek URL-jei.
# Udvarias tempó (1,5 s/kérés), több óráig tarthat. Megszakítható (Ctrl+C), újraindításkor folytatja.
python -m porcelan crawl --source vatera

# Általános porcelán/kerámia korpusz az előtanításhoz (kártyaszintű kép + ár)
python -m porcelan crawl --source vatera --corpus general

# Hivatalos herend.com katalógus: az azonosításhoz kell, ár nincs benne (kb. 1,5 óra)
python -m porcelan crawl-catalog

# Képek letöltése, duplikátumszűrés, CLIP-beágyazás, képi előszűrés
python -m porcelan images

# Pontos termékazonosítás (formaszám + mintakód) szövegből és képből
python -m porcelan identify

# Állapot és mennyiség
python -m porcelan status
python -m porcelan data-volume
```

Opcionális: tömeges eBay-gyűjtés (amerikai piac), ha a felhasználó ad eBay API-kulcsot (developer.ebay.com, Production keyset):

```powershell
$env:EBAY_CLIENT_ID="..."; $env:EBAY_CLIENT_SECRET="..."
python -m porcelan harvest-ebay --images
```

A Jófogás adapter ki van kapcsolva (`config/settings.example.toml`, `[jofogas] enabled = false`). Csak akkor kapcsold be, ha a felhasználó kéri.

## 6. Napi ismétlés (fontos a piaci árhoz)

A valódi piaci árhoz **lezárult aukciók záró licitjei** kellenek. Ezeket a crawler akkor rögzíti, ha egy aukció lejárta után újra lefut. Ezért naponta egyszer futtatni kell. Hozz létre egy ütemezett feladatot:

```powershell
$dir = (Get-Location).Path
$cmd = "cd `"$dir`"; .\.venv\Scripts\python.exe -m porcelan crawl --source vatera; .\.venv\Scripts\python.exe -m porcelan images; .\.venv\Scripts\python.exe -m porcelan identify; .\.venv\Scripts\python.exe -m porcelan score"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -Command $cmd"
$trigger = New-ScheduledTaskTrigger -Daily -At 3am
Register-ScheduledTask -TaskName "HerendiVatera" -Action $action -Trigger $trigger -Description "Herendi-Zsolnay napi Vatera-gyűjtés"
```

(A gépnek 3-kor bekapcsolva kell lennie; ha nem, válassz más időpontot.)

## 7. Tanítás és mérés (ha már van elég adat)

```powershell
python -m porcelan train             # új modellverzió + értékelés: models\<verzió>\EVALUATION.md
python -m porcelan sku-eval          # ±10%-os cél: cikkszám-szintű pontosság, piaci zajszint
python -m porcelan learning-curve    # hogyan javul a hiba az adatmennyiséggel
python -m porcelan score             # becslések a dashboardhoz
python -m porcelan serve             # dashboard: http://127.0.0.1:8000
```

## 8. Mit kell visszajelezni a felhasználónak

1. A próbafutás eredménye (`status`, `index_pages`, esetleges hibaüzenet).
2. A teljes gyűjtés után a `python -m porcelan status` kimenetéből: a `crawl` → `vatera` → `status`, `coverage` (a „RÉSZLEGES” felirat azt jelenti, hogy nem ért minden keresés a lapozás végére), és a hirdetésszámok.
3. A `python -m porcelan data-volume` kimenete: képes Herendi/Zsolnay rekordok, realizált árak.
4. Ha tanítás is volt: a `models\<verzió>\EVALUATION.md` „Státusz” sora és a „Pontos termék → pontos piaci ár” szakasz.

## 9. Az adatok visszaadása a felhős munkamenetnek

Az adatbázis nincs verziókezelve (`data/` a `.gitignore`-ban). Két lehetőség:
- **A:** a felhasználó feltölti a `data\hzfinder.sqlite` fájlt (és ha kell, a `data\images` mappát tömörítve) oda, ahonnan a felhős munkamenet eléri.
- **B:** a tanítás nálad fut (7. lépés), és az új modellverziót commitolod és pusholod ugyanerre az ágra:
  ```powershell
  git add models
  git commit -m "Modell helyi, élő Vatera-adaton"
  git push origin claude/pensive-hopper-vbd0td
  ```

## Hibaelhárítás

| Tünet | Teendő |
|---|---|
| `blocked` / challenge / 403 / 429 | Állj meg, jelezd a felhasználónak; ne kerüld meg. Később (órák/nap) újrapróbálható, a futás folytatódik. |
| `ModuleNotFoundError` | Aktív-e a venv (`.\.venv\Scripts\Activate.ps1`), lefutott-e a `pip install -r requirements.txt`. |
| `faiss` telepítési hiba | Kihagyható; a program nélküle is fut (lassabb keresés). |
| A futás megszakadt | Egyszerűen indítsd újra ugyanazt a parancsot: a félbemaradt bejárást folytatja. Friss bejáráshoz: `--no-resume`. |
| Lassú | Normális: kérésenként 1,5 s szünet (`config/settings.toml`, `[http] min_delay_sec`). Ne csökkentsd 1 s alá. |
