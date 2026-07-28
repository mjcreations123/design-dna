# Data visualization

Use this when data is encoded as position, length, area, color, shape, or motion. Start from the question and decision; a chart is useful only when it reveals a relationship more clearly than prose or a table.

## Frame the question

Record:

- audience, decision, and comparison they need to make;
- measure, unit, population, time window, source, freshness, and owner;
- relevant denominator, target, benchmark, or prior period;
- uncertainty, collection limits, and transformations;
- whether exact lookup, pattern recognition, monitoring, or exploration matters most.

Do not invent data, smooth away inconvenient variation, or present sample data as live. Separate observation, estimate, forecast, target, and annotation.

## Choose an honest form

Match the form to the relationship:

- use a table when exact values, many attributes, or row-level comparison matter;
- use bars or aligned points for categorical comparison;
- use lines for ordered change, especially time;
- use histograms, box plots, or density views for distribution;
- use scatter plots for relationships between quantitative measures;
- use part-to-whole forms only when the whole and denominator are meaningful;
- use maps only when geography explains the question.

Small multiples often preserve comparison better than overloaded legends or dual axes. Avoid decorative 3D, pictorial scaling, and chart novelty that changes perceived magnitude.

## Encode and scale

- Prefer accurately comparable position and length for important quantitative judgments.
- Keep units, precision, sorting, time intervals, and aggregation explicit.
- Give bar-like magnitude encodings a meaningful zero; disclose and visually clarify any necessary truncated range.
- Label logarithmic, indexed, normalized, cumulative, or reversed scales in plain language.
- Keep color domains stable across related views, and distinguish sequential, diverging, and categorical meaning.
- Show baselines and thresholds only when they have a sourced decision role.

## Preserve uncertainty and absence

Show uncertainty with an appropriate interval, range, distribution, scenario, or qualification. State sample size and methodology when they affect interpretation. Distinguish zero, unavailable, not applicable, suppressed, delayed, and not yet collected. Do not connect missing observations as if they existed.

## Interaction and access

- Make the central finding understandable without interaction.
- Pair hover details with focus, touch, or persistent alternatives.
- Keep selection and filter state visible; expose scope, reset, and no-result recovery.
- Preserve the user's place when data refreshes, and announce consequential updates without stealing focus.
- Provide a concise text summary and an accessible table or equivalent data path when the graphic carries essential information.
- Do not rely on color alone; test labels, contrast, focus, target size, zoom, forced colors, and screen-reader output.

Use motion to explain a meaningful transition, not to make values feel alive. Respect reduced motion and prevent animation from obscuring comparison.

## Adapt and verify

On smaller containers, preserve the question and important comparison rather than shrinking every mark. Recompose, prioritize, disclose, scroll with context, or offer a task-specific table. Keep titles, legends, annotations, controls, and source notes associated with the data.

Test sparse, dense, extreme, negative, tied, missing, stale, and rapidly changing values; long labels; locale-specific numbers and dates; keyboard and touch; supported themes; and intermediate widths. Validate calculations and interpretation against the source, then review the rendered result with representative data.

High-stakes statistical interpretation, regulated reporting, geospatial analysis, complex interactive graphics, or assistive-technology conformance requires the relevant data, domain, accessibility, legal, or compliance specialist. This reference does not certify analytical validity.
