// Test file: Binary expressions (concatenation)

const base = "/api";
const proto = "https://";
const host = "example.com";

// Simple concatenation
const url1 = proto + host + base;
const url2 = base + "/users";

// Complex concatenation
const url3 = window.location.origin + "/api/login";

// Nested concatenation
const path = "/v1" + "/data";
const fullPath = base + path + "/endpoint";

// With variables
const endpoint = "/users";
const action = "/profile";
const url4 = base + endpoint + action;
