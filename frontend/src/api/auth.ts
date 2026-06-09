import client from "./client";
import type { AuthUser } from "@/store/authStore";

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface LoginResponse {
  token: TokenResponse;
  user: AuthUser;
}

export interface RegisterRequest {
  username: string;
  password: string;
  role?: string;
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
}

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const response = await client.post<LoginResponse>("/auth/login", data);
  return response.data;
}

export async function register(data: RegisterRequest): Promise<AuthUser> {
  const response = await client.post<AuthUser>("/auth/register", data);
  return response.data;
}

export async function getMe(): Promise<AuthUser> {
  const response = await client.get<AuthUser>("/auth/me");
  return response.data;
}

export async function changePassword(data: ChangePasswordRequest): Promise<{ message: string }> {
  const response = await client.post<{ message: string }>("/auth/change-password", data);
  return response.data;
}
