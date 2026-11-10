# Sourcing: lines DigiKey could not supply on 2026-11-10

Part numbers for every kit line are in [kit-2sets.csv](kit-2sets.csv) (and fab/bom-digikey.csv). This page covers the lines
that were out of stock at DigiKey on 2026-11-10, with the same part at Mouser. The ICs are not substituted.

**Check every Mouser figure live before ordering.** Mouser's product pages could not be loaded from here (timeouts,
refused connections, a bot check), so the Mouser column is from cached search snippets of unknown age, and some carry
on-order dates already past. TI.com shows its stock only after login. The DigiKey column is from DigiKey's own pages on
2026-11-10.

| Part (refs) | DigiKey status | Mouser PN | Mouser stock / due (cached snippet) | TI.com |
|---|---|---|---|---|
| LM5069MMX-1/NOPB (main U1) | 0; 3,500 due 01-Mar-2027 (LM5069MM-1/NOPB also out) | 926-LM5069MMX-1/NOPB (aggregator listing) | US: 0, 12,475 on order "8/20/2026" (stale); EU site: 543 in stock; AU: 0, 4,295 on order. Factory lead time 16 wk. The US snippet showed LM5069MM-1/NOPB (small reel) in stock | login required |
| LM5069MMX-2/NOPB (main U7) | 0; 2,894 due 11-Jan-2027 (MM-2 also out) | 926-LM5069MMX-2/NOPB (search summary; not seen on a product page) | Snapshots disagree: US 81 in stock with on-order dates 9/3–10/29/2026 (stale), another US 0; AU: 32,808 expected 17-Dec-2026. Lead time 16 wk | login required |
| INA237AIDGSR (main U11,U12,U13,U17; buck U2,U4; 6 per set) | 0; 2,500 due 25-Nov-2026 | 595-INA237AIDGSR | 15,128 in stock, but the snippet notes the page is about 511 days old. Lead time 43 wk | login required |
| TPS3431SDRBR (main U25) | 0; 3,000 due 08-Mar-2027 | 595-TPS3431SDRBR | US: 58 in stock, 6,000 on order "10/16/2026" (stale); series page 4,373; AU 2,639 (stale). Lead time 12 wk | login required |
| LM5146RGYR (buck U1) | 0; 2,758 due 18-Jan-2027 (LM5146QRGYRQ1 also out) | not confirmed (Mouser product page exists; 595- prefix assumed, not verified) | US/AU: 3,312 in stock; UK: 0 with 5,395 on order. Lead time 12–20 wk | login required |
| JST SM08B-GHS-TB(LF)(SN) (main J20,J21) | 0; 2,500 due 18-Jan-2027 | not confirmed (Mouser product page exists, JST-Commercial) | 0 in stock; 42,500 on order (17,500 expected 15-Dec-2026). Lead time 16 wk | n/a |
| Vishay WSK25125L000FEA (main RS9; buck RS2) | 0; 2,000 due 28-Dec-2026 | 71-WSK25125L000FEA | eu.mouser: 10,481 in stock (cut tape) | n/a |
| Panasonic EEE-TK2A470AQ (buck C2) | rechecked: 0; 200 due 24-Sep-2027; 37 wk | not found at Mouser | No Mouser listing found. See B1: the part is 12.5 × 13.5 and the footprint is 10 × 10; use EMVH101ARA470MKE0S | n/a |
| Panasonic EEH-ZA1E331P (buck C24) | rechecked: 0; 500 due 30-Apr-2027; 37 wk | 667-EEH-ZA1E331P | 11,012 in stock in one snapshot, 103 in another. Lead time 14 wk. (EEH-ZA1E331V: DigiKey 52 in stock, see B3) | n/a |
| Coilcraft XAL1010-682MED (buck L2) | "No longer available at DigiKey" | not confirmed | QuickView about 6,967 in stock. Also Farnell 2289019 (923 cached) and Coilcraft direct | n/a |
| MG Chemicals 419D-55ML (consumable) | DigiKey no longer carries MG Chemicals coatings | 590-419D-55ML | Listed, "Shipping Restricted"; stock not visible. TestEquity 10001234-419D-55ML, US$18.88 | n/a |

Quantities for two sets, no spares: LM5069-1 ×2, LM5069-2 ×2, INA237 ×12, TPS3431 ×2, LM5146 ×2, SM08B-GHS-TB ×4,
WSK25125L000FEA ×4, C2 ×2, C24 ×2, L2 ×2.

On the cached figures, Mouser covers INA237, LM5146, the 5 mΩ WSK2512, EEH-ZA1E331P and XAL1010-682MED from stock;
LM5069-1/-2 and SM08B-GHS-TB look backordered there too (Mouser EU showed LM5069MMX-1 in stock); TPS3431 showed small stock.
C24 is now EEH-ZA1E331V (in stock at DigiKey; kit note gives the fit). C2 needs a decision: the kit note gives the
proposed replacement and the footprint change it needs.
