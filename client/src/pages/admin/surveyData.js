// Data-shaping helpers for the admin survey/ratings charts.

export function buildSurveyComplianceChartData(surveyCompliance) {
  if (!surveyCompliance) return [];
  const totalUsers = surveyCompliance.users.length;
  return [...surveyCompliance.weeks].reverse().map((w, ri) => {
    const i = surveyCompliance.weeks.length - 1 - ri;
    const activeCount = surveyCompliance.users.filter(u => u.weeks[i].query_count > 0).length;
    const surveyedCount = surveyCompliance.users.filter(u => u.weeks[i].survey_submitted).length;
    return { week: w.label, totalUsers, activeUsers: activeCount, surveyed: surveyedCount };
  });
}

export function buildDailyRatingsData(items, timeframe) {
  const numDays = !timeframe || timeframe === 'all' ? 60 : Math.min(parseInt(timeframe, 10), 60);
  const dayKeys = [];
  const now = new Date();
  for (let i = numDays - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setUTCDate(d.getUTCDate() - i);
    dayKeys.push(d.toISOString().slice(0, 10));
  }
  const counts = {};
  dayKeys.forEach(d => {
    counts[d] = { up: 0, down: 0 };
  });
  items.forEach(item => {
    const k = item.created_at.slice(0, 10);
    if (counts[k]) {
      if (item.rating === 5) counts[k].up++;
      else if (item.rating === 1) counts[k].down++;
    }
  });
  return dayKeys.map(d => ({
    day: new Date(d + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }),
    ...counts[d],
  }));
}
