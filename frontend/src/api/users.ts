import { apiClient } from "./client";
import type { User, UserCreateRequest, UserUpdateRequest } from "../types";

// The Users page's calls; Holly answers each with 403 to anyone but an admin.

export async function listUsers(): Promise<User[]> {
  const { data } = await apiClient.get<User[]>("/users");
  return data;
}

export async function createUser(payload: UserCreateRequest): Promise<User> {
  const { data } = await apiClient.post<User>("/users", payload);
  return data;
}

export async function resetPassword(userId: string, temporaryPassword: string): Promise<User> {
  const { data } = await apiClient.post<User>(`/users/${encodeURIComponent(userId)}/password`, {
    temporary_password: temporaryPassword,
  });
  return data;
}

export async function updateUser(userId: string, payload: UserUpdateRequest): Promise<User> {
  const { data } = await apiClient.patch<User>(`/users/${encodeURIComponent(userId)}`, payload);
  return data;
}
