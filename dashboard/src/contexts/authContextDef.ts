import { createContext } from 'react';
import type { User } from 'firebase/auth';
import type { UserProfile } from '../types';

export interface AuthContextType {
  user: User | null;
  profile: UserProfile | null;
  isAdmin: boolean;
  loading: boolean;
  loginWithEmail: (email: string, pass: string) => Promise<void>;
  signupWithEmail: (email: string, pass: string) => Promise<void>;
  loginWithGoogle: (googleEmail?: string) => Promise<void>;

  loginAsMock: (role: 'admin' | 'user') => void;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | null>(null);
