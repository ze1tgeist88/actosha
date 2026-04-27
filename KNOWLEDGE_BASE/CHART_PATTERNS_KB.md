# CHART PATTERNS KNOWLEDGE BASE
# ACTosha — Complete Pattern Definitions, Detection Rules & Differentiation
# Version: 1.0.0
# Last_Updated: 2026-04-27
# Source: Wikipedia, Investopedia, StockCharts, Bulkowski's ThePatternSite

═══════════════════════════════════════════════════════════════════════════════
SECTION 1 — PATTERN TAXONOMY (Complete Classification)
═══════════════════════════════════════════════════════════════════════════════

PATTERNS ARE DIVIDED INTO:

 CATEGORY           │ TYPE                  │ SUB-TYPES
 ───────────────────┼──────────────────────┼─────────────────────────────────
 REVERSAL           │ Top (Bearish)        │ Double Top, Triple Top, H&S, IH&S
                    │                       │ Broadening Top, Island Top
                    │ Bottom (Bullish)     │ Double Bottom, Triple Bottom
                    │                       │ Inverse H&S, Island Bottom
 CONTINUATION       │ Triangles            │ Ascending, Descending, Symmetric
                    │ Channels             │ Rising Channel, Falling Channel
                    │                       │ Horizontal Channel
                    │ Flags/Pennants      │ Bull Flag, Bear Flag
                    │                       │ Bull Pennant, Bear Pennant
                    │ Wedges               │ Rising Wedge, Falling Wedge
                    │ Gaps                 │ Breakaway, Exhaustion, Common
                    │                       │ Measuring (Runaway)
 SPECIAL/OTHER      │ Cup and Handle       │ Cup with Handle, Inverted Cup
                    │ Price Channels      │ Horizontal, Ascending, Descending

═══════════════════════════════════════════════════════════════════════════════
SECTION 2 — REVERSAL PATTERNS (Detailed)
═══════════════════════════════════════════════════════════════════════════════

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2.1 DOUBLE TOP (Bearish Reversal)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 DEFINITION:
 Two distinct peaks at approximately the same price level, followed by a
 breakdown below the neckline (support between peaks).

 FORMATION RULES:
   • Peak 1 and Peak 2 must be within tolerance of each other
   • Tolerance: 0.5% - 1.5% (textbook: 1%, empirically derived)
   • Time between peaks: 2 weeks to 2 months (ideally)
   • Peaks should not be adjacent candles (spaced by 10-50 candles)
   • Volume should be higher on first peak, lower on second
   • Neckline = lowest low between the two peaks
   • Confirmation: close below neckline with volume

 DETECTION PARAMETERS:
   tolerance = 0.01 (1% — from Wikipedia)
   min_peaks_distance = 10 bars
   neckline_break_confirm = True
   volume_confirm = recommended

 TARGET CALCULATION:
   Pattern Height = Peak Price - Neckline
   Target = Neckline - Pattern Height
   Risk/Reward: measure from neckline break to target

 DIFFERENTIATION FROM SIMILAR PATTERNS:
   vs H&S:        H&S has middle peak HIGHER than both shoulders
                  Double Top has two equal peaks, no middle peak
   vs Triple Top: Triple Top has THREE peaks, Double Top has TWO
   vs Broadening: Broadening has successively HIGHER peaks
                  Double Top has equal EQUAL peaks

 VARIATIONS:
   • Adam-Adam: Both peaks are sharp (single candle tops)
   • Adam-Eve: First peak is sharp, second is rounded
   • Eve-Adam: First peak is rounded, second is sharp
   • Eve-Eve: Both peaks are rounded (more reliable per Bulkowski)

 BULKOWSKI STATISTICS:
   Average Rise or Fall: ~20%
   Reversal Rate: ~48%
   Chart Performance: varies widely

 SOURCE: Wikipedia (Double Top and Double Bottom), Investopedia

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2.2 DOUBLE BOTTOM (Bullish Reversal)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 DEFINITION:
 Two distinct troughs at approximately the same price level, followed by a
 breakout above the neckline (resistance between troughs).

 FORMATION RULES:
   • Bottom 1 and Bottom 2 must be within tolerance of each other
   • Tolerance: 0.5% - 1.5% (textbook: 1%)
   • Time between bottoms: 2 weeks to 2 months (ideally)
   • Volume should be higher on first bottom, lower on second
   • Neckline = highest high between the two bottoms
   • Confirmation: close above neckline with volume

 DETECTION PARAMETERS:
   tolerance = 0.01 (1%)
   min_bottoms_distance = 10 bars
   neckline_break_confirm = True
   volume_confirm = recommended

 TARGET CALCULATION:
   Pattern Height = Neckline - Bottom Price
   Target = Neckline + Pattern Height

 DIFFERENTIATION:
   vs IH&S:       IH&S has middle bottom LOWER than shoulders
                  Double Bottom has equal lows, no middle trough
   vs Triple Bot: Triple Bottom has THREE troughs
   vs Broadening: Broadening has successively LOWER troughs

 VARIATIONS:
   Same as Double Top (Adam-Adam, Adam-Eve, Eve-Adam, Eve-Eve)

 SOURCE: Wikipedia

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2.3 TRIPLE TOP (Bearish Reversal)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 DEFINITION:
 Three distinct peaks at approximately the same price level, followed by a
 breakdown below the support level (lowest valley between peaks).

 FORMATION RULES:
   • Three peaks at similar price levels (within tolerance)
   • Peaks may NOT be evenly spaced
   • Intervening valleys may bottom at different levels
   • Volume typically diminishes with each subsequent peak
   • Confirmation: price falls below the lowest valley
   • Rare than double top

 DETECTION PARAMETERS:
   tolerance = 0.015 (1.5%)
   min_peaks = 3
   min_bars_between = 5
   volume_diminish_factor = 0.8 (each peak lower volume)

 DIFFERENTIATION:
   vs Double Top: Triple Top has THREE peaks, Double Top has TWO
   vs H&S:        H&S middle peak is HIGHER, Triple Top equal
   vs Head & Shoulders (variant): Sometimes misidentified

 KEY INSIGHT (from Wikipedia):
   "Observation shows that it is rare to see four tops or bottoms at equal
    levels. In case prices continue to rally up to the level of the three
    previous tops, there is a good chance that they will rally up higher.
    If they come down to the same level a fourth time, they usually decline."

 SOURCE: Wikipedia (Triple top and triple bottom)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2.4 TRIPLE BOTTOM (Bullish Reversal)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 DEFINITION:
 Three distinct troughs at approximately the same price level, followed by
 a breakout above the resistance level (highest peak between troughs).

 FORMATION RULES:
   • Three troughs at similar price levels
   • Volume typically higher on third bottom (capitulation)
   • Rally after third bottom should show increased volume
   • Confirmation: price breaks above highest peak between bottoms

 DIFFERENTIATION:
   vs Double Bottom: Triple Bottom has THREE troughs
   vs IH&S:        IH&S middle trough is LOWER
   All three reversals at same level suggests Triple

 SOURCE: Wikipedia

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2.5 HEAD AND SHOULDERS (Bearish Reversal)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 DEFINITION:
 Three peaks where the middle peak (head) is highest, and the two outer
 peaks (shoulders) are lower and approximately equal. Neckline connects
 the lows between peaks.

 ANATOMY:
   Left Shoulder: peak, then decline
   Head:          higher peak, then decline
   Right Shoulder: lower peak (similar to left), then decline
   Neckline:      support connecting lows between peaks

 FORMATION RULES:
   • Left shoulder peak < Head peak
   • Right shoulder peak < Head peak
   • Left shoulder ≈ Right shoulder (within tolerance 1-2%)
   • Neckline may slope slightly (acceptable)
   • Volume: lower on right shoulder
   • Confirmation: close below neckline

 DETECTION PARAMETERS:
   tolerance = 0.015 (1.5% — from Wikipedia)
   min_bars_shoulder_to_head = 10
   min_bars_head_to_shoulder = 10
   neckline_break = True

 VARIATIONS:
   • Complex H&S: Multiple shoulders on one or both sides
   • H&S with uneven shoulders: Left ≠ Right but both < Head

 DIFFERENTIATION:
   vs Double Top: H&S has a HIGHER middle peak
                  Double Top has two equal peaks
   vs Triple Top: Triple Top has three equal-high peaks

 SOURCE: Wikipedia (Head and shoulders (chart pattern))

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2.6 INVERSE HEAD AND SHOULDERS (Bullish Reversal)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 DEFINITION:
 Three troughs where the middle trough (head) is lowest, and the two outer
 troughs (shoulders) are higher and approximately equal.

 ANATOMY:
   Left Shoulder: trough, then rally
   Head:          lower trough, then rally
   Right Shoulder: higher trough (similar to left), then rally
   Neckline:      resistance connecting highs between troughs

 FORMATION RULES:
   • Left shoulder trough > Head trough
   • Right shoulder trough > Head trough
   • Left shoulder ≈ Right shoulder
   • Volume: increase on rally after head
   • Confirmation: close above neckline

 DETECTION PARAMETERS:
   Same as H&S, mirrored

 SOURCE: Wikipedia

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2.7 BROADENING TOP (Bearish Reversal)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 DEFINITION:
 Also known as "Megaphone Pattern". Price swings with successively HIGHER
 peaks and LOWER troughs, forming a widening shape.

 FORMATION RULES:
   • 5 minor reversals (a-b-c-d-e)
   • Point b is lower than point a
   • Points c and e are successively HIGHER than point a
   • Confirmation: price breaks below point b or d
   • Volume is irregular
   • Appears MORE FREQUENTLY at TOPS than bottoms

 ANATOMY (from Wikipedia):
   Five minor reversals a-b-c-d-e
   - d is lower than b
   - c and e are successively higher than a

 DETECTION PARAMETERS:
   min_reversals = 5
   slope_reject_threshold = 0
   requires_consecutive_higher_highs = True

 VARIATIONS:
   • Broadening Bottom (Inverse): Lower lows, higher highs (rare)
   • Symmetrical Broadening: Equal widening on both sides

 DIFFERENTIATION:
   vs Double/Triple Top: Equal peaks vs successively HIGHER peaks
   vs H&S: H&S middle peak HIGHEST vs Broadening successive HIGHER

 SOURCE: Wikipedia (Broadening top), Investopedia

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2.8 ISLAND REVERSAL (Bearish or Bullish Reversal)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 DEFINITION:
 A cluster of days (island) separated from preceding and subsequent price
 action by gaps. Can be top or bottom reversal.

 FORMATION RULES:
   • Island: compact trading area (1 to several days)
   • Preceding gap: exhaustion gap down (for top) or up (for bottom)
   • Following gap: breakaway gap in opposite direction
   • Gaps at BOTH ends at approximately same price level
   • High volume expected in island area
   • Reversal significance: MAJOR

 TYPES:
   • Bullish Island Bottom: Island separated by gap down, then gap up
   • Bearish Island Top: Island separated by gap up, then gap down

 DETECTION PARAMETERS:
   min_gap_size = 0.005 (0.5% of price)
   island_min_bars = 1
   island_max_bars = 10
   volume_threshold = 1.5 (above average)

 KEY CHARACTERISTICS:
   • Extremely good indicator of reversal
   • Indicates extreme sentiment change
   • "One-day reversal" when island is single day

 SOURCE: Wikipedia (Island reversal)

═══════════════════════════════════════════════════════════════════════════════
SECTION 3 — CONTINUATION PATTERNS (Detailed)
═══════════════════════════════════════════════════════════════════════════════

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3.1 TRIANGLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 COMMON RULES FOR ALL TRIANGLES:
   • Form over 1-3 months (classical) or weeks (fast)
   • At least 2 touches on each trendline
   • Volume decreases as pattern matures
   • Breakout usually on increasing volume
   • False breakouts common ~15% of cases

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ ASCENDING TRIANGLE (Bullish Continuation)                                   │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ Definition: Horizontal RESISTANCE line, rising SUPPORT line                 │
 │                                                                          │
 │ Formation:                                                                 │
 │   • Upper line: relatively horizontal (resistance)                        │
 │   • Lower line: ascending slope (support)                                  │
 │   • Price bounces between these lines                                     │
 │   • Each subsequent low is HIGHER than previous                            │
 │                                                                          │
 │ Breakout: UPWARD through resistance                                        │
 │ Volume: increase on breakout                                               │
 │                                                                          │
 │ Detection Parameters:                                                      │
 │   resistance_slope_max = 0.001 (nearly flat)                              │
 │   support_slope_min = 0.005 (clearly rising)                              │
 │   min_touches = 2 per line                                                │
 │   min_bars = 30                                                           │
 └─────────────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ DESCENDING TRIANGLE (Bearish Continuation)                                  │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ Definition: Falling RESISTANCE line, horizontal SUPPORT line               │
 │                                                                          │
 │ Formation:                                                                 │
 │   • Lower line: relatively horizontal (support)                           │
 │   • Upper line: descending slope (resistance)                              │
 │   • Each subsequent high is LOWER than previous                            │
 │                                                                          │
 │ Breakout: DOWNWARD through support                                         │
 │ Volume: increase on breakout                                               │
 └─────────────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ SYMMETRIC TRIANGLE (Neutral/Continuation)                                   │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ Definition: Converging trendlines (one descending, one ascending)         │
 │                                                                          │
 │ Formation:                                                                 │
 │   • Upper line: descending slope                                           │
 │   • Lower line: ascending slope                                            │
 │   • Lines converge toward apex                                             │
 │                                                                          │
 │ Breakout: Can break EITHER direction                                      │
 │   Statistical bias: breaks in direction of prior trend (~60%)            │
 │                                                                          │
 │ Detection Parameters (ALL TRIANGLES):                                      │
 │   lookback = 50 bars                                                      │
 │   min_touches = 2 per line                                                │
 │   squeeze_ratio = range_recent / range_early (< 0.7 suggests pattern)   │
 │   slope_thresh = 0.001 (for flat detection)                               │
 └─────────────────────────────────────────────────────────────────────────────┘

 DIFFERENTIATION BETWEEN TRIANGLES:
   Ascending: Flat top, rising bottom → breakout UP
   Descending: Falling top, flat bottom → breakout DOWN
   Symmetric: Both sloping → breakout in trend direction

 SOURCE: Wikipedia (Triangle (chart pattern)), Investopedia

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3.2 FLAGS AND PENNANTS (Short-term Continuation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ FLAG (Continuation)                                                        │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ DEFINITION: Small parallelogram against the prevailing trend               │
 │                                                                          │
 │ FORMATION:                                                                 │
 │   • Flagpole: sharp move up or down (at least 45° angle)                 │
 │   • Flag: small parallel channel (5-20 bars)                               │
 │   • Counter-trend direction:                                              │
 │     Bull Flag: slopes DOWN (small pullback)                                │
 │     Bear Flag: slopes UP (small rally)                                     │
 │                                                                          │
 │ RULES:                                                                     │
 │   • Pattern duration: 1-4 weeks                                           │
 │   • Flag slopes AGAINST trend (key differentiator from wedge)             │
 │   • Volume decreases during flag formation                                │
 │   • Volume INCREASES on breakout                                          │
 │   • Price usually continues in direction of flagpole                      │
 │                                                                          │
 │ TARGET:                                                                    │
 │   Measured move = length of flagpole                                      │
 │   Projected from breakout point                                           │
 │                                                                          │
 │ DETECTION PARAMETERS:                                                      │
 │   pole_min_slope = 0.01 (45° equivalent)                                 │
 │   flag_max_bars = 20                                                      │
 │   flag_min_bars = 5                                                       │
 │   volume_decrease_confirm = True                                          │
 │   parallel_slopes = True (flag vs wedge)                                  │
 └─────────────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ PENNANT (Continuation)                                                     │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ DEFINITION: Small symmetric triangle against prevailing trend               │
 │                                                                          │
 │ DIFFERENCE FROM FLAG:                                                      │
 │   Flag: Parallel lines (rectangle shape)                                  │
 │   Pennant: Converging lines (triangle shape)                              │
 │                                                                          │
 │ OTHERWISE IDENTICAL TO FLAG:                                              │
 │   • Flagpole precedes pattern                                             │
 │   • Duration 1-4 weeks                                                    │
 │   • Volume decreases during formation                                     │
 │   • Volume increases on breakout                                          │
 │                                                                          │
 │ KEY DIFFERENTIATOR from WEDGE:                                             │
 │   Pennant/Wedge: Both converging BUT                                      │
 │   Pennant: Forms AFTER sharp pole, short duration (1-4 weeks)             │
 │   Wedge: Slopes AGAINST main trend direction (rising/falling)            │
 │   Wedge: Takes longer to form (~3-4 weeks minimum)                        │
 └─────────────────────────────────────────────────────────────────────────────┘

 SOURCE: Wikipedia (Flag and pennant patterns)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3.3 WEDGES (Reversal or Continuation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ RISING WEDGE (Bearish Bias)                                                 │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ Definition: Converging lines BOTH sloping UPWARD                           │
 │                                                                          │
 │ Formation:                                                                 │
 │   • Both upper and lower lines slant UP from left to right                │
 │   • Lower line rises FASTER than upper line                               │
 │   • Creates narrowing "rising" shape                                       │
 │   • Price range contracts as wedge rises                                  │
 │                                                                          │
 │ Direction:                                                                  │
 │   • In UPTREND: considered REVERSAL (uptrend losing steam)               │
 │   • In DOWNTREND: considered BULLISH continuation                         │
 │                                                                          │
 │ Breakout: DOWNWARD (typically)                                             │
 │ Volume: decreases as wedge forms, increases on breakout                    │
 │                                                                          │
 │ DETECTION PARAMETERS:                                                      │
 │   lookback = 40 bars                                                      │
 │   min_both_slopes_positive = True                                        │
 │   slope_diff_threshold = 0.001 (convergence requirement)                  │
 │   break_direction = "down"                                                │
 └─────────────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ FALLING WEDGE (Bullish Bias)                                               │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ Definition: Converging lines BOTH sloping DOWNWARD                        │
 │                                                                          │
 │ Formation:                                                                 │
 │   • Both upper and lower lines slant DOWN from left to right              │
 │   • Upper line falls FASTER than lower line                               │
 │   • Creates narrowing "falling" shape                                      │
 │                                                                          │
 │ Direction:                                                                  │
 │   • In DOWNTREND: considered REVERSAL (downtrend losing steam)           │
 │   • In UPTREND: considered BEARISH continuation                          │
 │                                                                          │
 │ Breakout: UPWARD (typically)                                              │
 │ Volume: decreases as wedge forms, increases on breakout                   │
 │                                                                          │
 │ SAME DETECTION PARAMETERS, mirrored                                        │
 └─────────────────────────────────────────────────────────────────────────────┘

 CRITICAL DIFFERENTIATION (Wedge vs Flag vs Pennant):
 ┌──────────────────┬───────────────────┬────────────────────────────────────┐
 │ PATTERN          │ SLOPE vs TREND    │ SHAPE                              │
 ├──────────────────┼───────────────────┼────────────────────────────────────┤
 │ Bull Flag        │ AGAINST (down)    │ PARALLEL lines (rectangle)         │
 │ Bear Flag        │ AGAINST (up)      │ PARALLEL lines (rectangle)         │
 │ Bull Pennant     │ AGAINST (down)    │ CONVERGING (triangle) small        │
 │ Bear Pennant     │ AGAINST (up)      │ CONVERGING (triangle) small        │
 │ Rising Wedge     │ WITH (rising)     │ CONVERGING both rising             │
 │ Falling Wedge    │ WITH (falling)    │ CONVERGING both falling            │
 └──────────────────┴───────────────────┴────────────────────────────────────┘

 SOURCE: Wikipedia (Wedge pattern)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3.4 PRICE CHANNELS (Continuation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ HORIZONTAL CHANNEL (Sideways/Ranging)                                      │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ Definition: Parallel horizontal lines (support + resistance)               │
 │                                                                          │
 │ Formation:                                                                 │
 │   • Price oscillates between two horizontal lines                         │
 │   • Neither slope clearly up nor down                                     │
 │   • Duration: can be weeks to months                                       │
 │                                                                          │
 │ Breakout: Can break either direction                                       │
 └─────────────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ ASCENDING CHANNEL (Bullish)                                                │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ Definition: Parallel lines BOTH sloping UP                                 │
 │                                                                          │
 │ Formation:                                                                 │
 │   • Higher highs AND higher lows                                           │
 │   • Both lines have positive slope                                        │
 │   • Trend is healthy uptrend                                               │
 │                                                                          │
 │ Breakout: Usually continues UP, can break BOTH directions                  │
 └─────────────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ DESCENDING CHANNEL (Bearish)                                               │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ Definition: Parallel lines BOTH sloping DOWN                               │
 │                                                                          │
 │ Formation:                                                                 │
 │   • Lower highs AND lower lows                                            │
 │   • Both lines have negative slope                                        │
 │   • Trend is healthy downtrend                                             │
 │                                                                          │
 │ Breakout: Usually continues DOWN                                          │
 └─────────────────────────────────────────────────────────────────────────────┘

 DETECTION PARAMETERS:
   min_touches_per_line = 2
   slope_threshold_for_horizontal = 0.001
   parallel_tolerance = 0.01

 DIFFERENTIATION:
   vs Flag:        Channel has PARALLEL lines, Flag is slight angle against trend
   vs Wedge:       Channel PARALLEL, Wedge CONVERGING
   vs Rectangle:   Same as Horizontal Channel (different names)

 SOURCE: Wikipedia (Price channels)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3.5 GAPS (Continuation or Reversal)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ BREAKAWAY GAP (Continuation/Start of Move)                                 │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ Definition: Gap that occurs when price breaks away from congestion area    │
 │                                                                          │
 │ Characteristics:                                                            │
 │   • Occurs at START of new move or end of consolidation                   │
 │   • Often accompanies strong trend initiation                              │
 │   • Gap remains UNFILLED for extended period                               │
 │   • Heavy volume SUPPORTS the gap                                          │
 │                                                                          │
 │ Trading Implication:                                                        │
 │   If gap occurs with high volume → likely continues in gap direction      │
 │   If gap occurs with low volume → may fill before resuming                │
 └─────────────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ COMMON GAP (Area Gap / Pattern Gap)                                        │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ Definition: Gap within a trading range or congestion area                  │
 │                                                                          │
 │ Characteristics:                                                            │
 │   • Occurs in sideways markets                                            │
 │   • Price usually FILLS the gap within days                               │
 │   • Little forecasting significance                                       │
 │   • Most common type of gap                                                │
 │                                                                          │
 │ Trading Implication:                                                        │
 │   "Fade the gap" strategy: expect price to fill gap                       │
 └─────────────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ EXHAUSTION GAP (Reversal)                                                  │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ Definition: Gap at the END of a rapid, straight-line move                  │
 │                                                                          │
 │ Characteristics:                                                            │
 │   • Occurs near end of trending move                                      │
 │   • Often accompanied by HEAVY VOLUME (key differentiator)                 │
 │   • Price often reverses shortly after                                     │
 │                                                                          │
 │ KEY DIFFERENTIATION from Measuring Gap:                                     │
 │   Measure vs Exhaustion: Look at VOLUME                                    │
 │   Low volume after gap → Measuring (continuation)                         │
 │   High volume after gap → Exhaustion (reversal)                           │
 │                                                                          │
 │ Trading Implication:                                                        │
 │   Major reversal signal                                                    │
 └─────────────────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ MEASURING GAP (Runaway Gap)                                                │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ Definition: Gap that occurs MID-WAY through a trend                         │
 │                                                                          │
 │ Characteristics:                                                            │
 │   • Occurs approximately in middle of rapid move                          │
 │   • NOT associated with congestion                                          │
 │   • Usually NOT FILLED for considerable time                              │
 │   • Can be used to MEASURE further target                                  │
 │                                                                          │
 │ Target Calculation:                                                         │
 │   Distance from start to gap = Distance from gap to target               │
 │                                                                          │
 │ Trading Implication:                                                        │
 │   Continuation of trend                                                    │
 └─────────────────────────────────────────────────────────────────────────────┘

 DETECTION PARAMETERS:
   gap_min_size = 0.005 (0.5% of price — filters noise)
   gap_identification: Requires open of current bar vs close of previous bar

 SOURCE: Wikipedia (Gap (chart pattern))

═══════════════════════════════════════════════════════════════════════════════
SECTION 4 — SPECIAL PATTERNS
═══════════════════════════════════════════════════════════════════════════════

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4.1 CUP AND HANDLE (Bullish Continuation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 DEFINITION:
 Formed by a "U"-shaped rounded bottom (cup) followed by a small pullback
 (handle), suggesting bullish continuation.

 FORMATION RULES:
   • Cup should be ROUNDED (not V-shaped)
   • Cup bottom should reach SAME price level as cup rim (both sides equal)
   • Cup depth: 12% to 33% (ideally) of cup price
   • Handle retraces 30% to 50% of cup's rise
   • Handle duration: 1 to 4 weeks (much shorter than cup)
   • Cup duration: 1 to 6 months (classical)
   • Volume: decreases during cup, increases during handle

 CUP REQUIREMENTS:
   Ideal Cup: Both sides reach exactly same high
   Acceptable: Slight asymmetry, but both should reach similar levels
   Shape: Rounded bottom (U-shape), not sharp (V-shape)

 HANDLE REQUIREMENTS:
   • Should retrace 30-50% of cup's rise
   • If retraces MORE than 50% → pattern less reliable
   • Should be small and compact
   • Price should break above handle resistance

 VARIATIONS:
   • Inverted Cup and Handle (Bearish): Mirror image, breaks down

 DETECTION PARAMETERS:
   cup_min_depth_pct = 0.10
   cup_max_depth_pct = 0.40
   handle_retrace_min = 0.30
   handle_retrace_max = 0.50
   min_cup_bars = 20
   max_handle_bars = 20

 DIFFERENTIATION:
   vs V-bottom: Cup has ROUNDED bottom, V is sharp reversal
   vs Double Bottom: Cup has gradual rounded bottom vs two distinct bottoms

 SOURCE: Wikipedia (Cup and handle)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4.2 DEAD CAT BOUNCE (Bearish - Misleading Name)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 DEFINITION:
 Temporary rally in prolonged downtrend. Despite name, is actually a
 recognized technical pattern showing interim bounce before resume下降.

 FORMATION:
   • Occurs in strong downtrend
   • Price rallies 5-10% (sometimes up to 30-40%)
   • Then declines again to new lows
   • Rally is to previous support (now resistance)

 Trading Implication:
   NOT a buy-the-dip opportunity
   Rallies are selling opportunities
   Wait for new lows confirmation

 SOURCE: Wikipedia (Dead cat bounce) — noted as concept, not classic pattern

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4.3 BULL TRAP / BEAR TRAP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 DEFINITION:
 False breakout that traps traders on wrong side.

 Bull Trap: Price breaks ABOVE resistance, then falls back
 Bear Trap: Price breaks BELOW support, then rises back

 Characteristics:
   • Breakout with LOW volume (key warning sign)
   • Quickly reverses
   • Often triggered by news

 SOURCE: Wikipedia (Point and figure — listed under traps)

═══════════════════════════════════════════════════════════════════════════════
SECTION 5 — CANDLESTICK PATTERNS (Brief Reference)
═══════════════════════════════════════════════════════════════════════════════

 SIMPLE (Single Candle):
   • Doji: Open ≈ Close (indecision)
   • Hammer: Small body, long lower shadow (bullish reversal)
   • Inverted Hammer: Small body, long upper shadow (bullish reversal)
   • Shooting Star: Long upper shadow, small body at bottom (bearish)

 COMPLEX (Multiple Candles):
   • Engulfing: Body engulfs previous body (bullish/bearish)
   • Morning Star: 3-bar bullish reversal
   • Evening Star: 3-bar bearish reversal
   • Three White Soldiers: 3 consecutive bullish candles
   • Three Black Crows: 3 consecutive bearish candles
   • Hikkake: Complex 4+ bar pattern

 Note: Candlestick patterns already implemented in pattern_scanner.py.
 Full detection code exists for: engulfing, hammer, doji, morning/evening star.

═══════════════════════════════════════════════════════════════════════════════
SECTION 6 — PATTERN CONFUSION MATRIX (Differentiation Guide)
═══════════════════════════════════════════════════════════════════════════════

 ┌────────────────────────────────────────────────────────────────────────────┐
 │ DOUBLE TOP vs HEAD & SHOULDERS                                              │
 ├────────────────────────────────────────────────────────────────────────────┤
 │ Double Top:        Two peaks EQUAL height                                  │
 │ H&S:              Middle peak HIGHER (head) than shoulders                │
 │                                                                            │
 │ Key Question: Is there a third distinct high between the two peaks?        │
 │ If YES and middle is highest → H&S                                         │
 │ If NO and peaks are equal → Double Top                                     │
 └────────────────────────────────────────────────────────────────────────────┘

 ┌────────────────────────────────────────────────────────────────────────────┐
 │ DOUBLE TOP vs TRIPLE TOP                                                   │
 ├────────────────────────────────────────────────────────────────────────────┤
 │ Double Top: 2 peaks at same level                                         │
 │ Triple Top: 3 peaks at same level (or 3rd at lower)                       │
 │                                                                            │
 │ Key Question: How many peaks touching/near same resistance?               │
 │ 2 → Double Top | 3 → Triple Top                                            │
 └────────────────────────────────────────────────────────────────────────────┘

 ┌────────────────────────────────────────────────────────────────────────────┐
 │ HEAD & SHOULDERS vs BROADENING TOP                                          │
 ├────────────────────────────────────────────────────────────────────────────┤
 │ H&S:          Head highest, shoulders lower but equal                     │
 │ Broadening:   Peaks successively HIGHER, no "head"                        │
 │                                                                            │
 │ Key Question: Are peaks getting progressively higher?                       │
 │ If progressively higher → Broadening                                       │
 │ If middle is clear head → H&S                                              │
 └────────────────────────────────────────────────────────────────────────────┘

 ┌────────────────────────────────────────────────────────────────────────────┐
 │ FLAG vs PENNANT vs WEDGE                                                   │
 ├────────────────────────────────────────────────────────────────────────────┤
 │ Flag:        PARALLEL lines, counter-trend                                 │
 │ Pennant:     CONVERGING lines, counter-trend, short duration               │
 │ Rising Wedge: CONVERGING lines, BOTH rising (slopes WITH trend)           │
 │ Falling Wedge: CONVERGING lines, BOTH falling                             │
 │                                                                            │
 │ Key Question 1: Are lines parallel or converging?                         │
 │   Parallel → Flag | Converging → go to Q2                                 │
 │ Key Question 2: Do both lines slope in SAME direction?                    │
 │   YES → Wedge | NO (one flat/one sloping) → Pennant                      │
 └────────────────────────────────────────────────────────────────────────────┘

 ┌────────────────────────────────────────────────────────────────────────────┐
 │ ASCENDING vs DESCENDING vs SYMMETRIC TRIANGLE                              │
 ├────────────────────────────────────────────────────────────────────────────┤
 │ Ascending:   Flat RESISTANCE top, rising SUPPORT bottom                   │
 │ Descending:  Falling RESISTANCE top, flat SUPPORT bottom                   │
 │ Symmetric:   Both lines CONVERGING (one down, one up)                     │
 │                                                                            │
 │ Key: Look at which boundary is flat/dominant                              │
 └────────────────────────────────────────────────────────────────────────────┘

 ┌────────────────────────────────────────────────────────────────────────────┐
 │ CUP AND HANDLE vs DOUBLE BOTTOM                                            │
 ├────────────────────────────────────────────────────────────────────────────┤
 │ Cup:          Rounded U-shape, gradual                                     │
 │ Double Bot:   Two distinct sharp or flat bottoms                           │
 │                                                                            │
 │ Key: Shape of the bottom between lows                                      │
 │   Rounded gradual → Cup | Sharp V or flat → Double Bottom                │
 └────────────────────────────────────────────────────────────────────────────┘

 ┌────────────────────────────────────────────────────────────────────────────┐
 │ MEASURING GAP vs EXHAUSTION GAP                                            │
 ├────────────────────────────────────────────────────────────────────────────┤
 │ Measuring: Mid-trend, LOW volume after gap                                 │
 │ Exhaustion: End of trend, HIGH volume after gap                          │
 │                                                                            │
 │ Key: Volume after gap formation                                            │
 │   Low volume → Measuring (continuation)                                   │
 │   High volume → Exhaustion (reversal)                                     │
 └────────────────────────────────────────────────────────────────────────────┘

 ┌────────────────────────────────────────────────────────────────────────────┐
 │ COMMON GAP vs BREAKAWAY GAP                                                │
 ├────────────────────────────────────────────────────────────────────────────┤
 │ Common: Within congestion, FILLED quickly                                  │
 │ Breakaway: At START of new move, NOT filled quickly                       │
 │                                                                            │
 │ Key: Context — is price in a range or breaking out?                       │
 └────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
SECTION 7 — IMPLEMENTATION STATUS
═══════════════════════════════════════════════════════════════════════════════

 PATTERN                          │ STATUS        │ CODE LOCATION
 ────────────────────────────────┬───────────────┼──────────────────────────────
 Double Top                      │ ✅ IMPLEMENTED │ pattern_scanner.py
 Double Bottom                   │ ✅ IMPLEMENTED │ pattern_scanner.py
 Head & Shoulders                │ ✅ IMPLEMENTED │ pattern_scanner.py
 Inverse H&S                     │ ✅ IMPLEMENTED │ pattern_scanner.py
 ────────────────────────────────┼───────────────┼──────────────────────────────
 Ascending Triangle              │ ✅ IMPLEMENTED │ pattern_scanner.py
 Descending Triangle             │ ✅ IMPLEMENTED │ pattern_scanner.py
 Symmetric Triangle             │ ✅ IMPLEMENTED │ pattern_scanner.py
 ────────────────────────────────┼───────────────┼──────────────────────────────
 Rising Wedge                    │ ✅ IMPLEMENTED │ pattern_scanner.py
 Falling Wedge                   │ ✅ IMPLEMENTED │ pattern_scanner.py
 ────────────────────────────────┼───────────────┼──────────────────────────────
 Bull Flag                       │ ❌ MISSING     │ needs implementation
 Bear Flag                       │ ❌ MISSING     │ needs implementation
 Bull Pennant                    │ ❌ MISSING     │ needs implementation
 Bear Pennant                    │ ❌ MISSING     │ needs implementation
 ────────────────────────────────┼───────────────┼──────────────────────────────
 Triple Top                      │ ❌ MISSING     │ needs implementation
 Triple Bottom                   │ ❌ MISSING     │ needs implementation
 ────────────────────────────────┼───────────────┼──────────────────────────────
 Broadening Top                  │ ❌ MISSING     │ needs implementation
 Broadening Bottom               │ ❌ MISSING     │ needs implementation
 ────────────────────────────────┼───────────────┼──────────────────────────────
 Island Reversal (Top/Bottom)   │ ❌ MISSING     │ needs implementation
 ────────────────────────────────┼───────────────┼──────────────────────────────
 Cup and Handle                  │ ❌ MISSING     │ needs implementation
 Inverted Cup and Handle         │ ❌ MISSING     │ needs implementation
 ────────────────────────────────┼───────────────┼──────────────────────────────
 Horizontal Channel              │ ❌ MISSING     │ needs implementation
 Ascending Channel               │ ❌ MISSING     │ needs implementation
 Descending Channel              │ ❌ MISSING     │ needs implementation
 ────────────────────────────────┼───────────────┼──────────────────────────────
 Breakaway Gap                   │ ❌ MISSING     │ needs implementation
 Exhaustion Gap                  │ ❌ MISSING     │ needs implementation
 Common Gap                      │ ❌ MISSING     │ needs implementation
 Measuring Gap                   │ ❌ MISSING     │ needs implementation
 ────────────────────────────────┼───────────────┼──────────────────────────────
 Bull Trap                       │ ❌ MISSING     │ needs implementation
 Bear Trap                       │ ❌ MISSING     │ needs implementation
 ────────────────────────────────┼───────────────┼──────────────────────────────
 Bullish Engulfing              │ ✅ IMPLEMENTED │ pattern_scanner.py
 Bearish Engulfing              │ ✅ IMPLEMENTED │ pattern_scanner.py
 Hammer                          │ ✅ IMPLEMENTED │ pattern_scanner.py
 Inverted Hammer                 │ ✅ IMPLEMENTED │ pattern_scanner.py
 Doji                            │ ✅ IMPLEMENTED │ pattern_scanner.py
 Morning Star                    │ ✅ IMPLEMENTED │ pattern_scanner.py
 Evening Star                    │ ✅ IMPLEMENTED │ pattern_scanner.py
 ────────────────────────────────┼───────────────┼──────────────────────────────
 Three White Soldiers            │ ❌ MISSING     │ needs implementation
 Three Black Crows               │ ❌ MISSING     │ needs implementation
 Hikkake                         │ ❌ MISSING     │ needs implementation
 Shooting Star                   │ ❌ MISSING     │ needs implementation

 TOTAL: 16 patterns IMPLEMENTED, 24 MISSING

═══════════════════════════════════════════════════════════════════════════════
SECTION 8 — PATTERN RELIABILITY (Based on Bulkowski Research)
═══════════════════════════════════════════════════════════════════════════════

 NOTE: These statistics are from Thomas Bulkowski's "Encyclopedia of Chart
 Patterns" — empirical research on historical performance.

 PATTERN                    │ REVERSAL % │ AVG MOVE  │ RANKING
 ───────────────────────────┼────────────┼────────────┼────────────────
 Double Top                 │ ~48%       │ ~20%       │ Below Average
 Double Bottom              │ ~48%       │ ~20%       │ Below Average
 Head & Shoulders           │ ~53%       │ ~35%       │ Average
 Inverse H&S                │ ~53%       │ ~35%       │ Average
 ───────────────────────────┼────────────┼────────────┼────────────────
 Ascending Triangle         │ ~73%       │ ~25%       │ Above Average
 Descending Triangle        │ ~71%       │ ~25%       │ Above Average
 Symmetric Triangle         │ ~62%       │ ~25%       │ Average
 ───────────────────────────┼────────────┼────────────┼────────────────
 Rising Wedge              │ ~64%       │ ~20%       │ Average
 Falling Wedge              │ ~64%       │ ~20%       │ Average
 ───────────────────────────┼────────────┼────────────┼────────────────
 Bull Flag                  │ ~67%       │ ~15%       │ Above Average
 Bear Flag                  │ ~67%       │ ~15%       │ Above Average
 Cup and Handle             │ ~65%       │ ~35%       │ Above Average
 ───────────────────────────┼────────────┼────────────┼────────────────
 Triple Top                 │ ~47%       │ ~20%       │ Below Average
 Broadening Top             │ ~43%       │ ~25%       │ Below Average

 KEY INSIGHT:
 Pattern "strength" in scanner (0-1) is currently based on rule-satisfaction.
 It should be calibrated against empirical success rates above.

 Example recalibration:
   Current: strength = rules_satisfied_count / max_rules
   Better:  strength = rules_satisfied_count / max_rules * empirical_reversal_rate

 ════════════════════════════════════════════════════════════════════════════════
 VERSION & AUDIT
 ════════════════════════════════════════════════════════════════════════════════

 v1.0.0 — 2026-04-27 — Researched and compiled from Wikipedia, Investopedia,
           StockCharts, Bulkowski's ThePatternSite.
 All pattern definitions sourced from open authoritative sources.
 Statistics are empirical (Bulkowski) where noted.
