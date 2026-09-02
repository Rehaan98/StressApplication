/**
 * Plain-language labels: translate technical/clinical jargon into
 * simple, friendly words that any user can understand.
 */

// Raw feature names (from the ML engine) → friendly descriptions
export const FEATURE_LABELS: Record<string, string> = {
  total_pss: 'Overall stress level',
  pss_q1: 'Stress from unexpected events',
  pss_q2: 'Feeling in control of life',
  pss_q3: 'Feeling nervous or stressed',
  pss_q4: 'Confidence in handling problems',
  pss_q5: 'Feeling things are going well',
  pss_q6: 'Ability to calm irritations',
  pss_q7: 'Feeling on top of things',
  pss_q8: 'Anger from things out of control',
  pss_q9: 'Control over time use',
  pss_q10: 'Feeling difficulties pile up',
  hrv_sdnn: 'Heart rhythm calmness',
  heart_rate: 'Heart rate',
  hrv_to_hr_ratio: 'Heart rhythm balance',
  sleep_hours: 'Sleep duration',
  sleep_efficiency: 'Sleep quality',
  sleep_deficiency_index: 'Sleep deficit',
  physical_activity_min: 'Daily activity',
  work_hours: 'Work hours',
  screen_time_hours: 'Screen time',
  breaks_per_day: 'Breaks per day',
  work_stress_factor: 'Work pressure',
  sentiment_score: 'Mood balance',
  anxiety_score: 'Anxiety level',
  composite_strain_index: 'Overall strain',
  social_support: 'Social support',
  loneliness_score: 'Loneliness level',
  burnout_score: 'Burnout level',
};

export function friendlyFeature(feature: string): string {
  return FEATURE_LABELS[feature] ?? feature.replace(/_/g, ' ');
}

// Simple dictionary for turning raw feature values into plain descriptions
const VALUE_DESCRIPTORS: Record<string, Record<string, string>> = {
  total_pss: { high: 'your overall stress score is high', low: 'your overall stress score is low' },
  hrv_sdnn: { high: 'your heart rhythm is calm', low: 'your heart rhythm is unsettled' },
  anxiety_score: { high: 'your anxiety level is raised', low: 'your anxiety level is low' },
  sleep_hours: { high: 'you are sleeping well', low: 'you are not sleeping enough' },
  sleep_efficiency: { high: 'your sleep quality is good', low: 'your sleep quality is poor' },
  sentiment_score: { high: 'your mood is positive', low: 'your mood is low' },
  work_hours: { high: 'you work long hours', low: 'your work hours are manageable' },
  screen_time_hours: { high: 'your screen time is high', low: 'your screen time is low' },
  breaks_per_day: { high: 'you take regular breaks', low: 'you rarely take breaks' },
  physical_activity_min: { high: 'you are physically active', low: 'you get little physical activity' },
  work_stress_factor: { high: 'your work pressure is high', low: 'your work pressure is manageable' },
  composite_strain_index: { high: 'your overall strain is high', low: 'your overall strain is low' },
  sleep_deficiency_index: { high: 'your sleep deficit is high', low: 'your sleep deficit is low' },
  heart_rate: { high: 'your heart rate is raised', low: 'your heart rate is calm' },
};

const DEFAULT_DESCRIPTOR = { high: 'this factor is raised', low: 'this factor is low' };

/**
 * Translate a LIME rule string like "total_pss > 22.0" or "hrv_sdnn <= 48.5"
 * into a friendly sentence such as "Your overall stress score is high".
 */
export function friendlyRule(rule: string): string {
  const match = rule.match(/^([a-z_0-9]+)\s*(>=|<=|>|<|=)\s*([0-9.\-]+)$/i);
  if (!match) return rule;
  const [, feature, op] = match;
  const name = FEATURE_LABELS[feature] ?? feature.replace(/_/g, ' ');
  const desc = VALUE_DESCRIPTORS[feature] ?? DEFAULT_DESCRIPTOR;
  const isHigh = op === '>' || op === '>=' || (op === '=' && Number(match[3]) > 0);
  return `${name} — ${isHigh ? desc.high : desc.low}`;
}

// Intervention categories from the knowledge base → friendly labels
export const CATEGORY_LABELS: Record<string, string> = {
  'Cognitive Behavioral Therapy (CBT)': 'Thinking & mindset',
  'Autonomic Nervous System Regulation': 'Breathing & calm',
  'Sleep Hygiene & Recovery': 'Sleep & rest',
  'Workload & Screen Ergonomics': 'Work & screen habits',
  'Physical Activity & Somatic Discharge': 'Movement & body',
  'Mindfulness & Affective Regulation': 'Mindfulness & emotions',
  'Anger Regulation': 'Calming anger',
  'Fear & Anxiety Regulation': 'Calming fear',
  'Sadness & Mood Elevation': 'Lifting low mood',
  'Surprise & Overstimulation Recovery': 'Settling after overload',
  'Disgust & Somatic Release': 'Releasing tension',
  'Positive Emotion Preservation': 'Enjoying good moments',
};

export function friendlyCategory(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}

// Stress levels → friendly short labels
export const LEVEL_LABELS: Record<string, string> = {
  Low: 'Low',
  Moderate: 'Moderate',
  High: 'High',
  Severe: 'Severe',
};

// Plain explanations of stress levels
export const LEVEL_EXPLANATIONS: Record<string, string> = {
  Low: 'You seem relaxed. Keep up whatever you are doing!',
  Moderate: 'You are handling things, but a little extra care could help.',
  High: 'Stress is building up. Try one of the coping exercises below.',
  Severe: 'You are under heavy strain. Please consider one of the exercises below and talk to someone you trust.',
};
