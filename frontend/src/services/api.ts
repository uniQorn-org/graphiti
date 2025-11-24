/**
 * API クライアント
 */
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:20001/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 型定義
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface EntityNode {
  uuid: string;
  name: string;
  summary?: string;
  created_at: string;
  labels: string[];
  attributes: Record<string, any>;
}

export interface EntityEdge {
  uuid: string;
  source_node_uuid: string;
  target_node_uuid: string;
  name: string;
  fact: string;
  created_at: string;
  valid_at?: string;
  invalid_at?: string;
  expired_at?: string;
  episodes: string[];
  // 修正履歴フィールド
  updated_at?: string;
  original_fact?: string;
  update_reason?: string;
}

export interface SearchResult {
  nodes: EntityNode[];
  edges: EntityEdge[];
  total_count: number;
}

export interface ChatRequest {
  message: string;
  history: ChatMessage[];
  include_search_results: boolean;
}

export interface ChatResponse {
  answer: string;
  search_results?: SearchResult;
  sources: string[];
}

export interface ManualSearchRequest {
  query: string;
  limit?: number;
}

export interface UpdateFactRequest {
  edge_uuid: string;
  new_fact: string;
  reason?: string;
}

export interface UpdateFactResponse {
  success: boolean;
  message: string;
  updated_edge?: EntityEdge;
}

export interface AddEpisodeRequest {
  name: string;
  content: string;
  source?: string;
  source_description?: string;
}

export interface AddEpisodeResponse {
  success: boolean;
  message: string;
  episode_uuid?: string;
}

// API関数
export const chatAPI = {
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await api.post<ChatResponse>('/chat', request);
    return response.data;
  },
};

export const searchAPI = {
  async search(request: ManualSearchRequest): Promise<SearchResult> {
    const response = await api.post<SearchResult>('/search', request);
    return response.data;
  },
};

export const factsAPI = {
  async updateFact(edgeUuid: string, request: Omit<UpdateFactRequest, 'edge_uuid'>): Promise<UpdateFactResponse> {
    const response = await api.put<UpdateFactResponse>(`/facts/${edgeUuid}`, {
      edge_uuid: edgeUuid,
      ...request,
    });
    return response.data;
  },
};

export const episodesAPI = {
  async addEpisode(request: AddEpisodeRequest): Promise<AddEpisodeResponse> {
    const response = await api.post<AddEpisodeResponse>('/episodes', request);
    return response.data;
  },
};

export default api;
