import { createContext, useContext, useState, useEffect, ReactNode } from "react";

type UserMode = "simple" | "advanced";

interface UserModeContextType {
  mode: UserMode;
  setMode: (mode: UserMode) => void;
  toggleMode: () => void;
  isAdvanced: boolean;
}

const UserModeContext = createContext<UserModeContextType | undefined>(undefined);

export function UserModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<UserMode>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("user-mode");
      return (saved as UserMode) || "simple";
    }
    return "simple";
  });

  useEffect(() => {
    localStorage.setItem("user-mode", mode);
  }, [mode]);

  const setMode = (newMode: UserMode) => {
    setModeState(newMode);
  };

  const toggleMode = () => {
    setModeState((prev) => (prev === "simple" ? "advanced" : "simple"));
  };

  const value: UserModeContextType = {
    mode,
    setMode,
    toggleMode,
    isAdvanced: mode === "advanced",
  };

  return (
    <UserModeContext.Provider value={value}>
      {children}
    </UserModeContext.Provider>
  );
}

export function useUserMode() {
  const context = useContext(UserModeContext);
  if (context === undefined) {
    throw new Error("useUserMode must be used within a UserModeProvider");
  }
  return context;
}
