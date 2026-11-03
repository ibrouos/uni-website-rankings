# Product

## Register

product

## Users
Web and digital teams at UK universities (e.g. the University of Sheffield web team). They check the dashboard to benchmark their homepage against peer institutions, see whether a release or redesign moved their Lighthouse scores, and pull evidence for conversations with stakeholders. They know what LCP, TBT and CLS mean and don't need hand-holding, but they do want the answer to "where do we stand, and which way are we heading?" in seconds.

## Product Purpose
A public, automatically updated league table of UK university homepage performance, built from daily Lighthouse runs on mobile and desktop. Success means a team can find their university, read its current score and trend at a glance, see how its Core Web Vitals have moved over time, and line it up against chosen competitors.

## Brand Personality
Precise, calm, technical. Instrument-like rather than promotional: the data is the interface, decoration is minimal, and every mark on the page means something. Confident enough to let numbers speak without hero treatment.

## Anti-references
- The previous version of this dashboard: generic, low-density list with stat tiles and little sense of trend or history.
- Generic SaaS templates: hero metrics, gradient accents, identical card grids.
- Lighthouse report clones: circular gauges and traffic-light circles everywhere.

## Design Principles
1. **Trend over snapshot.** A score without its direction is half an answer; history and trend sit next to the current number, not behind a click.
2. **Comparison is a first-class task.** Choosing a few universities and lining them up should be as easy as reading the list.
3. **Density with calm.** Show a lot of data per row, but with quiet structure so it scans rather than shouts.
4. **Honest data.** Show staleness, gaps and sample size plainly; never imply freshness the monitor hasn't delivered.

## Accessibility & Inclusion
WCAG 2.2 AA. Chart series must stay distinguishable without colour alone (line style, direct labels, or tooltip text), score grades must not rely solely on red/green, everything must be keyboard operable, and motion respects `prefers-reduced-motion`.
