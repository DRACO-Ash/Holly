export type UserRole = "analyst" | "operator" | "admin";

export interface User {
  id: string;
  username: string;
  email: string | null;
  role: UserRole;
  is_active: boolean;
  // Set when an admin chose the password: the user must choose their own before anything else.
  must_change_password: boolean;
  created_at: string;
}

export interface PasswordChangeRequest {
  current_password: string;
  new_password: string;
}

export interface UserCreateRequest {
  username: string;
  email: string | null;
  role: UserRole;
  temporary_password: string;
}

export interface UserUpdateRequest {
  role?: UserRole;
  is_active?: boolean;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}
