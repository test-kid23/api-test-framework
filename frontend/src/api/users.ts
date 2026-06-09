import client from "./client";
import type { AuthUser } from "@/store/authStore";

export interface PaginatedUsers {
  items: AuthUser[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

export interface AdminCreateUserRequest {
  username: string;
  password: string;
  role: "admin" | "editor" | "viewer";
  is_active: boolean;
}

export interface AdminUpdateUserRequest {
  role?: "admin" | "editor" | "viewer";
  is_active?: boolean;
  new_password?: string;
}

export async function listUsers(
  page = 1,
  pageSize = 20,
  search?: string
): Promise<PaginatedUsers> {
  const response = await client.get<PaginatedUsers>("/users", {
    params: { page, page_size: pageSize, search },
  });
  return response.data;
}

export async function createUser(
  data: AdminCreateUserRequest
): Promise<AuthUser> {
  const response = await client.post<AuthUser>("/users", data);
  return response.data;
}

export async function updateUser(
  userId: string,
  data: AdminUpdateUserRequest
): Promise<AuthUser> {
  const response = await client.patch<AuthUser>(`/users/${userId}`, data);
  return response.data;
}

export async function deleteUser(
  userId: string
): Promise<{ message: string }> {
  const response = await client.delete<{ message: string }>(
    `/users/${userId}`
  );
  return response.data;
}
