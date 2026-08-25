import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { authService } from '../services/authService';
import type { UserOut, LoginInput } from '../types/api';

interface AuthContextType {
  user: UserOut | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (payload: LoginInput) => Promise<void>;
  signUp: (payload: any) => Promise<{ message: string; requiresConfirmation: boolean } | void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserOut | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const checkSession = async () => {
    const savedToken = localStorage.getItem('token');
    if (!savedToken) {
      setIsLoading(false);
      return;
    }
    try {
      const data = await authService.me();
      setUser(data.user);
      setToken(savedToken);
    } catch (error) {
      // Clear invalid tokens
      localStorage.removeItem('token');
      setToken(null);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    checkSession();
  }, []);

  const login = async (payload: LoginInput) => {
    setIsLoading(true);
    try {
      const session = await authService.login(payload);
      localStorage.setItem('token', session.access_token);
      setToken(session.access_token);
      setUser(session.user);
    } catch (error) {
      localStorage.removeItem('token');
      setToken(null);
      setUser(null);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const signUp = async (payload: any) => {
    setIsLoading(true);
    try {
      const result = await authService.signUp(payload);
      if (result && 'requiresConfirmation' in result && result.requiresConfirmation) {
        return result;
      } else if (result && 'access_token' in result) {
        localStorage.setItem('token', result.access_token);
        setToken(result.access_token);
        setUser(result.user);
      }
    } catch (error) {
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      if (token) {
        await authService.logout();
      }
    } catch (e) {
      // Ignore network failures on logout and proceed with local cleanup
    } finally {
      localStorage.removeItem('token');
      setToken(null);
      setUser(null);
      setIsLoading(false);
    }
  };

  const refreshUser = async () => {
    try {
      const data = await authService.me();
      setUser(data.user);
    } catch (e) {
      // Ignore errors
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user,
        isLoading,
        login,
        signUp,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
