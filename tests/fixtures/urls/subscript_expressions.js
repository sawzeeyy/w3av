// Test file: Subscript expressions (bracket notation)

const obj = {
    "api-url": "https://api.example.com",
    "base": "/api"
};

// String literal subscripts
const url1 = obj["api-url"] + "/users";
const url2 = obj["base"] + "/v2";

// Variable subscripts
const key1 = "api-url";
const key2 = "base";
const url3 = obj[key1] + "/data";
const url4 = obj[key2] + "/posts";

// Nested subscripts
const config = {
    "endpoints": {
        "v1": "/api/v1",
        "v2": "/api/v2"
    }
};

const endpoint = config["endpoints"]["v1"] + "/users";
