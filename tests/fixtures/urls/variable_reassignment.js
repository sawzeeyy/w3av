// Test file: Variable reassignment

let base = "/api";
const url1 = base + "/users";

base = "/v2";
const url2 = base + "/products";

// Object property reassignment
const config = {
    endpoint: "/api"
};

const url3 = config.endpoint + "/data";

config.endpoint = "/v3";
const url4 = config.endpoint + "/resource";
