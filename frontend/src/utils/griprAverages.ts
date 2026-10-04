/** The average a chart's reference line shows: the mean over the periods shown, leaving out the
 * last one when it's the period still in progress -- a half-finished month would drag the
 * average down and make every complete month look "above average". `count` is how many
 * periods it's over, so the legend can say so. */
export function completedPeriodAverage(values: number[], lastIsInProgress: boolean): { average: number; count: number } | null {
  const complete = lastIsInProgress ? values.slice(0, -1) : values;
  if (complete.length === 0) return null;
  return { average: complete.reduce((sum, v) => sum + v, 0) / complete.length, count: complete.length };
}
