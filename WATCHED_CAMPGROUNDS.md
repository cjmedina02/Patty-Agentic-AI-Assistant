# Watched Campgrounds

**Home zip:** 92126 (Mira Mesa, San Diego)
**Max distance:** 800 miles
**Checks every:** 15 minutes via Azure Functions
**Notifies:** Discord webhook on new tent site openings

---

## ReserveCalifornia (10 campgrounds)

| # | Campground | PlaceId | ~Distance |
|---|---|---|---|
| 1 | Doheny State Beach | 639 | 49 mi |
| 2 | South Carlsbad State Beach | 720 | 17 mi |
| 3 | Idyllwild / Mt San Jacinto SP | coord (33.7631, -116.7364) | 62 mi |
| 4 | San Elijo State Beach | 709 | 20 mi |
| 5 | Leo Carrillo State Beach | 665 | 95 mi |
| 6 | Crystal Cove State Park | 635 | 75 mi |
| 7 | Palomar Mountain SP | 687 | 55 mi |
| 8 | Anza-Borrego Desert SP | 2 | 80 mi |
| 9 | D.L. Bliss SP (Lake Tahoe) | 637 | 450 mi |
| 10 | Emerald Bay SP (Lake Tahoe) | 641 | 449 mi |

---

## Recreation.gov (10 campgrounds)

| # | Campground | Facility ID | ~Distance |
|---|---|---|---|
| 11 | Fern Basin CG (Idyllwild, San Bernardino NF) | 231969 | 65 mi |
| 12 | Marion Mountain CG (Idyllwild, San Bernardino NF) | 231973 | 65 mi |
| 13 | Serrano CG (Big Bear, San Bernardino NF) | 232250 | 110 mi |
| 14 | Black Rock CG (Joshua Tree NP) | 232473 | 130 mi |
| 15 | Indian Cove CG (Joshua Tree NP) | 232472 | 145 mi |
| 16 | Jumbo Rocks CG (Joshua Tree NP) | 272300 | 155 mi |
| 17 | Cottonwood CG (Joshua Tree NP) | 272299 | 175 mi |
| 18 | Lodgepole CG (Sequoia NP) | 232461 | 290 mi |
| 19 | Dorst Creek CG (Sequoia NP) | 232460 | 295 mi |
| 20 | Potwisha CG (Sequoia NP) | 249979 | 280 mi |

---

## Notes

- ReserveCalifornia campgrounds use the Tyler/RDR API (`california-rdr.prod.cali.rd12.recreation-management.tylerapp.com`)
- Recreation.gov campgrounds use the RIDB API (`recreation.gov/api/camps/availability`)
- Tent/standard sites only — RV, hookup, electric, cabin, group, and yurt sites are excluded
- Discord notification fires only on **new** openings (dates not seen in the previous check)
- To add more campgrounds, update `WATCHED_CAMPGROUNDS` in `src/react_agent/campsite_agent.py`
