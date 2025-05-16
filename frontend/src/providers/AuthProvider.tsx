"use client";

import React, {
  createContext,
  useContext,
  ReactNode,
} from "react";

import {
  LoginCredentials,
  User,
  UserCreate,
  useCurrentUser,
  useLoginMutation,
  useLogoutMutation,
  useRegisterMutation,
} from "@/lib/api/auth";

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
  register: (userData: UserCreate) => Promise<void>;
  fetchUser: () => Promise<unknown>; // To match useCurrentUser's refetch signature
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {

  const {
    data: user,
    isLoading: isUserLoading,
    refetch: refetchUser,
  } = useCurrentUser();

  const loginMutation = useLoginMutation();
  const logoutMutation = useLogoutMutation();
  const registerMutation = useRegisterMutation();

  const login = async (credentials: LoginCredentials) => {
    try {
      await loginMutation.mutateAsync(credentials);
    } catch (error) {
      console.error("AuthProvider: Login failed:", error);
      throw error;
    }
  };

  const logout = async () => {
    try {
      await logoutMutation.mutateAsync();
    } catch (error) {
      console.error("AuthProvider: Logout failed:", error);
      throw error;
    }
  };

  const register = async (userData: UserCreate) => {
    try {
      await registerMutation.mutateAsync(userData);
    } catch (error) {
      console.error("AuthProvider: Registration failed:", error);
      throw error;
    }
  };

  const isLoading =
    isUserLoading ||
    loginMutation.isPending ||
    logoutMutation.isPending ||
    registerMutation.isPending;
  const isAuthenticated = !!user;

  return (
    <AuthContext.Provider
      value={{
        user: user || null, // Ensure user is User | null
        isLoading,
        isAuthenticated,
        login,
        logout,
        register,
        fetchUser: refetchUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
