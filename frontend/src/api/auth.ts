import { apiClient } from "./client";
import type { LoginRequest, PasswordChangeRequest, TokenResponse, User } from "../types";

export async function login(payload: LoginRequest): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/auth/login", payload);
  return data;
}

export async function refresh(refreshToken: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/auth/refresh", {
    refresh_token: refreshToken,
  });
  return data;
}

export async function getCurrentUser(): Promise<User> {
  const { data } = await apiClient.get<User>("/auth/me");
  return data;
}

export async function logout(refreshToken: string): Promise<void> {
  await apiClient.post("/auth/logout", { refresh_token: refreshToken });
}

// Changes the signed-in user's own password. The answer is a new pair: every earlier token,
// this session's included, stops working.
export async function changePassword(payload: PasswordChangeRequest): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/auth/password", payload);
  return data;
}
