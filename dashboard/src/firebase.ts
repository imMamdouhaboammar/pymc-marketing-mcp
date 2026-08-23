import { initializeApp, getApps, getApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyBOo4oMi-80xhcZAH3eT8dCvCTSmulqqSA",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "project-10698895-5ed8-4764-bb7.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "project-10698895-5ed8-4764-bb7",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "pymc-marketing-storage-project-10698895-5ed8-4764-bb7",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "699454963470",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:699454963470:web:d1fc44130ae34c7a"
};

const app = !getApps().length ? initializeApp(firebaseConfig) : getApp();
export const auth = getAuth(app);
export const db = getFirestore(app);

export const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({
  prompt: 'select_account'
});

export default app;
