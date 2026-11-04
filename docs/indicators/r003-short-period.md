# R003: Short submission period

> **A risk signal, not evidence of wrongdoing.** A short period can favour bidders who
> knew in advance, but it can also come from urgency or from data entry errors.

- **Code and definition:** R003 from the Open Contracting Partnership's red flags, as
  implemented in [Cardinal](https://cardinal.readthedocs.io/en/latest/cli/indicators/R/003.html):
  the time between `tender/tenderPeriod/startDate` and `endDate` is too short. Cardinal's
  default threshold is 15 days and it can be set per procedure type (legal minimums).
- **Models:** `gold.indicator_r003_short_period` (one row per evaluated process) and
  `gold.buyer_r003_summary` (one row per buyer).

## How days are counted

Days are **complete 24-hour periods** between start and end. This is how SERCOP computes
`durationInDays`: in 16,101 competitive processes, `durationInDays` equals the calendar-date
difference in 7,287 cases and is exactly **one day less** in 8,814. Most processes open in
the afternoon (17:00, 20:00, 18:00) and close in the morning (10:00, 09:00), so counting
dates adds a day that bidders never had. It is not business days ("término"): that matched
almost no process. A warning-level dbt test (`assert_tender_duration_matches_dates`) checks
this reading on every build.

## Which processes are evaluated

| Rule | Why |
|---|---|
| `procurement_method` in `open`, `selective` (var `r003_procurement_methods`) | Competitive procedures, where the period matters for who can bid. |
| Start and end dates known, end after start | SERCOP publishes the end date for only 11,835 of 48,318 open processes. **Subasta Inversa Electrónica has no end date**, so it cannot be evaluated. |
| Procedure type with at least 100 processes (var `r003_min_group`) | A percentile of a handful of processes means nothing. |

In practice this covers Licitación, Menor Cuantía, Cotización and Licitación de Seguros.

## What "short" means

Each procedure type has its own legal minimum, so one national threshold (such as
Cardinal's 15 days) does not fit: the median Licitación lasts about 14 calendar days.
Until the legal minimums are loaded **with their legal citations**, a period is "short"
when it is **strictly below the 5th percentile of its procedure type** (var
`r003_percentile`), comparing complete days.

Calendar days in the exploration (before the complete-day correction):

| Procedure type | Processes | Minimum | 5th percentile | Median |
|---|---:|---:|---:|---:|
| Licitación | 8,588 | 1 | 8 | 14 |
| Menor Cuantía | 4,266 | 1 | 7 | 13 |
| Cotización | 1,919 | 3 | 11 | 18 |
| Licitación de Seguros | 1,328 | 8 | 14 | 16 |

Many Seguros tenders last exactly 14 days (1st, 5th and 25th percentiles), which looks
like a legal minimum.

## Comparing buyers

`buyer_r003_summary` compares each buyer's share of short periods with the share
expected for its procedure types, computed from **other** buyers only (leave-one-out),
and marks `enough_data` from 20 evaluated processes (var `r003_min_processes`).

## Legitimate causes and data issues

- Urgent needs that justify the legal minimum.
- Data entry errors or corrected dates (periods of 0–1 days are more likely errors than
  real periods).
- Processes that were cancelled and republished.

## Limitations

- A relative threshold always flags about 5% of each type, even if every process met
  the law. Legal minimums with citations should replace or complement it.
- No coverage of Subasta Inversa Electrónica, the most common competitive procedure.
- Only the published period is measured, not when the documents were really available.
