/**
 * Backend Credential Control Plane API client.
 * API keys are created and verified by the backend. Raw secrets are shown only once at creation.
 */

export interface CredentialDTO {
  credential_id: string;
  tenant_id: string;
  owner_subject: string;
  name: string;
  prefix: string;
  scopes: string[];
  status: 'active' | 'revoked';
  created_at: string;
  revoked_at: string | null;
  last_used_at: string | null;
}

export interface CreateCredentialResponse {
  credential: CredentialDTO;
  secret: string;
}

export async function fetchCredentials(authToken?: string): Promise<CredentialDTO[]> {
  const headers: Record<string, string> = {};
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }
  const response = await fetch('/control/credentials', { headers });
  if (!response.ok) {
    throw new Error(`Failed to fetch credentials (${response.status})`);
  }
  const data = await response.json();
  return data.credentials || [];
}

export async function createCredential(
  name: string,
  scopes: string[] = ['marketing:read', 'marketing:model', 'marketing:decide'],
  authToken?: string
): Promise<CreateCredentialResponse> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }
  const response = await fetch('/control/credentials', {
    method: 'POST',
    headers,
    body: JSON.stringify({ name, scopes }),
  });
  if (!response.ok) {
    throw new Error(`Failed to issue credential (${response.status})`);
  }
  return response.json();
}

export async function revokeCredential(credentialId: string, authToken?: string): Promise<CredentialDTO> {
  const headers: Record<string, string> = {};
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }
  const response = await fetch(`/control/credentials/${encodeURIComponent(credentialId)}`, {
    method: 'DELETE',
    headers,
  });
  if (!response.ok) {
    throw new Error(`Failed to revoke credential (${response.status})`);
  }
  const data = await response.json();
  return data.credential;
}
