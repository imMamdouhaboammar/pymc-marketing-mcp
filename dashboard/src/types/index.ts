export interface UserProfile {
  uid: string;
  email: string;
  displayName?: string;
  role: 'user' | 'admin';
  createdAt: string;
  totalRequests: number;
}

export interface ApiKeyItem {
  id: string;
  name: string;
  keySecret?: string; // Full secret shown upon creation
  keyPrefix: string;
  ownerUid: string;
  ownerEmail: string;
  status: 'active' | 'revoked';
  createdAt: string;
  lastUsedAt?: string;
  requestCount: number;
}

export interface UsageLogItem {
  id: string;
  ownerUid: string;
  ownerEmail?: string;
  keyId?: string;
  toolName: string;
  status: 'success' | 'error';
  latencyMs?: number;
  timestamp: string;
}

export const ADMIN_EMAILS = [
  'mamdouhfces1997@gmail.com',
  'omar.hassan.gebally@gmail.com',
  'admin@pymc-marketing.com'
];

