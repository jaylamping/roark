# Sourcing: lines DigiKey could not supply on 2026-11-10

Part numbers for every kit line are in [kit-2sets.csv](kit-2sets.csv) (and fab/bom-digikey.csv). This page covers the lines
that were out of stock at DigiKey on 2026-11-10, with the same part at Mouser. The ICs are not substituted.

**Check every Mouser figure live before ordering.** The LM5069-1, LM5069-2 and SM08B-GHS-TB rows were checked live on
the distributors' pages on 2026-11-10 and say so. The other Mouser figures are unverified: Mouser's product pages could
not be loaded from here (timeouts, refused connections, a bot check), so they come from cached search snippets of
unknown age, and some carry on-order dates already past. TI.com shows its stock only after login. The DigiKey column is from DigiKey's own pages on
2026-11-10.

| Part (refs) | DigiKey status | Mouser PN | Mouser stock / due (cached snippet) | TI.com |
|---|---|---|---|---|
| LM5069MMX-1/NOPB (main U1) | 0; 3,500 due 01-Mar-2027 (LM5069MM-1/NOPB also out) | not recorded | **Checked live 2026-11-10, LM5069MM-1/NOPB:** Mouser 0 in stock, 583 due 24-May-2027 and 40,000 due 23-Sep-2027, lead time 26 weeks. Arrow out; TI.com "not available"; LCSC C486026 out of stock; RS, TME and element14 0. Only brokers list stock (Win Source 3,490, UnikeyIC 3,500, Hi-Tech Circuit 1,396). **The latching LM5069-1 cannot be bought from an authorised source today.** | not available |
| LM5069MMX-2/NOPB (main U7) | 0; 2,894 due 11-Jan-2027 (MM-2 also out) | not recorded | **Checked live 2026-11-10:** Mouser LM5069MM-2/NOPB 51 in stock (6,000 due 1-Feb-2027); LCSC C2653582 (LM5069MMX-2/NOPB) 3,156 in stock at $4.44 each | login required |
| INA237AIDGSR (main U11,U12,U13,U17; buck U2,U4; 6 per set) | 0; 2,500 due 25-Nov-2026 | 595-INA237AIDGSR | 15,128 in stock, but the snippet notes the page is about 511 days old. Lead time 43 wk | login required |
| TPS3431SDRBR (main U25) | 0; 3,000 due 08-Mar-2027 | 595-TPS3431SDRBR | US: 58 in stock, 6,000 on order "10/16/2026" (stale); series page 4,373; AU 2,639 (stale). Lead time 12 wk | login required |
| LM5146RGYR (buck U1) | 0; 2,758 due 18-Jan-2027 (LM5146QRGYRQ1 also out) | not confirmed (Mouser product page exists; 595- prefix assumed, not verified) | US/AU: 3,312 in stock; UK: 0 with 5,395 on order. Lead time 12–20 wk | login required |
| JST SM08B-GHS-TB(LF)(SN) (main J20,J21) | 0; 2,500 due 18-Jan-2027 | not recorded | **Checked live 2026-11-10:** Mouser 975 in stock, 17,500 due 22-Dec-2026; LCSC C265111 26,635 in stock | n/a |
| Vishay WSK25125L000FEA (main RS9; buck RS2) | 0; 2,000 due 28-Dec-2026 | 71-WSK25125L000FEA | eu.mouser: 10,481 in stock (cut tape) | n/a |
| Panasonic EEE-TK2A470AQ (buck C2, replaced) | rechecked: 0; 200 due 24-Sep-2027; 37 wk | not found at Mouser | Replaced by Chemi-Con EMVH101ARA470MKE0S on a 12.5 mm footprint (the TK part is 12.5 × 13.5, not 10 × 10) | n/a |
| Panasonic EEH-ZA1E331P (buck C24) | rechecked: 0; 500 due 30-Apr-2027; 37 wk | 667-EEH-ZA1E331P | 11,012 in stock in one snapshot, 103 in another. Lead time 14 wk. (EEH-ZA1E331V: DigiKey 52 in stock, see B3) | n/a |
| Coilcraft XAL1010-682MED (buck L2) | "No longer available at DigiKey" | not confirmed | QuickView about 6,967 in stock. Also Farnell 2289019 (923 cached) and Coilcraft direct | n/a |
| MG Chemicals 419D-55ML (consumable) | DigiKey no longer carries MG Chemicals coatings | 590-419D-55ML | Listed, "Shipping Restricted"; stock not visible. TestEquity 10001234-419D-55ML, US$18.88 | n/a |

Quantities for two sets, no spares: LM5069-1 ×2, LM5069-2 ×2, INA237 ×12, TPS3431 ×2, LM5146 ×2, SM08B-GHS-TB ×4,
WSK25125L000FEA ×4, C2 ×2, C24 ×2, L2 ×2.

Checked live: **LM5069-1 (U1, latch-off) has no authorised stock anywhere** (Mouser's next 583 are due 24-May-2027);
LM5069-2 is in stock at Mouser (51, small reel) and LCSC (3,156, large reel); SM08B-GHS-TB is in stock at Mouser (975) and
LCSC (26,635). On the cached, unverified figures, Mouser covers INA237, LM5146, the 5 mΩ WSK2512, EEH-ZA1E331P and
XAL1010-682MED from stock; TPS3431 showed small stock. C24 is EEH-ZA1E331V (in stock at DigiKey; kit note gives the fit).
C2 is EMVH101ARA470MKE0S (decided; the buck board is laid out for it). What fitting LM5069-2 in U1's place would mean:
[LM5069_RETRY.md](LM5069_RETRY.md).
