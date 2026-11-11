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

Quantities for two sets, no spares: LM5069-2 ×4 (U1 temporary fit and U7; LM5069-1 ×2 later), INA237 ×12, TPS3431 ×2, LM5146 ×2, SM08B-GHS-TB ×4,
WSK25125L000FEA ×4, C2 ×2, C24 ×2, L2 ×2.

Checked live: **LM5069-1 (U1, latch-off) has no authorised stock anywhere** (Mouser's next 583 are due 24-May-2027);
LM5069-2 is in stock at Mouser (51, small reel) and LCSC (3,156, large reel); SM08B-GHS-TB is in stock at Mouser (975) and
LCSC (26,635). On the cached, unverified figures, Mouser covers INA237, LM5146, the 5 mΩ WSK2512, EEH-ZA1E331P and
XAL1010-682MED from stock; TPS3431 showed small stock. C24 is EEH-ZA1E331V (in stock at DigiKey; kit note gives the fit).
C2 is EMVH101ARA470MKE0S (decided; the buck board is laid out for it).

**Decided 2026-11-10: U1 is fitted with LM5069MM-2/NOPB for now.** The kit orders 5 LM5069-2: 4 for two sets (U1 and U7) and 1 spare:
Mouser LM5069MM-2/NOPB or LCSC C2653582 (LM5069MMX-2/NOPB, the large reel). The schematic keeps LM5069MMX-1 as U1's
design part, with a "Fitted" field naming the -2; order 2 LM5069MM-1/NOPB and swap U1 when it is back in stock. With
the -2 the bus restarts by itself about every 63 ms after a fault clears, and the heatsink fan must run whenever the
pack is connected: [LM5069_RETRY.md](LM5069_RETRY.md).

## LCSC, checked live 2026-11-11

Read from LCSC's product pages. Prices are LCSC's list price before US duty (about 37.5 % on China-origin goods) and
shipping (about $20).

| Part | LCSC | Stock | Price at the kit quantity | Note |
|---|---|---|---|---|
| IPB017N10N5LFATMA1 (18) | C3289286 | 499 | $4.30 each at 10+ ($5.04 at 1) | about $77, about $106 with duty: not cheaper than DigiKey's roughly $5.50 each |
| INA237AIDGSR (14) | C2864837 | 9,825 | $1.56 each at 10+ | in stock; DigiKey is out until 25-Nov-2026 |
| TPS48111LQDGXRQ1 (7) | C17558994 | 9,860 | $3.00 each at 1, $2.56 at 10+ | |
| TPS259541DSGR (6) | C2155673 | 155 | $0.27 each, sold in fives | |
| TPS7A4001DGNR (3) | C55006 | 4,364 | $2.46 each | |
| EEH-ZC1K470P (28) | C178648 | 9 | $0.65 each at 10+ | too few in stock |
| LM5146RGYR (3) | C3188679 | 0 | | out of stock |
| TPS3431SDRBR (3) | C702145 | 0 | | out of stock |

**What this changes.** PRODUCTION_RUN.md section 1 estimated the power FETs at about $51 for 16 from LCSC; the live price
is about $69 for 16 before duty, so the FETs are no cheaper from LCSC once duty is paid. After duty and LCSC's shipping,
moving the lines above to LCSC saves little or nothing against DigiKey. The second order exists for stock, not for
price: the lines DigiKey cannot supply (LM5069-2, INA237, TPS3431S, LM5146, SM08B-GHS-TB, WSK25125L000FEA,
XAL1010-682MED, 419D) go to Mouser, which ships from the US without duty; LCSC covers only INA237, LM5069-2 and
SM08B-GHS-TB of those. The Mouser stock figures above are still unverified.

## Distributor comparison, checked 2026-11-11

Unit prices at the kit quantity, from trustedparts.com (authorised distributors) and LCSC's product pages. "No stock"
means no authorised distributor showed units on hand.

| Part (kit qty) | DigiKey | Mouser | Other | Buy from |
|---|---|---|---|---|
| IPB017N10N5LFATMA1 (18) | $5.51 | $4.37 | LCSC $4.30 before duty | Mouser, about $20 less |
| BSC040N10NS5ATMA1 (5) | $3.45 at 1, $2.24 at 10 | $1.73 at 10 | Arrow $1.63 at 10 | Mouser |
| INA237AIDGSR (14) | $2.42 | $2.13, 13,105 in stock | LCSC $1.56 before duty | Mouser |
| TPS48111LQDGXRQ1 (7) | $5.05 at 1, $3.85 at 10 | $5.10 at 1, $3.89 at 10 | LCSC $3.00 at 1 | LCSC, about $6 less with duty |
| TPS48100QDGXRQ1 (3) | $4.50 | $4.50 | not at LCSC | DigiKey |
| EEH-ZC1K470P (28) | $1.09 | $1.18 | LCSC 9 in stock | DigiKey |
| C1210C225K1RACTU (24) | $0.69 | $0.69 | | DigiKey |
| CSS2H-2512K-2L00F (7) | $1.48 at 1, $0.97 at 10 | the same | Arrow $0.59 | DigiKey (about $4 more than Arrow) |
| WSK25125L000FEA (5) | no stock | 123 in stock, $2.86 at 1 | Arrow 545, $1.81; Newark 124 | Mouser |
| LM5069MM-2/NOPB (5) | no stock | lead time only (51 in stock on 2026-11-10) | LCSC C2653582 (MMX-2) 4,802 at $4.10 | LCSC |
| LM5146RGYR (3) | no stock until 18-Jan-2027 | lead time 112 days | TI.com out of stock; LCSC out | none: see below |
| TPS3431SDRBR (3) | no stock | stock not shown, $2.07 | Spirit Electronics 139 at $1.95 | Mouser if it shows stock |
| SM08B-GHS-TB(LF)(SN) (5) | no stock | stock not shown (975 on 2026-11-10) | LCSC C265111 out of stock today | Mouser if it shows stock |
| XAL1010-682MED (2) | not sold | stock not shown, $5.11 | Coilcraft direct | Mouser or Coilcraft |

**LM5146RGYR has no authorised stock.** The automotive-grade LM5146QRGYRQ1 (LM5146-Q1, the same RGY VQFN-20 package)
is at LCSC (C1850329, 60 in stock, $7.21) and Spirit Electronics (1,424, $5.69). TI's LM5146 product page lists
the LM5146-Q1 as the "pin-to-pin, automotive version of LM5146", in the same 20-pin RGY package (4.5 x 3.5 mm), so it
fits buck12's U1 footprint unchanged. It costs about $3 more per chip.

**Decided 2026-11-11: buck U1 is ordered as LM5146QRGYRQ1** (3 pieces, LCSC C1850329). The schematic value stays LM5146RGYR;
the two are the same device in the same package.

Outside the lines above DigiKey and Mouser price within a few percent of each other, so shopping further saves about
$35 to $45 on the whole order, most of it the power FETs at Mouser.
