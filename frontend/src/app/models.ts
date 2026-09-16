export type Sign = "1" | "X" | "2";
export type Outcome = "home" | "draw" | "away";
export type Mode = "optimal" | "safe" | "value";
export interface Probabilities {
  home: number;
  draw: number;
  away: number;
}
export const OUTCOMES: { key: Outcome; sign: Sign }[] = [
  { key: "home", sign: "1" },
  { key: "draw", sign: "X" },
  { key: "away", sign: "2" },
];
export interface Snapshot {
  source: string;
  recorded_at?: string | null;
  valid_at?: string | null;
  retrieved_at?: string | null;
  source_updated_at?: string | null;
}
export interface CouponMatch {
  marketSource?: string | null;
  marketQuality?: {
    bookmaker_count?: number;
    confidence?: string;
    dispersion?: Probabilities;
    oldest_bookmaker_update?: string;
    newest_bookmaker_update?: string;
  } | null;
  number: number;
  homeTeam: string;
  awayTeam: string;
  date: string;
  league: string;
  crowd: Probabilities;
  marketOdds: Probabilities;
  oddsSnapshot?: Snapshot;
  crowdSnapshot?: Snapshot;
  kickoffAt?: string | null;
  providerEventId?: string | null;
  crowdMatchId?: string | null;
  competition?: string | null;
  modelCoverage?: boolean | null;
}
export interface Coupon {
  id: string;
  week: number;
  date: string;
  demo: boolean;
  matches: CouponMatch[];
  drawNumber?: number | null;
  salesCloseAt?: string | null;
  retrievedAt?: string | null;
  dataSource?: "manual" | "svenska-spel" | "demo";
  drawStatus?: string | null;
}
export interface FormMatch {
  date: string;
  opponent: string;
  venue: string;
  points: number;
  goals_for: number;
  goals_against: number;
  shots: number | null;
  sot: number | null;
}
export interface MatchAnalysis extends CouponMatch {
  matchId: string;
  activeModel?: string;
  modelVersion?: string;
  newsAffectsProbabilities?: boolean;
  model: Probabilities;
  market: Probabilities;
  edge: Probabilities;
  value: Probabilities;
  valueFloorApplied: boolean;
  source: "ml" | "market_fallback" | "market_baseline";
  warnings: string[];
  features: Record<string, number | string | null>;
  form: { home: FormMatch[]; away: FormMatch[] };
  recommendation: Sign[];
  mostLikely: Sign;
  bestValue: Sign;
  explanation: string;
}
export interface SystemCost {
  rowCount: number;
  cost: number;
  costPerRow: number;
  singles: number;
  doubles: number;
  triples: number;
}
export interface OptimizedSystem extends SystemCost {
  selections: Sign[][];
  budget: number;
  mode: Mode;
  objectiveScore: number;
  metrics: {
    coverageScore: number;
    allCorrectProbability: number;
    riskScore: number;
    valueIndex: number;
  };
}
export interface Insight {
  description?: string;
  title: string;
  number: number;
  homeTeam: string;
  awayTeam: string;
  sign: Sign;
  model: number;
  crowd: number;
  edge: number;
  value: number;
}
export interface Analysis {
  inputCoupon?: Coupon;
  drawSnapshot?: LiveDraw;
  movement?: Movement[];
  couponId: string;
  demo: boolean;
  matches: MatchAnalysis[];
  system: OptimizedSystem;
  insights: Insight[];
  analyzedAt: string;
  drawNumber?: number;
  snapshotId?: string;
  changes?: { number: number; previous: Sign[]; current: Sign[] }[];
}

export interface LiveMatch {
  number: number;
  match_id: string;
  provider_event_id: string | null;
  home_team: string;
  away_team: string;
  source_home_team: string;
  source_away_team: string;
  home_team_id: string | null;
  away_team_id: string | null;
  kickoff_at: string | null;
  competition: string | null;
  league: string | null;
  model_coverage: boolean;
  status: string | null;
  crowd: Probabilities | null;
  crowd_source_updated_at: string | null;
  market_odds: Probabilities | null;
  issues: string[];
}
export interface LiveDraw {
  draw_number: number;
  draw_date: string;
  sales_close_at: string;
  sales_open_at: string | null;
  status: string;
  retrieved_at: string;
  provider: string;
  source: string;
  matches: LiveMatch[];
  issues: string[];
}
export interface Movement {
  number: number;
  observations: number;
  since_previous: Probabilities | null;
  since_first: Probabilities | null;
}
export interface LiveState {
  manual_odds_matches?: number;
  draw: LiveDraw | null;
  coupon: Coupon | null;
  analysis_ready: boolean;
  stale: boolean;
  enabled: boolean;
  message: string | null;
  issues: string[];
  available_draws: {
    draw_number: number;
    sales_close_at: string;
    status: string;
  }[];
  health: {
    status: string;
    last_successful_fetch: string | null;
    issue: string | null;
  };
  mapping?: {
    references: number;
    mapped: number;
    unmapped: string[];
    supported_model_matches: number;
  };
  movement?: Movement[];
}
export interface CrowdObservation {
  id: string;
  recorded_at: string;
  retrieved_at: string;
  source_updated_at: string | null;
  crowd: Probabilities;
  is_pre_close_snapshot: boolean;
  source: string;
}
export interface ArchiveRow {
  draw_number: number;
  draw_date: string;
  sales_close_at: string;
  status: string;
  matches: number;
  crowd_data_available: boolean;
  pre_close_available: boolean;
  result_available: boolean;
  payout_available: boolean;
  snapshots: number;
  system: {
    created_at: string;
    model: { active_model: string };
    system: OptimizedSystem;
    max_covered_correct: number | null;
  } | null;
}
export interface ArchiveDetail {
  draw: LiveDraw;
  as_of: string;
  selection: string;
  message: string | null;
  snapshots: { id: string; recorded_at: string; retrieved_at: string }[];
  observation: { draw: LiveDraw; recorded_at: string } | null;
  crowd: Record<string, CrowdObservation>;
  market: Record<
    string,
    {
      odds: Probabilities;
      market: Probabilities;
      recorded_at: string;
      source: string;
    }
  >;
  optimizer: {
    analysis: Analysis;
    created_at: string;
    model: { active_model: string };
    changes: { number: number; previous: Sign[]; current: Sign[] }[];
  } | null;
  result: {
    matches: {
      number: number;
      outcome: Sign | null;
      home_goals: number | null;
      away_goals: number | null;
      cancelled: boolean;
    }[];
    payouts: {
      correct: number;
      winners: number | null;
      amount: number | null;
    }[];
    recorded_at: string;
  } | null;
}
export interface Scores {
  log_loss: number;
  brier_score: number;
  accuracy: number;
  matches: number;
  ece?: number;
  calibration?: {
    lower: number;
    upper: number;
    count: number;
    predicted: number;
    observed: number;
  }[][];
}
export interface Period {
  from: string;
  to: string;
  seasons: string[];
  matches: number;
}
export interface ModelMetadata {
  modelVersion?: string;
  activeModel?: string;
  activeModelLabel?: string;
  evaluation?: ModelEvaluation;
  trained_at: string;
  training_matches: number;
  dataset_matches: number;
  data_through: string;
  leagues: string[];
  seasons: string[];
  features: string[];
  dataset_leagues: Record<string, number>;
  split: Record<
    "train" | "validation" | "test" | "production_fit" | "evaluation_fit",
    Period
  >;
  test: { market: Scores; ml: Scores };
  validation: { market: Scores; ml: Scores };
}
export interface AblationScore extends Scores {
  delta_log_loss: number;
  delta_brier: number;
  winning_seasons: number;
}
export interface ModelEvaluation {
  overall: Record<string, Scores>;
  byLeague: Record<string, Record<string, Scores>>;
  bySeason: Record<string, Record<string, Scores>>;
  byMarketBucket: Record<string, Record<string, Scores | null>>;
  ablation: Record<string, AblationScore>;
  developmentAblation: Record<string, AblationScore>;
  disagreement: Record<
    string,
    Record<string, { matches: number; delta_log_loss: number | null }>
  >;
  selection: {
    active: string;
    v2_candidate: string;
    reason: string;
    development_seasons: string[];
  };
  auditSeason: string;
  audit: Record<string, Scores>;
}
export interface NewsSignal {
  id: string;
  event_id: string;
  team: string;
  player: string | null;
  type: string;
  direction: "positive" | "negative" | "neutral";
  summary: string;
  evidence: string;
  status_label: string;
  source_count: number;
  independent_source_count: number;
  first_published_at: string;
  last_confirmed_at: string;
  recorded_at: string;
  source_article_ids: string[];
  has_conflicting_reports: boolean;
  extractor: string;
}
export interface NewsSource {
  id: string;
  version_id: string;
  title: string;
  url: string;
  publisher: string;
  published_at: string | null;
  retrieved_at: string;
  source_tier: number;
}
export interface MatchNews {
  configured: boolean;
  extraction: string;
  extractionConfigured: boolean;
  message: string | null;
  match_id: string;
  last_checked_at: string | null;
  signals: NewsSignal[];
  sources: NewsSource[];
  source_count: number;
  error: string | null;
  stale: boolean;
  newsAffectsProbabilities: boolean;
}
export interface ModelStatus {
  trained: boolean;
  datasetAvailable: boolean;
  metadata: ModelMetadata | null;
  error: string | null;
  importReport: { failed: { file: string; error: string }[] } | null;
}
export interface AppConfig {
  budgetPresets: number[];
  costPerRow: number;
  leagues: Record<string, string>;
  crowdTolerance: number;
  valueFloor: number;
}
