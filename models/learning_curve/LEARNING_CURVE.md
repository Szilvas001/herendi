# Tanulási görbe – mennyi adat kell?

Készült: 2026-09-28T15:06:43+00:00. Teszthalmaz: csoportszintű véletlen (a megfigyelések csak 3 napot fednek le; időbeli teszt nem lehetséges).

| Változat | Piac | Tanítósor | Tesztminta | MdAPE | MAE | 80%-os lefedettség |
|---|---|---:|---:|---:|---:|---:|
| csak Herendi/Zsolnay | HU | 128 | 246 | 60.0% | 46 181 | 79% |
| csak Herendi/Zsolnay | US | 5 | 19 | 86.4% | 481 | 84% |
| csak Herendi/Zsolnay | HU | 308 | 246 | 55.0% | 46 101 | 71% |
| csak Herendi/Zsolnay | US | 15 | 19 | 75.0% | 463 | 84% |
| csak Herendi/Zsolnay | HU | 603 | 246 | 48.5% | 43 762 | 74% |
| csak Herendi/Zsolnay | US | 35 | 19 | 75.9% | 448 | 79% |
| csak Herendi/Zsolnay | HU | 1167 | 246 | 44.1% | 40 567 | 76% |
| csak Herendi/Zsolnay | US | 84 | 19 | 73.3% | 453 | 68% |

## Extrapoláció (MdAPE ≈ a·n^(−b) + c)

- HU/hz_only: a=1.21, b=0.142, aszimptota c=0.0% → ~6 211 tanítósor kellene 35% MdAPE-hez
- US/hz_only: MEGBÍZHATATLAN extrapoláció (tesztminta 19, legfeljebb 84 tanítósor) – nincs értelmes becslés.

Extrapoláció kevés pontból: nagyságrendi becslés, nem ígéret.
