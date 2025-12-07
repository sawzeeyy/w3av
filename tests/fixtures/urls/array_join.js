// Test file: Array join() method

// Array with strings
const pathSegments = ["/api", "/v2", "/users"];
const url1 = pathSegments.join("");

// Array with separator
const segments = ["api", "v1", "data"];
const path = segments.join("/");
const url2 = "https://api.example.com/" + path;

// Array with variable references
const base = "/api";
const version = "/v2";
const paths = [base, version, "/endpoint"];
const url3 = "https://example.com" + paths.join("");

// Mixed: array in concatenation
const parts = ["/users", "/profile"];
const endpoint = parts.join("") + "/settings";
