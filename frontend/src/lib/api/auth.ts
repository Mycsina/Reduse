import apiClient from '../api-client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useToast } from '@/hooks/use-toast';

const AUTH_BASE = '/auth';
const USERS_BASE = '/users';

const COOKIE_NAME = 'reduseauth';

const AUTH_QUERY_KEY_PREFIX = 'auth';

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface UserCreate {
  email: string;
  password: string;
}

export interface User {
  id?: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
  created_at?: string;
}

// --- Query Hook ---
export function useCurrentUser() {
  return useQuery<User | null, Error>({
    queryKey: [AUTH_QUERY_KEY_PREFIX, 'currentUser'],
    queryFn: async () => {
        try {
            const user = await apiClient._fetch(`${USERS_BASE}/me`);
            return user as User | null;
        } catch (error: any) {
            if (error.status === 401) {
                return null;
            }
            console.error('Failed to fetch current user:', error);
            throw error;
        }
    },
    staleTime: Infinity,
    gcTime: Infinity,
    retry: false,
  });
}

// --- Mutation Hooks ---
export function useLoginMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<void, Error, LoginCredentials>({
    mutationFn: async (credentials: LoginCredentials) => {
        const formData = new FormData();
        formData.append('username', credentials.email);
        formData.append('password', credentials.password);

        const response = await fetch(`${apiClient.baseUrl}${AUTH_BASE}/jwt/login`, {
            method: 'POST',
            body: formData,
            credentials: 'include',
        });

        if (!response.ok) {
            let errorData;
            try {
                errorData = await response.json();
            } catch (e) {
                errorData = { detail: `HTTP error! status: ${response.status}` };
            }
            console.error('Login failed:', errorData);
            throw new Error(errorData.detail || 'Login failed');
        }
        console.log('Login request successful, auth cookie should be set.');
    },
    onSuccess: () => {
      toast({ title: "Login Successful", description: "You are now logged in." });
      queryClient.invalidateQueries({ queryKey: [AUTH_QUERY_KEY_PREFIX, 'currentUser'] });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Login Failed", description: error.message });
    },
  });
}

export function useLogoutMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  return useMutation<void, Error, void>({
    mutationFn: async () => {
        try {
            const response = await fetch(`${apiClient.baseUrl}${AUTH_BASE}/jwt/logout`, {
                method: 'POST',
                credentials: 'include',
            });
            if (!response.ok) {
                console.warn(`Server logout failed with status ${response.status}, but attempting client-side cookie clear.`);
            }
        } catch (error) {
            console.error("Error during server logout fetch:", error);
        }
        
        console.log("Clearing auth cookie client-side.");
        document.cookie = `${COOKIE_NAME}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax; Secure`;
    },
    onSuccess: () => {
      toast({ title: "Logout Successful", description: "You have been logged out." });
      queryClient.setQueryData([AUTH_QUERY_KEY_PREFIX, 'currentUser'], null);
      queryClient.invalidateQueries({ queryKey: [AUTH_QUERY_KEY_PREFIX, 'currentUser'] });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Logout Failed", description: error.message || "An error occurred during logout." });
    },
  });
}

export function useRegisterMutation() {
  const { toast } = useToast();
  return useMutation<User, Error, UserCreate>({
    mutationFn: (details: UserCreate) => 
        apiClient._fetch(`${AUTH_BASE}/register`, {
            method: 'POST',
            body: JSON.stringify(details),
            headers: {
                'Content-Type': 'application/json',
            },
        }),
    onSuccess: (data) => {
      toast({ title: "Registration Successful", description: `User ${data.email} registered. Please check your email if verification is required.` });
    },
    onError: (error) => {
      toast({ variant: "destructive", title: "Registration Failed", description: error.message });
    },
  });
} 