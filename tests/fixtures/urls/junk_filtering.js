// Test file: Junk URLs that should be filtered out

// MIME types (should be filtered)
const mime1 = "application/json";
const mime2 = "text/html; charset=utf-8";
const mime3 = "image/png";
const mime4 = "multipart/form-data";

// Incomplete protocols (should be filtered)
const incomplete1 = "https://";
const incomplete2 = "//";
const incomplete3 = "http:";

// Property paths (should be filtered)
const property1 = "action.target.value";
const property2 = "util.promisify.custom";
const property3 = "user.profile.name";

// W3C namespaces (should be filtered)
const w3c = "http://www.w3.org/2000/svg";

// Generic paths (should be filtered)
const generic1 = "/{t}";
const generic2 = "//FUZZ";
const generic3 = "./";

// Test URLs (should be filtered)
const test1 = "http://localhost";
const test2 = "http://a";

// URLs with unbalanced brackets (should be cleaned)
throw new Error("See https://github.com/apollographql/invariant-packages)");
const url1 = "https://api.example.com/endpoint]";

// Valid URLs (should be kept)
const validUrl = "https://api.example.com/users";
const validPath = "/api/v2/users";
const validDomain = "api.github.com";
