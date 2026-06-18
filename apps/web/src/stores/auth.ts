import { create } from "zustand";

type AuthState = {
  accessToken: string | null;
  /** false until the on-boot refresh attempt resolves. Gates ProtectedRoute so a
   *  hard reload doesn't bounce to /login before the refresh cookie rehydrates. */
  authReady: boolean;
  setAccess: (t: string | null) => void;
  setAuthReady: (v: boolean) => void;
  isAuthed: () => boolean;
};

export const useAuth = create<AuthState>((set, get) => ({
  accessToken: null,
  authReady: false,
  setAccess: (t) => set({ accessToken: t }),
  setAuthReady: (v) => set({ authReady: v }),
  isAuthed: () => !!get().accessToken,
}));
