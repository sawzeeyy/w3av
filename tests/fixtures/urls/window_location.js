// Test file: Window.location specific behavior

// All window.location properties
const origin = window.location.origin;  // Should default to https://FUZZ
const href = window.location.href;
const protocol = window.location.protocol;
const hostname = window.location.hostname;
const port = window.location.port;
const pathname = window.location.pathname;
const search = window.location.search;
const hash = window.location.hash;
const host = window.location.host;

// Just location without window
const loc1 = location.origin;
const loc2 = location.href;
const loc3 = location.pathname;

// Concatenation with location properties
const apiUrl = window.location.origin + "/api/v1";
const fullUrl = location.protocol + "//" + location.host + location.pathname;
const withQuery = location.origin + "/search" + location.search;
