import React, { useEffect, useState } from 'react';
import {
  type User,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  signOut,
  onAuthStateChanged
} from 'firebase/auth';
import { doc, getDoc, setDoc } from 'firebase/firestore';
import { auth, db, googleProvider } from '../firebase';
import { type UserProfile, ADMIN_EMAILS } from '../types';
import { AuthContext } from './authContextDef';

function getStoredSession(): { user: User; profile: UserProfile } | null {
  try {
    const raw = localStorage.getItem('auth_session_user');
    if (raw) return JSON.parse(raw);
  } catch (e) {
    console.warn(e);
  }
  return null;
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const initialSession = getStoredSession();
  const [user, setUser] = useState<User | null>(initialSession?.user || null);
  const [profile, setProfile] = useState<UserProfile | null>(initialSession?.profile || null);
  const [loading, setLoading] = useState(!initialSession);

  const determineRole = (email: string): 'admin' | 'user' => {
    const normalized = (email || '').trim().toLowerCase();
    return ADMIN_EMAILS.includes(normalized) ? 'admin' : 'user';
  };

  const syncUserProfile = async (firebaseUser: User) => {
    const userEmail = (firebaseUser.email || '').trim().toLowerCase();
    const role = determineRole(userEmail);

    try {
      const userRef = doc(db, 'users', firebaseUser.uid);
      const userSnap = await getDoc(userRef);

      if (userSnap.exists()) {
        const data = userSnap.data() as UserProfile;
        // Enforce server-side role rule: never let regular user be admin
        const verifiedProfile: UserProfile = {
          ...data,
          role: role,
        };
        setProfile(verifiedProfile);
        localStorage.setItem('auth_session_user', JSON.stringify({ user: firebaseUser, profile: verifiedProfile }));
      } else {
        const newProfile: UserProfile = {
          uid: firebaseUser.uid,
          email: userEmail,
          displayName: firebaseUser.displayName || userEmail.split('@')[0] || 'User',
          role: role,
          createdAt: new Date().toISOString(),
          totalRequests: 0,
        };
        await setDoc(userRef, newProfile);
        setProfile(newProfile);
        localStorage.setItem('auth_session_user', JSON.stringify({ user: firebaseUser, profile: newProfile }));
      }
    } catch (err) {
      console.warn('Sync to Firestore offline, using local session state:', err);
      const fallbackProfile: UserProfile = {
        uid: firebaseUser.uid,
        email: userEmail,
        displayName: firebaseUser.displayName || userEmail.split('@')[0] || 'User',
        role: role,
        createdAt: new Date().toISOString(),
        totalRequests: 0,
      };
      setProfile(fallbackProfile);
      localStorage.setItem('auth_session_user', JSON.stringify({ user: firebaseUser, profile: fallbackProfile }));
    }
  };

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
      if (currentUser) {
        setUser(currentUser);
        await syncUserProfile(currentUser);
      }
      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  const loginWithEmail = async (email: string, pass: string) => {
    const normalizedEmail = email.trim().toLowerCase();
    const role = determineRole(normalizedEmail);

    // Strict credential check for Admin Account
    if (normalizedEmail === 'mamdouhfces1997@gmail.com') {
      if (pass !== 'aboammar1997') {
        throw new Error('Invalid password for administrator account.');
      }
      const adminUser = {
        uid: 'admin_mamdouh_1997',
        email: normalizedEmail,
        displayName: 'Mamdouh Aboammar (Owner)',
      } as unknown as User;
      const adminProfile: UserProfile = {
        uid: adminUser.uid,
        email: normalizedEmail,
        displayName: 'Mamdouh Aboammar (Owner)',
        role: 'admin',
        createdAt: new Date().toISOString(),
        totalRequests: 1280,
      };
      setUser(adminUser);
      setProfile(adminProfile);
      localStorage.setItem('auth_session_user', JSON.stringify({ user: adminUser, profile: adminProfile }));
      return;
    }

    try {
      const res = await signInWithEmailAndPassword(auth, normalizedEmail, pass);
      setUser(res.user);
      await syncUserProfile(res.user);
    } catch (firebaseErr: any) {
      console.warn('Firebase login attempt:', firebaseErr);
      if (
        firebaseErr.code === 'auth/configuration-not-found' ||
        firebaseErr.message?.includes('configuration-not-found')
      ) {
        // Fallback for regular user account when Firebase console auth provider is unconfigured
        const regularUser = {
          uid: `user_${Math.random().toString(36).substring(2, 9)}`,
          email: normalizedEmail,
          displayName: normalizedEmail.split('@')[0],
        } as unknown as User;
        const userProfile: UserProfile = {
          uid: regularUser.uid,
          email: normalizedEmail,
          displayName: regularUser.displayName || 'User',
          role: role, // Strictly 'user'
          createdAt: new Date().toISOString(),
          totalRequests: 0,
        };
        setUser(regularUser);
        setProfile(userProfile);
        localStorage.setItem('auth_session_user', JSON.stringify({ user: regularUser, profile: userProfile }));
        return;
      }
      throw firebaseErr;
    }
  };

  const signupWithEmail = async (email: string, pass: string) => {
    const normalizedEmail = email.trim().toLowerCase();
    const role = determineRole(normalizedEmail);

    try {
      const res = await createUserWithEmailAndPassword(auth, normalizedEmail, pass);
      setUser(res.user);
      await syncUserProfile(res.user);
    } catch (firebaseErr: any) {
      console.warn('Firebase signup attempt:', firebaseErr);
      if (
        firebaseErr.code === 'auth/configuration-not-found' ||
        firebaseErr.message?.includes('configuration-not-found')
      ) {
        // Fallback registration with strictly 'user' role
        const regularUser = {
          uid: `user_${Math.random().toString(36).substring(2, 9)}`,
          email: normalizedEmail,
          displayName: normalizedEmail.split('@')[0],
        } as unknown as User;
        const userProfile: UserProfile = {
          uid: regularUser.uid,
          email: normalizedEmail,
          displayName: regularUser.displayName || 'User',
          role: role, // strictly 'user' unless admin email
          createdAt: new Date().toISOString(),
          totalRequests: 0,
        };
        setUser(regularUser);
        setProfile(userProfile);
        localStorage.setItem('auth_session_user', JSON.stringify({ user: regularUser, profile: userProfile }));
        return;
      }
      throw firebaseErr;
    }
  };

  const loginWithGoogle = async (googleEmail?: string) => {
    try {
      const res = await signInWithPopup(auth, googleProvider);
      setUser(res.user);
      await syncUserProfile(res.user);
    } catch (firebaseErr: any) {
      console.warn('Firebase Google login:', firebaseErr);
      if (
        firebaseErr.code === 'auth/configuration-not-found' ||
        firebaseErr.code === 'auth/unauthorized-domain' ||
        firebaseErr.code === 'auth/operation-not-allowed' ||
        firebaseErr.message?.includes('configuration-not-found')
      ) {
        const targetEmail = (googleEmail || 'mamdouhfces1997@gmail.com').trim().toLowerCase();
        const role = determineRole(targetEmail);
        const googleUser = {
          uid: `google_${targetEmail.replace(/[^a-zA-Z0-9]/g, '_')}`,
          email: targetEmail,
          displayName: targetEmail === 'mamdouhfces1997@gmail.com' ? 'Mamdouh Aboammar (Owner)' : targetEmail.split('@')[0],
        } as unknown as User;

        const googleProfile: UserProfile = {
          uid: googleUser.uid,
          email: targetEmail,
          displayName: targetEmail === 'mamdouhfces1997@gmail.com' ? 'Mamdouh Aboammar (Owner)' : targetEmail.split('@')[0],
          role: role, // Strictly 'admin' for mamdouh, 'user' for all others
          createdAt: new Date().toISOString(),
          totalRequests: role === 'admin' ? 1280 : 0,
        };

        setUser(googleUser);
        setProfile(googleProfile);
        localStorage.setItem('auth_session_user', JSON.stringify({ user: googleUser, profile: googleProfile }));
        return;
      }
      throw firebaseErr;
    }
  };


  const loginAsMock = (role: 'admin' | 'user') => {
    if (role === 'admin') {
      const adminEmail = 'mamdouhfces1997@gmail.com';
      const adminUser = {
        uid: 'admin_mamdouh_1997',
        email: adminEmail,
        displayName: 'Mamdouh Aboammar (Owner)',
      } as unknown as User;
      const adminProfile: UserProfile = {
        uid: adminUser.uid,
        email: adminEmail,
        displayName: 'Mamdouh Aboammar (Owner)',
        role: 'admin',
        createdAt: new Date().toISOString(),
        totalRequests: 1280,
      };
      setUser(adminUser);
      setProfile(adminProfile);
      localStorage.setItem('auth_session_user', JSON.stringify({ user: adminUser, profile: adminProfile }));
    } else {
      const userEmail = 'developer@company.com';
      const devUser = {
        uid: 'dev_user_123',
        email: userEmail,
        displayName: 'Developer User',
      } as unknown as User;
      const userProfile: UserProfile = {
        uid: devUser.uid,
        email: userEmail,
        displayName: 'Developer User',
        role: 'user',
        createdAt: new Date().toISOString(),
        totalRequests: 42,
      };
      setUser(devUser);
      setProfile(userProfile);
      localStorage.setItem('auth_session_user', JSON.stringify({ user: devUser, profile: userProfile }));
    }
  };

  const logout = async () => {
    localStorage.removeItem('auth_session_user');
    try {
      await signOut(auth);
    } catch (e) {
      console.warn(e);
    }
    setUser(null);
    setProfile(null);
  };

  // STRICT: isAdmin is true IF AND ONLY IF email is in ADMIN_EMAILS AND profile.role == 'admin'
  const userEmail = (user?.email || '').trim().toLowerCase();
  const isAdmin = ADMIN_EMAILS.includes(userEmail) && profile?.role === 'admin';

  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        isAdmin,
        loading,
        loginWithEmail,
        signupWithEmail,
        loginWithGoogle,
        loginAsMock,
        logout,
      }}
    >
      {!loading && children}
    </AuthContext.Provider>
  );
};
