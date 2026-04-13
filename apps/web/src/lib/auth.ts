import Cookies from "js-cookie";

export function setToken(token: string) {
  Cookies.set("access_token", token, { expires: 1, secure: process.env.NODE_ENV === "production" });
}

export function getToken() {
  return Cookies.get("access_token");
}

export function removeToken() {
  Cookies.remove("access_token");
}

export function isAuthenticated() {
  return !!getToken();
}
