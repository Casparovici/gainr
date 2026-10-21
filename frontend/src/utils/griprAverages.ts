/** The average a chart's reference line shows: the mean over the periods shown, leaving out the
 * last one when it's the period still in progress -- a half-finished month would drag the
 * average down and make every complete month look "above average". `count` is how many
 * periods it's over, so the legend can say so. */
export function completedPeriodAverage(values: number[], lastIsInProgress: boolean): { average: number; count: number } | null {
  const complete = lastIsInProgress ? values.slice(0, -1) : values;
  if (complete.length === 0) return null;
  return { average: complete.reduce((sum, v) => sum + v, 0) / complete.length, count: complete.length };
}

/** Splits a series' values into a solid part and a dashed one, so the last point (a period still in
 * progress) is drawn as unfinished. The dashed part keeps the last completed point as its anchor so
 * the two lines join. Nothing is dashed when the series ends in a finished period. */
export function splitInProgress(values: number[], inProgress: boolean): { solid: (number | null)[]; partial: (number | null)[] } {
  const last = values.length - 1;
  if (!inProgress || last < 1) return { solid: [...values], partial: values.map(() => null) };
  return {
    solid: values.map((v, i) => (i === last ? null : v)),
    partial: values.map((v, i) => (i >= last - 1 ? v : null)),
  };
}
