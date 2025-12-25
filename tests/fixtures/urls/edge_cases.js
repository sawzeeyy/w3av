// Test file: Edge cases and special scenarios

// Multiple URLs in one string
const errorMsg = "Failed to fetch from https://api.example.com/v1/users or https://backup.example.com/v2/users";

// Embedded URL in error message
throw new Error("Cannot connect to https://database.example.com/api");

// Protocol-relative URLs
const cdnUrl = "//cdn.example.com/static/app.js";
const resourceUrl = "//resources.example.com/images";

// Empty strings in concatenation
const url1 = "" + "https://example.com" + "";
const url2 = window.location.origin + "" + "/api";

// Very long URL
const longUrl = "https://very-long-domain-name.example.com/api/v1/resources/users/profiles/settings/preferences/notifications";

// Special characters in URLs
const encoded = "https://example.com/search?q=%20test%20&page=1";
const fragment = "https://example.com/page#section";

// Mixed quotes
const url3 = 'https://example.com/single-quotes';
const url4 = "https://example.com/double-quotes";
const url5 = `https://example.com/backticks`;

// Concatenation with undefined/unknown variables
const url6 = unknownVar + "/api/users";
const url7 = "/api" + unknownSuffix;
