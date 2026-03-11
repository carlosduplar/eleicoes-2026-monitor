/**
 * TypeScript type definitions for all data/*.json files.
 * Source of truth: docs/schemas/*.schema.json
 *
 * These types are used by the React frontend (site/src/).
 * Python scripts produce data conforming to these shapes.
 */

// --- Common ---

export type CandidateSlug =
  | 'lula'
  | 'flavio-bolsonaro'
  | 'tarcisio'
  | 'caiado'
  | 'zema'
  | 'ratinho-jr'
  | 'eduardo-leite'
  | 'aldo-rebelo'
  | 'renan-santos';

export type TopicId =
  | 'economia'
  | 'seguranca'
  | 'saude'
  | 'educacao'
  | 'meio_ambiente'
  | 'corrupcao'
  | 'armas'
  | 'privatizacao'
  | 'previdencia'
  | 'politica_ext'
  | 'lgbtq'
  | 'aborto'
  | 'indigenas'
  | 'impostos'
  | 'midia'
  | 'eleicoes';

export type SourceCategory =
  | 'mainstream'
  | 'politics'
  | 'magazine'
  | 'international'
  | 'institutional'
  | 'party';

export type ArticleStatus = 'raw' | 'validated' | 'curated';
export type SentimentLabel = 'positivo' | 'neutro' | 'negativo';
export type Stance = 'favor' | 'against' | 'neutral' | 'unclear';
export type Confidence = 'high' | 'medium' | 'low';
export type PollType = 'estimulada' | 'espontanea';
export type PipelineTier = 'foca' | 'editor' | 'editor-chefe';

// --- Articles (data/articles.json) ---

export interface EditHistoryEntry {
  tier: PipelineTier;
  at: string; // ISO 8601
  provider: string;
  action: 'collected' | 'validated' | 'curated';
  changes?: string[];
}

export interface Article {
  id: string; // sha256(url)[:16]
  url: string;
  title: string;
  source: string;
  source_category?: SourceCategory;
  published_at: string; // ISO 8601
  collected_at: string; // ISO 8601
  status: ArticleStatus;
  relevance_score?: number; // 0.0-1.0
  candidates_mentioned?: CandidateSlug[];
  topics?: TopicId[];
  narrative_cluster_id?: string | null;
  summaries?: {
    'pt-BR'?: string;
    'en-US'?: string;
  };
  sentiment_score?: number; // -1 to +1
  sentiment_per_candidate?: Partial<Record<string, SentimentLabel>>;
  confidence_score?: number; // 0.0-1.0
  prominence_score?: number; // 0.0-1.0
  needs_editor_review?: boolean;
  editor_note?: string | null;
  edit_history?: EditHistoryEntry[];
  ai_provider_foca?: string;
  ai_provider_editor?: string;
  disclaimer_pt?: string;
  disclaimer_en?: string;
}

// --- Sentiment (data/sentiment.json) ---

export interface Sentiment {
  updated_at: string; // ISO 8601
  article_count: number;
  methodology_url: '/metodologia';
  disclaimer_pt: string;
  disclaimer_en: string;
  by_topic: Record<string, Record<string, number>>; // candidate -> topic -> score
  by_source: Record<string, Record<string, number>>; // candidate -> source_cat -> score
}

// --- Quiz (data/quiz.json) ---

export interface QuizOption {
  id: string; // opt_a, opt_b, etc.
  text_pt: string;
  text_en: string;
  weight: -2 | -1 | 0 | 1 | 2;
  candidate_slug: CandidateSlug;
  source_pt?: string;
  source_en?: string;
  confidence: 'high' | 'medium';
}

export interface QuizTopic {
  divergence_score: number; // 0.0-1.0
  question_pt: string;
  question_en: string;
  options: QuizOption[];
}

export interface Quiz {
  generated_at: string; // ISO 8601
  ordered_topics: TopicId[];
  topics: Record<string, QuizTopic>;
}

// --- Polls (data/polls.json) ---

export interface PollResult {
  candidate_slug: CandidateSlug;
  candidate_name: string;
  percentage: number; // 0-100
  variation?: number | null;
}

export interface Poll {
  id: string; // sha256(institute + published_at)[:16]
  institute: string;
  published_at: string; // ISO 8601
  collected_at: string; // ISO 8601
  type: PollType;
  sample_size?: number;
  margin_of_error?: number;
  confidence_level?: number;
  tse_registration?: string | null;
  source_url?: string;
  results: PollResult[];
}

// --- Candidates (data/candidates.json) ---

export interface Candidate {
  slug: CandidateSlug;
  name: string;
  full_name: string;
  party: string;
  party_site: string;
  color: string; // hex
  twitter: string;
  status: 'pre-candidate' | 'speculated' | 'confirmed' | 'withdrawn';
  bio_pt: string;
  bio_en: string;
  photo_url: string | null;
  tse_registration_url: string | null;
}

export interface CandidatesFile {
  candidates: Candidate[];
}

// --- AI Usage (data/ai_usage.json) ---

export type AIUsage = Record<string, number>; // "{provider}_{YYYY-MM-DD}" -> count

// --- Affinity Result (client-side) ---

export interface AffinityResult {
  slug: CandidateSlug;
  affinity: number; // 0-100
  byTopic: Record<string, number>; // topic -> similarity 0.0-1.0
}
