# Stryktipset Predictor — UI/UX Specification

## 1. Purpose

This document defines the UI/UX direction for a Stryktipset predictor application.

The product should help the user answer three questions quickly:

1. **What is the optimal row to play?**
2. **Why is that row optimal?**
3. **Where does the model disagree with Svenska Folket?**

The interface should feel simple, trustworthy, data-driven and clearly inspired by the visual identity of Stryktipset without copying the official product.

The core principle is:

> **Simple on the surface, detailed underneath.**

Advanced statistics, model reasoning and source material should be available through submenus and expandable views, but should never dominate the default experience.

---

# 2. Product Design Principles

## 2.1 The optimal row is the hero

The optimal row is the most important element in the entire product.

It should always be easy to find and understand.

The user should not need to interpret charts or statistics before seeing the recommendation.

---

## 2.2 Progressive disclosure

Show only the most useful information first.

More advanced information should be accessible through:

- tabs
- drawers
- expandable sections
- modals
- submenus

The default interface should remain clean even when the system contains large amounts of data.

---

## 2.3 Explain recommendations

The application must not feel like a black box.

For every recommendation, the user should be able to inspect:

- model probabilities
- Svenska Folket
- bookmaker market probabilities
- statistical factors
- current news/signals
- reason for the recommended sign
- source material

---

## 2.4 Probability and value are different

The UI must clearly distinguish between:

- **Most likely outcome**
- **Best value**
- **Recommended Stryktipset sign**

Example:

A home team can still be the most likely winner while being heavily overstreckad.

The design should make this distinction obvious without requiring the user to understand machine learning.

---

## 2.5 Avoid betting-dashboard clutter

Do not create a dense sportsbook-style interface.

Avoid:

- excessive charts
- blinking elements
- bright green/red everywhere
- dozens of badges
- too many numbers per card
- visual noise
- unnecessary gradients
- casino aesthetics

The visual language should feel more like a modern analytics product.

---

# 3. Visual Identity

## 3.1 Core colors

### Primary blue

`#00427A`

Use for:

- top navigation
- primary buttons
- selected signs
- active tabs
- main headings
- links
- focus states
- important UI controls

---

### White

`#FFFFFF`

Use as:

- main page background
- card background
- modal background
- primary text-on-blue contrast

---

### Soft pink

`#FFECEB`

Use as a subtle highlight color.

Recommended uses:

- value opportunities
- noteworthy matches
- "pay attention" surfaces
- selected secondary states
- weekly insight cards

Do **not** use the pink color as an error or danger state.

Its role is:

> This is worth looking at.

---

## 3.2 Neutral palette

Recommended supporting colors:

```css
--gray-50:  #F7F8F9;
--gray-100: #F1F3F5;
--gray-200: #E3E6E8;
--gray-300: #CDD2D6;
--gray-500: #7A838B;
--gray-600: #5F6870;
--gray-800: #27323A;
--gray-900: #17212B;
```

Primary text:

`#17212B`

Secondary text:

`#5F6870`

Borders:

`#E3E6E8`

---

## 3.3 Semantic colors

Keep semantic colors restrained.

Success:

`#247A4B`

Warning:

`#B36A00`

Error:

`#B83A3A`

These colors should mainly be used for system feedback.

Do not use them as the core visual language of match predictions.

---

# 4. Typography

Use a clean modern sans-serif.

Recommended:

- Inter
- Geist
- Source Sans 3
- system font stack

Preferred default:

```css
font-family:
  Inter,
  ui-sans-serif,
  system-ui,
  -apple-system,
  BlinkMacSystemFont,
  "Segoe UI",
  sans-serif;
```

---

## 4.1 Type scale

### Page title

32 px desktop  
26 px mobile  
700 weight

### Section heading

22–24 px  
700 weight

### Card heading

16–18 px  
600–700 weight

### Body

14–16 px  
400–500 weight

### Small metadata

12–13 px  
500 weight

Large numerical probabilities may use:

24–32 px  
700 weight

---

# 5. Spacing and Layout

Use an 8 px spacing system.

Recommended spacing tokens:

```text
4
8
12
16
24
32
40
48
64
```

Main desktop content width:

`1200–1320px`

Recommended:

`max-width: 1280px`

Horizontal desktop page padding:

`32px`

Tablet:

`24px`

Mobile:

`16px`

---

# 6. Border Radius

Use moderate rounded corners.

Recommended:

- small controls: `6px`
- buttons: `8px`
- cards: `10px`
- large panels: `12px`
- modals/drawers: `14px`

Avoid excessively rounded pill-style components except for small tags.

---

# 7. Shadows

Use shadows sparingly.

Most cards should rely on borders rather than shadows.

Default card:

```css
border: 1px solid #E3E6E8;
```

Elevated surfaces:

```css
box-shadow: 0 8px 30px rgba(23, 33, 43, 0.08);
```

---

# 8. Global Navigation

## Desktop navigation

Top navigation bar.

Background:

`#00427A`

Height:

approximately `64px`

Content:

- product logo/name
- Översikt
- Kupong
- Analys
- Historik

Optional right-side content:

- current draw / week selector
- settings icon

Example:

```text
STRYKTIPSET AI      Översikt   Kupong   Analys   Historik       Vecka 37
```

Active navigation item should be clearly visible through:

- white text
- subtle underline
- or slightly brighter background

Do not overcrowd the navigation.

---

## Mobile navigation

Use bottom navigation.

Items:

1. Översikt
2. Kupong
3. Analys
4. Historik

Keep labels visible.

Do not use icon-only navigation.

---

# 9. Page Structure

Primary pages:

```text
/overview
/coupon
/analysis
/history
```

Individual match detail can be shown through a drawer or route:

```text
/match/:id
```

Desktop recommendation:

Use a right-side drawer.

Mobile recommendation:

Use a full-screen detail view or bottom sheet.

---

# 10. Overview Page

This is the default landing page.

The user should understand the week in approximately 10 seconds.

Page sections:

1. Week header
2. Optimal row
3. System summary
4. Weekly insights
5. 13 match cards

---

# 11. Week Header

Example:

```text
Stryktipset · Vecka 37
Lördag 12 september 2026
```

Optional metadata:

```text
Senast uppdaterad 14:32
```

Add a subtle status indicator:

```text
Data uppdaterad
```

Avoid adding unnecessary technical information here.

---

# 12. Optimal Row Hero

This is the main hero component.

Card background:

`#FFFFFF`

Border:

`1px solid #E3E6E8`

Optional subtle blue top border.

Header:

```text
OPTIMAL RAD
```

Secondary text:

```text
Baserad på modell, marknad och Svenska Folket
```

---

## 12.1 Sign display

Display all 13 matches as compact sign cells.

Desktop example:

```text
1   X   1X   1   X2   1   1X2   2   1   X   1X   2   1
```

Each cell should include the match number.

Example:

```text
1
1
```

or:

```text
M1
1
```

Recommended desktop layout:

13 equal-width cells.

Mobile:

Allow horizontal scrolling or use a compact multi-row grid.

Do not shrink text until it becomes hard to read.

---

# 13. Sign Button Component

Three base states:

## Unselected

White background.

Border:

`#CDD2D6`

Text:

`#27323A`

---

## Selected

Background:

`#00427A`

Text:

`#FFFFFF`

Border:

`#00427A`

---

## Value-highlighted

Use:

- pink outline
- pink corner marker
- subtle `#FFECEB` background

Do not replace selected blue state.

Possible representation:

```text
X ✦
```

Use the symbol sparingly.

---

# 14. System Summary

Directly below the optimal row.

Example:

```text
256 kr
4 spikar
5 halvgarderingar
1 helgardering
Värdeindex 1.28
```

Recommended desktop layout:

single horizontal summary row.

Mobile:

2-column grid.

---

# 15. Budget Selector

The user should be able to change the betting budget.

Preset values:

```text
64 kr
128 kr
256 kr
512 kr
```

Optional:

```text
Egen insats
```

Changing budget should immediately recalculate:

- spikar
- half covers
- full covers
- optimal combination

Use a segmented control or compact button group.

Avoid dropdowns if only four common options exist.

---

# 16. Hero Actions

Primary:

```text
Visa system
```

Secondary:

```text
Ändra insats
```

Optional tertiary:

```text
Jämför alternativ
```

Primary button:

blue background.

Secondary button:

white background + blue border.

---

# 17. Weekly Insights

Show exactly three primary insights.

Recommended cards:

### Starkaste spik

Example:

```text
Arsenal
61 %
```

---

### Bästa värdetecken

Example:

```text
Brighton 2
Modell 34 %
Folket 21 %
```

---

### Största varningen

Example:

```text
Liverpool 1
Folket 81 %
Modell 64 %
```

Desktop:

3-column layout.

Mobile:

vertical stack or horizontal cards.

Cards may use subtle `#FFECEB` emphasis.

Avoid adding more than three primary insights on the overview page.

---

# 18. Match List

Below weekly insights show all 13 matches.

Each match should be represented by a compact match card.

The card must remain understandable without opening details.

---

# 19. Match Card

Example:

```text
1   Arsenal – Everton

Modell
61     24     15
1      X      2

Svenska Folket
72     18     10

Rekommendation
1X

Analys ›
```

---

## 19.1 Information hierarchy

Top:

- match number
- home team
- away team
- kickoff time

Middle:

- model probability
- Svenska Folket

Bottom:

- recommended sign
- value indicator
- analysis link

Do not show every possible statistic here.

---

# 20. Probability Display

Use the standard order:

```text
1     X     2
61%   24%   15%
```

The strongest probability may use:

- bold text
- blue text

Do not automatically use green.

---

# 21. Svenska Folket Comparison

Display directly beneath model probability.

Example:

```text
Svenska Folket

72%   18%   10%
```

Optional difference row:

```text
-11    +6    +5
```

Do not show difference row by default if it makes cards too dense.

A compact indicator can instead show:

```text
1 överstreckad +11
```

---

# 22. Recommendation Label

Examples:

```text
Rekommendation: 1
Rekommendation: 1X
Rekommendation: X2
Rekommendation: 1X2
```

The recommendation should be visually stronger than the raw numbers.

Use dark text and selected-sign component.

---

# 23. Match Attention State

Matches that deserve extra attention can receive:

background:

`#FFECEB`

or a subtle pink left border.

Use for cases such as:

- major model/folk disagreement
- strong value opportunity
- important injury signal
- unusual market movement

Do not highlight too many matches.

Ideally 2–5 per coupon.

---

# 24. Match Detail Drawer

Clicking a match opens a detail surface.

Desktop:

right drawer approximately `480–560px` wide.

Mobile:

full-screen view.

Header:

```text
Arsenal – Everton
Match 1
```

Tabs:

```text
Översikt
Form
Nyheter
Modell
```

---

# 25. Detail Tab — Översikt

This is the default tab.

Display three probability groups.

---

## 25.1 Model

```text
Vår modell

1     X     2
61    24    15
```

---

## 25.2 Svenska Folket

```text
Svenska Folket

1     X     2
72    18    10
```

---

## 25.3 Bookmaker market

```text
Marknaden

1     X     2
66    21    13
```

Bookmaker probabilities should be de-vigged before display.

---

## 25.4 Recommendation explanation

Example:

```text
Rekommendation: 1X

Arsenal är fortfarande tydlig favorit, men ettan är överstreckad
jämfört med både modellen och marknaden. Krysset ger bättre
spelvärde än Svenska Folkets streck antyder.
```

Explanation should be concise.

Avoid AI-generated filler.

---

# 26. Detail Tab — Form

Show useful historical/team context.

Recommended sections:

### Recent form

```text
Arsenal
V V O V F

Everton
O F V F O
```

---

### Performance metrics

Possible metrics:

- xG
- xGA
- goals scored
- goals conceded
- shots
- Elo
- expected points
- home/away performance

Use compact comparison rows.

Example:

```text
xG / match          1.82        1.31
xGA / match         0.94        1.52
Elo                  1842        1688
```

Avoid giant dashboards.

---

# 27. Detail Tab — News

The news tab summarizes current information relevant to the match.

Do not present full articles by default.

Use structured signals.

Example:

```text
Viktiga signaler

↑ Saka tillbaka i full träning
↓ Ordinarie mittback saknas
↑ Everton har två extra vilodagar
↓ Everton svag bortastatistik senaste perioden
```

---

## 27.1 Signal component

Each signal should contain:

- direction
- team
- short summary
- confidence
- source count

Optional:

```text
Hög säkerhet
2 källor
```

Do not display raw LLM confidence decimals to normal users.

---

## 27.2 Sources

Button:

```text
Visa källor
```

Expanded view:

```text
BBC Sport
PremierLeague.com
The Athletic
Club press conference
```

Each source entry can show:

- publisher
- headline
- publication time
- external link

---

# 28. Detail Tab — Model

Advanced section intended for technical users.

Possible layout:

```text
Bookmaker baseline      64 / 22 / 14
Statistical model       60 / 25 / 15
News adjustment         -1 / +0 / +1
--------------------------------------
Final prediction        61 / 24 / 15
```

---

## 28.1 Model factors

Show key contributing factors.

Example:

```text
Största positiva faktorer

+ Home advantage
+ Higher Elo
+ Better xG trend

Största negativa faktorer

- Important defensive injury
- Shorter rest period
```

Optional confidence:

```text
Modellsäkerhet
78 / 100
```

Do not imply false certainty.

Tooltip:

> Modellsäkerhet beskriver hur stabil prediktionen är utifrån tillgänglig data, inte sannolikheten att rekommendationen blir rätt.

---

# 29. Coupon Page

The coupon page focuses on system construction.

Main areas:

1. Budget selector
2. 13 matches
3. Selected signs
4. Price
5. Alternative systems

---

# 30. Coupon Builder

Each match row:

```text
1 Arsenal – Everton

[1] [X] [2]

Modell: 61 / 24 / 15
Folket: 72 / 18 / 10
```

The model-generated system is selected by default.

The user may manually override signs.

When manually changed, show:

```text
Manuellt ändrad
```

Include:

```text
Återställ modellens val
```

---

# 31. System Price

Sticky summary on desktop.

Sticky bottom bar on mobile.

Example:

```text
256 kr
4 spikar
5 halvgarderingar
1 helgardering

Spela enligt modell
```

If no direct betting integration exists:

Use:

```text
Kopiera system
```

or:

```text
Exportera rad
```

Do not imply direct betting functionality unless it actually exists.

---

# 32. Alternative Systems

Provide three system modes.

## Optimal

Balances probability and value.

Default mode.

---

## Säker

Higher weight on model probability and favourites.

Lower variance.

---

## Värde

Higher weight on underselected outcomes versus Svenska Folket.

Higher variance.

---

Each mode should display:

```text
256 kr
4 spikar
Value index
Risk
```

Avoid presenting one mode as objectively guaranteed to be better.

---

# 33. Analysis Page

This page is designed for users who want to inspect the week more deeply.

Recommended sections:

### Biggest model vs crowd differences

Table:

```text
Match                  Sign   Modell   Folket   Skillnad
Everton – Brighton     2      34%      21%      +13
Leeds – Villa          1      39%      27%      +12
```

---

### Most overselected outcomes

Example:

```text
Liverpool 1
Folket 81%
Modell 64%
Difference -17
```

---

### Most underselected outcomes

Example:

```text
Brighton 2
Folket 21%
Modell 34%
Difference +13
```

---

### Market disagreements

Compare:

- model
- bookmakers
- Svenska Folket

This page may use more tables and charts than the overview page.

---

# 34. History Page

The history page shows model performance over time.

Recommended summary metrics:

- coupons analyzed
- 13-right rate
- 12-right rate
- 11-right rate
- average Brier score
- log loss
- calibration
- theoretical EV
- actual betting return if tracked

Clearly separate:

```text
Backtest
```

from:

```text
Live predictions
```

Never mix historical training results with real-world live performance.

---

# 35. Historical Coupon View

Each previous week can be opened.

Example:

```text
Vecka 36

Model row
Actual result
Correct signs
Missed matches
Predicted value
Actual payout
```

Allow detailed inspection of each match.

---

# 36. Responsive Behavior

## Desktop

Primary experience.

Recommended:

- content max width 1280 px
- 13-sign row visible without scrolling
- right-side match drawer
- tables allowed

---

## Tablet

Reduce padding.

Allow:

- wrapped optimal row
- drawer approximately 60–70% viewport width

---

## Mobile

Critical requirements:

- bottom navigation
- single-column card layout
- optimal row may use 7 + 6 grid
- sticky system price
- match detail becomes full screen
- minimum touch target 44×44 px

Avoid horizontal scrolling except where it clearly improves usability.

---

# 37. Mobile Optimal Row

Recommended layout:

```text
1   X   1X  1   X2  1   1X2
2   1   X   1X  2   1
```

Each sign should still show the corresponding match number.

Do not show tiny 13-column layouts on mobile.

---

# 38. Loading States

Use skeleton UI.

Examples:

- match card skeleton
- optimal row skeleton
- probability skeleton

Avoid full-page spinners whenever possible.

---

# 39. Empty States

Example:

```text
Ingen kupong hittades ännu.

Vi väntar på att veckans Stryktipskupong ska publiceras.
```

Provide useful context rather than generic:

```text
No data
```

---

# 40. Error States

Example:

```text
Vissa analyser kunde inte uppdateras.

Kupongdata och tidigare modellvärden visas fortfarande.
```

Always preserve usable cached data when possible.

---

# 41. Data Freshness

Because recommendations change over time, freshness must be visible.

Example:

```text
Senast uppdaterad 14:32
```

For individual data sources:

```text
Odds 14:31
Svenska Folket 14:30
Nyheter 14:25
```

Only show these details in expanded/advanced views.

---

# 42. Accessibility

Requirements:

- WCAG AA contrast minimum
- do not rely on color alone
- selected signs need visual and textual state
- keyboard navigation
- visible focus state
- `aria-label` on sign buttons
- meaningful screen reader labels
- minimum 44 px touch target mobile

Example:

```html
<button aria-label="Välj kryss för Arsenal mot Everton">
  X
</button>
```

---

# 43. Animation

Animations should be subtle.

Use approximately:

`150–220ms`

Recommended:

- drawer transition
- tab underline
- sign selection
- accordion expansion

Avoid:

- bouncing
- glowing
- large scale animations
- continuous motion

---

# 44. Component Architecture

Recommended Angular components:

```text
AppShellComponent
TopNavigationComponent
BottomNavigationComponent

WeekHeaderComponent
OptimalRowCardComponent
SystemSummaryComponent
BudgetSelectorComponent
WeeklyInsightsComponent
InsightCardComponent

MatchListComponent
MatchCardComponent
MatchProbabilityComponent
SignSelectorComponent
ValueIndicatorComponent

MatchDetailDrawerComponent
MatchOverviewTabComponent
MatchFormTabComponent
MatchNewsTabComponent
MatchModelTabComponent

CouponBuilderComponent
CouponMatchRowComponent
SystemPriceBarComponent
AlternativeSystemCardComponent

AnalysisOverviewComponent
ValueTableComponent
MarketComparisonComponent

HistoryOverviewComponent
HistoricalCouponCardComponent
ModelPerformanceChartComponent
```

---

# 45. Suggested Data Structures for UI

Example match view model:

```ts
interface MatchViewModel {
  id: string;
  number: number;

  homeTeam: string;
  awayTeam: string;
  kickoff: string;

  model: OutcomeProbabilities;
  crowd: OutcomeProbabilities;
  market: OutcomeProbabilities;

  recommendation: Array<'1' | 'X' | '2'>;

  strongestValue?: '1' | 'X' | '2';

  attentionLevel: 'normal' | 'interesting';

  shortExplanation: string;

  updatedAt: string;
}

interface OutcomeProbabilities {
  home: number;
  draw: number;
  away: number;
}
```

---

# 46. Design Tokens

Recommended initial CSS tokens:

```css
:root {
  --color-primary: #00427A;
  --color-primary-dark: #00345F;

  --color-background: #FFFFFF;
  --color-surface: #FFFFFF;

  --color-highlight: #FFECEB;

  --color-text: #17212B;
  --color-text-secondary: #5F6870;

  --color-border: #E3E6E8;
  --color-muted: #F5F6F7;

  --color-success: #247A4B;
  --color-warning: #B36A00;
  --color-error: #B83A3A;

  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;
  --space-7: 48px;
  --space-8: 64px;

  --content-width: 1280px;
}
```

---

# 47. Desktop Overview Wireframe

```text
┌─────────────────────────────────────────────────────────────┐
│ STRYKTIPSET AI   Översikt Kupong Analys Historik   Vecka 37│
└─────────────────────────────────────────────────────────────┘


 Stryktipset · Vecka 37
 Lördag 12 september


┌─────────────────────────────────────────────────────────────┐
│ OPTIMAL RAD                                                 │
│                                                             │
│  1   X   1X   1   X2   1   1X2   2   1   X   1X   2   1 │
│                                                             │
│  256 kr   4 spikar   Värdeindex 1.28                       │
│                                                             │
│  [ Visa system ]   [ Ändra insats ]                         │
└─────────────────────────────────────────────────────────────┘


 VECKANS ANALYS

┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│ Starkaste spik │ │ Bästa värde    │ │ Största varning│
│ Arsenal 61%    │ │ Brighton 2     │ │ Liverpool 1    │
└────────────────┘ └────────────────┘ └────────────────┘


 MATCHER

┌─────────────────────────────────────────────────────────────┐
│ 1 Arsenal – Everton                             16:00        │
│                                                             │
│ Modell           61       24       15                         │
│                  1        X        2                          │
│                                                             │
│ Svenska Folket   72       18       10                         │
│                                                             │
│ Rekommendation   [1] [X]                         Analys ›    │
└─────────────────────────────────────────────────────────────┘
```

---

# 48. Mobile Overview Wireframe

```text
┌───────────────────────┐
│ Stryktipset · V37     │
│ Lör 12 sep            │
└───────────────────────┘

┌───────────────────────┐
│ OPTIMAL RAD           │
│                       │
│ 1  X  1X  1  X2  1  1X2
│ 2  1  X   1X 2   1
│                       │
│ 256 kr · 4 spikar     │
│                       │
│ [ Visa system ]       │
└───────────────────────┘

Veckans analys

[ Starkaste spik ]
[ Bästa värde    ]
[ Största varning]

Matcher

┌───────────────────────┐
│ 1 Arsenal – Everton   │
│                       │
│ Modell                │
│ 1 61  X 24  2 15      │
│                       │
│ Folket                │
│ 1 72  X 18  2 10      │
│                       │
│ Rek: 1X      Analys › │
└───────────────────────┘


┌───────────────────────┐
│ Översikt Kupong Analys│
│ Historik              │
└───────────────────────┘
```

---

# 49. UX Rules for Recommendations

The application should never say:

```text
This outcome will win.
```

Use language such as:

```text
Modellen uppskattar...
Modellen rekommenderar...
Starkaste tecknet...
Bäst spelvärde...
```

Predictions should always be communicated probabilistically.

---

# 50. Definition of "Optimal"

The word **Optimal** must have a clear product definition.

Recommended definition:

> The combination of singles, doubles and triples that maximizes the model's expected value for the selected budget based on the model probabilities and Svenska Folket.

The optimal system should therefore not simply maximize the raw probability of 13 correct results.

---

# 51. UX Priority Order

When making UI tradeoffs, use this order:

1. Optimal row
2. Recommended signs
3. Price
4. Model probability
5. Svenska Folket
6. Match explanation
7. News/signals
8. Market probability
9. Advanced statistics
10. Technical model details

Anything lower on the list should never interfere with something higher.

---

# 52. MVP UI Scope

The first UI implementation should include:

- desktop/mobile app shell
- overview page
- week header
- optimal row
- budget selector
- system summary
- three weekly insights
- 13 match cards
- match detail drawer
- overview/form/news/model tabs
- coupon builder
- system price
- manual sign overrides
- analysis page
- history shell

Do not spend MVP time on:

- advanced animations
- social features
- user profiles
- complex customization
- dozens of charts
- gamification
- dark mode
- multiple themes

---

# 53. Final Product Feel

The finished product should feel:

- Swedish
- calm
- analytical
- modern
- trustworthy
- focused
- clearly connected to Stryktipset
- simple enough for casual users
- deep enough for serious users

The application should never feel like:

- a casino
- a crypto dashboard
- an AI demo
- a generic Bootstrap admin panel
- a sportsbook clone

The core experience should always be:

> **Open the app → see the optimal row → understand the key decisions → inspect deeper analysis only when desired.**
