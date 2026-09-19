# Hungarian Finds dashboard

Nyisd meg az `index.html` fájlt a böngészőben. Nincs telepítés, szerver vagy API-kulcs.
Alternatíva a repó gyökeréből: `python -m http.server 8080 --bind 127.0.0.1`, majd `http://127.0.0.1:8080/dashboard/`.

Új riport: `python -m elemzes.export_dashboard`. Az igazságforrás a `riport/hungarian-top3.json`; az `app.js` a felhasználó által módosított feltételekkel újraszámol. Nem ment felhasználói adatot, nem végez vásárlást.

## SaaS-alap és élesítés

Ez működő kutatási dashboard-prototípus, nem kész előfizetéses SaaS. A GitHub a forráskódot tárolja; a push nem kapcsol be webhostingot.

Javasolt szolgáltatás: felhasználónként mentett keresések, költségprofilok és ellenőrizhető exportjelöltek. Élesítéshez szükséges:

1. API és adatbázis: users, searches, runs, listings, observations, comparables, decisions táblák; minden felhasználói erőforráson tulajdonos-ellenőrzés. Megfigyelések időbélyeggel, nem felülírt aktuális árként.
2. OIDC-bejelentkezés szerveroldali munkamenettel; HttpOnly/Secure/SameSite cookie, CSRF-védelem, kulcsok csak szerveroldalon. A statikus demóban nincs hitelesítés.
3. Háttérfeladatok futásonkénti idő-, kérés- és költségkerettel, hostonkénti sebességkorláttal. 403/429/CAPTCHA esetén leállás, nem megkerülés. Forrásonként engedélyezett API vagy feldolgozás; részleges futás külön állapot.
4. Modell/dekor/méret/állapot szerinti összehasonlítás, külön aktív és lezárt rekordokkal. Idő-előrejelzés csak megfigyelt hirdetési és lezárási időkből, cenzorált, még aktív tételekkel is validálva. Törölt hirdetés nem automatikusan eladott.
5. Előfizetés szolgáltatói checkouttal, ellenőrzött webhook-aláírással és idempotenciával; keretek szerveroldali kikényszerítése. E-mail-értesítés opt-in alapon.
6. TLS hosting, mentés/visszaállítás, naplózás személyes adatok nélkül, tenant-szigetelési tesztek. Csak ezek után fizetős szolgáltatásként indítható.

## Kutatási korlát

A három jelölt egyikének sincs öt pontosan illesztett lezárt eladása. A felület ezért nem ígér biztos profitot vagy gyors eladást. Az ár- és időforgatókönyv a kereskedői döntés előkészítésére való.
