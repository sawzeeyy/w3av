// Test file: Chained concat() calls

// Simple chaining
const url1 = "https://api.example.com".concat("/v2").concat("/users").concat("/profile");

// Chaining with variables
const base = "/api";
const url2 = "".concat(window.location.origin).concat(base).concat("/login");

// Complex chaining
const proto = "https://";
const host = "example.com";
const url3 = "".concat(proto).concat(host).concat("/api").concat("/v1").concat("/data");

// Mixed literals and variables
const version = "/v2";
const endpoint = "users";
const url4 = "".concat("/api").concat(version).concat("/").concat(endpoint);
