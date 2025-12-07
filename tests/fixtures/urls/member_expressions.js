// Test file: Member expressions (window.location, nested objects)

// window.location properties
const origin = window.location.origin;
const href = window.location.href;
const pathname = window.location.pathname;
const host = window.location.host;

// Concatenation with window.location
const apiUrl = window.location.origin + "/api/users";
const fullPath = window.location.protocol + "//" + window.location.host + "/path";

// Nested member expressions
const config = {
    server: {
        base: {
            url: "https://api.example.com"
        }
    }
};

const serverUrl = config.server.base.url + "/endpoint";
