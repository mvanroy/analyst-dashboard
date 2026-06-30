# Breakout Radar Engine Contract

This file defines what each engine must prove. The scanner should not pass a
setup because several loosely bullish indicators average together. Each engine
must answer its own question with explicit proof rules.

No new indicators should be added without first deciding which existing proof
rule failed and why the existing variables cannot answer it.

## Engine Questions

```text
Compression: Is energy actually stored?
Structure: Are buyers actually pressing resistance?
Participation: Are buyers actually entering constructively?
Momentum: Is impulse actually improving?
Acceptance: Is price actually being accepted, not rejected?
Magnitude: Is there enough room for the move to matter?
```

## Compression

Question: `Is energy actually stored?`

Existing variables:

- ATR percentile
- Bollinger Band Width percentile
- Historical Volatility percentile
- Donchian Width percentile
- Range Compression Ratio
- Keltner Width percentile
- Standard Deviation percentile

Proof rules:

```text
At least 4 of 7 compression metrics must be Strong or Moderate.
ATR percentile must not be > 70.
BB width percentile must not be > 70.
Range Compression Ratio must be <= 1.10.
If ATR or BB width is expanded, compression score is capped at 45.
If range ratio is too loose, compression score is capped at 55.
```

Failure meaning:

```text
Low volatility in one metric is not enough.
Already-expanded volatility is not stored energy.
Loose range behavior is not compression.
```

## Structural Pressure

Question: `Are buyers actually pressing resistance?`

Existing variables:

- Higher lows
- Pullback depth
- Resistance test count
- Seller reaction size
- Time near resistance
- Triangle / trendline convergence
- Support holds
- Lower wick rejection
- Breakout level distance
- Prior local resistance source
- Recent base tightness in ATR
- Current price extension from base low in ATR
- Recent candle body overlap
- Volume dry-up into the base

Proof rules:

```text
Resistance must be a prior local level, not the current breakout candle's high.
Resistance tests are distinct swing highs only.
Resistance tests must be within 2% of resistance.
Resistance tests must be separated by at least 6 bars.
Support holds are distinct swing lows only.
Support holds must be within 1.5% of support.
Recent base range should be tight relative to ATR.
Price should not already be heavily extended from the recent base low.
Recent candle bodies should overlap enough to prove a coil, not wide chop.
Volume should dry into the base instead of expanding messily before the alert.
If price is more than 8% below resistance, structure is capped at 50.
```

Failure meaning:

```text
Repeated candles are not repeated attacks.
Repeated candles near support are not repeated holds.
Structure cannot be high if price is not actually pressing resistance.
Recovery momentum is not the same thing as a tight coil.
Wide overlapping chop is not a controlled base.
Already-travelled price is not an early breakout setup.
```

## Participation

Question: `Are buyers actually entering constructively?`

Existing variables:

- Relative volume
- Coil-relative RVOL context
- Volume z-score
- Volume percentile
- Volume trend
- OBV trend
- Chaikin Money Flow
- VWAP relationship

Proof rules:

```text
At least 3 participation metrics must score >= 75.
If coil quality is good and RVOL >= 1.3, participation is beginning.
RVOL >= 1.3 is not a standalone signal; without valid coil context it is ignored.
RVOL >= 1.5 remains the stronger participation confirmation.
VWAP should prove constructive entry or reclaim behaviour.
Price slightly below/near VWAP can still be constructive if VWAP is rising
or the candle is reclaiming with a strong close position.
Price meaningfully below VWAP without reclaim behaviour caps participation at 45.
Slightly negative CMF is weak, but not an automatic failure.
Deeply negative CMF caps participation at 45.
If volume spikes on a rejection candle, participation is capped at 50.

Rejection candle:
  upper wick > 45%
  OR close position < 50% of candle range.
```

Failure meaning:

```text
Volume is not constructive if price is below VWAP.
Volume is not accumulation if CMF is negative.
Volume on rejection is not buyer participation.
RVOL without a valid coil is not enough to prove participation.
```

## Momentum

Question: `Is impulse actually improving?`

Existing variables:

- RSI
- RSI slope
- ADX
- ADX slope
- MACD histogram
- Rate of Change
- Money Flow Index

Proof rules:

```text
At least 4 momentum metrics must score >= 75.
RSI slope must be positive.
ADX slope must be positive.
MACD histogram must not be deteriorating.
If RSI > 75, momentum is capped at 45.
If MFI > 80, momentum is capped at 45.
If RSI/ADX/MACD deterioration is present, momentum is capped near 50.
```

Failure meaning:

```text
High ADX is not enough if ADX is falling.
High RSI is not enough if RSI slope is falling or overheated.
Positive momentum must be improving, not merely present.
```

## Price Acceptance

Question: `Is price actually being accepted, not rejected?`

Existing variables:

- Candle close position
- Candle body %
- Upper wick %
- Consecutive closes near resistance
- Close outside range
- Retest quality
- Pullback volume after breakout attempt
- VWAP acceptance

Proof rules:

```text
At least 4 acceptance metrics must score >= 75.
Upper wick > 45% caps acceptance at 45.
Body < 25% caps acceptance at 55.
No current VWAP hold caps acceptance at 50.
Near-resistance closes only count properly if candle quality is controlled.

Controlled candle:
  close position >= 65%
  body >= 45%
  upper wick <= 35%
```

Failure meaning:

```text
Location near resistance is not acceptance.
A long upper wick is rejection.
A weak candle body is not commitment.
VWAP chop is not acceptance.
```

## Magnitude

Question: `Is there enough room for the move to matter?`

Existing variables:

- ATR scale
- Base height
- Raw ATR/base target
- Nearest structural target
- Realistic capped target
- Air above %
- Reward to invalidation
- Target capped flag

Proof rules:

```text
Magnitude is a separate axis from readiness.
ATR-scaled target is an input, not the final target.
Measured move must be snapped to real structure.
If the measured target is capped by nearby supply, quote the realistic level.
Air above and reward-to-invalidation must be sufficient for the setup to matter.
```

Failure meaning:

```text
A setup can be ready but not worth trading.
Readiness cannot compensate for poor room.
Magnitude should not inflate readiness; it gates opportunity quality.
```

## Classification Gates

These gates are applied after the weighted score is calculated. A weighted score
alone cannot promote a setup if a required proof engine is missing.

### Developing Setup

```text
overall >= 65
compression >= 70
structure >= 60
participation >= 60
momentum >= 50
acceptance >= 55
magnitude >= 50
distance to resistance <= 10%
```

### High Watch

```text
overall >= 75
compression >= 70
structure >= 65
participation >= 65
momentum >= 55
acceptance >= 60
magnitude >= 50
distance to resistance <= 6%
```

### Breakout Radar Priority

```text
overall >= 85
compression >= 75
structure >= 70
participation >= 70
momentum >= 65
acceptance >= 65
magnitude >= 60
distance to resistance <= 3%
```

## Tuning Rule

When backtesting shows false positives, do not add warning labels first.

Instead:

```text
Find which engine allowed the false positive through.
Identify which existing variable failed to prove the engine question.
Tighten, cap, or remove that variable from the engine logic.
Backtest the same sample again.
```

Warnings are secondary. Engine proof comes first.
