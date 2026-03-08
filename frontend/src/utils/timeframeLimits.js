/**
 * Timeframe-Based Backtest Range Limiter
 * ──────────────────────────────────────
 * Central utility shared across the frontend to enforce max backtest
 * date-range limits based on the selected timeframe resolution.
 *
 * Rules:
 *   1m           → max 1 year
 *   2m, 3m       → max 2 years
 *   5m           → max 5 years
 *   10m, 15m+    → full history (no limit)
 *   hours, days  → full history (no limit)
 */

// ── Limit map (timeframe string  →  max years, null = unlimited) ──────────
const TIMEFRAME_MAX_YEARS = {
    '1m': 1,
    '2m': 2,
    '3m': 3,
    '5m': 5,
    '10m': null,
    '15m': null,
    '20m': null,
    '30m': null,
    '45m': null,
};

/**
 * Parse a timeframe string (e.g. "5m", "2h", "1D") into its numeric value
 * and unit character.
 */
function parseTimeframe(tf) {
    const match = tf.match(/^(\d+)([mhDWM])$/);
    if (!match) return null;
    return { value: parseInt(match[1], 10), unit: match[2] };
}

/**
 * Return the maximum allowed backtest range in years for a given timeframe,
 * or `null` if there is no limit (i.e. full history is allowed).
 */
export function getMaxYears(timeframe) {
    // Direct lookup first
    if (timeframe in TIMEFRAME_MAX_YEARS) {
        return TIMEFRAME_MAX_YEARS[timeframe];
    }

    // For any custom minute-based timeframe, derive dynamically
    const parsed = parseTimeframe(timeframe);
    if (!parsed) return null; // unparseable → allow (backend will validate)

    if (parsed.unit === 'm') {
        // Minutes: if < 15 min, cap by the minute value itself (generous)
        if (parsed.value < 15) {
            return Math.max(1, parsed.value); // e.g. 7m → 7 years
        }
        return null; // 15m+ → unlimited
    }

    // Hours, Days, Weeks, Months → no limit
    return null;
}

/**
 * Given a timeframe and the user-selected from/to dates, check whether
 * the range exceeds the allowed limit.
 *
 * Returns:
 *   { ok: true }                          – range is within limits
 *   { ok: false, maxYears, adjustedFrom, adjustedTo, message }
 *                                         – range was clamped
 */
export function enforceTimeframeLimit(timeframe, fromStr, toStr) {
    const maxYears = getMaxYears(timeframe);

    // No limit → always OK
    if (maxYears == null) {
        return { ok: true };
    }

    const from = new Date(fromStr);
    const to = new Date(toStr);

    // Calculate the difference in years (approximate but good enough)
    const diffMs = to.getTime() - from.getTime();
    const diffYears = diffMs / (365.25 * 24 * 60 * 60 * 1000);

    if (diffYears <= maxYears) {
        return { ok: true };
    }

    // Clamp: keep the "to" date, pull "from" forward
    const adjustedFrom = new Date(to);
    adjustedFrom.setFullYear(adjustedFrom.getFullYear() - maxYears);

    const adjustedFromStr = adjustedFrom.toISOString().split('T')[0];
    const adjustedToStr = to.toISOString().split('T')[0];

    return {
        ok: false,
        maxYears,
        adjustedFrom: adjustedFromStr,
        adjustedTo: adjustedToStr,
        message: `⚠ For ${timeframe} timeframe, the maximum supported backtest range is ${maxYears} year${maxYears > 1 ? 's' : ''}. The date range has been automatically adjusted.`,
    };
}
