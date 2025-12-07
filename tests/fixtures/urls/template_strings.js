// Test file: Template literals with substitutions

const baseUrl = "https://api.example.com";
const version = "v2";
const userId = "123";

// Template strings
const endpoint1 = `${baseUrl}/users`;
const endpoint2 = `${baseUrl}/${version}/data`;
const userUrl = `/users/${userId}/profile`;

// Nested template strings
const fullUrl = `${baseUrl}/${version}/users/${userId}`;

// Mixed static and dynamic
const apiPath = `/api/v1/resource`;
