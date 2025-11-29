/**
 * API クライアント
 */
import axios from 'axios';

// Graphiti MCP Server (graph operations: search, facts, episodes)
const GRAPHITI_API_BASE_URL = import.meta.env.VITE_GRAPHITI_API_URL || 'http://localhost:30547';

// Search Bot Backend (chat with LLM)
const CHAT_API_BASE_URL = import.meta.env.VITE_CHAT_API_URL || 'http://localhost:20001/api';

// API client for graph operations (search, facts, episodes)
const graphitiApi = axios.create({
  baseURL: GRAPHITI_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// API client for chat functionality
const chatApi = axios.create({
  baseURL: CHAT_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Backward compatibility
const api = graphitiApi;

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

export interface CitationInfo {
  episode_uuid: string;
  episode_name: string;
  source: string;
  source_description: string;
  created_at: string | null;
  source_url: string | null;
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
  citations?: CitationInfo[]; // Citations with source URLs
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
  fact: string;
  source_node_uuid?: string;
  target_node_uuid?: string;
  attributes?: Record<string, any>;
}

export interface UpdateFactResponse {
  status: string;
  old_uuid: string;
  new_uuid: string;
  message: string;
  new_edge?: EntityEdge; // The newly created edge with citations
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
    const response = await chatApi.post<ChatResponse>('/chat', request);
    return response.data;
  },
};

// Backend search response type
interface GraphSearchResponse {
  message: string;
  search_type: string;
  results: EntityEdge[];
  count: number;
}

export const searchAPI = {
  async search(request: ManualSearchRequest): Promise<GraphSearchResponse> {
    const response = await api.post<GraphSearchResponse>('/graph/search', {
      query: request.query,
      search_type: 'facts',
      max_results: request.limit || 20
    });
    return response.data;
  },
};

export const factsAPI = {
  async updateFact(edgeUuid: string, request: UpdateFactRequest): Promise<UpdateFactResponse> {
    const response = await api.patch<UpdateFactResponse>(`/graph/facts/${edgeUuid}`, request);
    return response.data;
  },
};

export interface DeleteEpisodeResponse {
  status: string;
  uuid: string;
  message: string;
}

export const episodesAPI = {
  async addEpisode(request: AddEpisodeRequest): Promise<AddEpisodeResponse> {
    const response = await api.post<AddEpisodeResponse>('/episodes', request);
    return response.data;
  },

  async deleteEpisode(uuid: string): Promise<DeleteEpisodeResponse> {
    const response = await api.delete<DeleteEpisodeResponse>(`/graph/episodes/${uuid}`);
    return response.data;
  },
};

export default api;
