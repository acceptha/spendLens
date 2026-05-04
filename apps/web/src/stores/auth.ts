import { create } from "zustand";

type AuthState = {
  accessToken: string | null;
  setAccess: (t: string | null) => void;
  isAuthed: () => boolean;
};

export const useAuth = create<AuthState>((set, get) => ({
  accessToken: null,
  setAccess: (t) => set({ accessToken: t }),
  isAuthed: () => !!get().accessToken,
}));
