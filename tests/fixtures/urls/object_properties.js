// Test file: Object properties and nested objects

const config = {
    base: "/api",
    version: "/v2"
};

const endpoints = {
    users: "/users",
    posts: "/posts"
};

// Object property access
const url1 = config.base + endpoints.users;
const url2 = config.version + endpoints.posts;

// Nested objects
const settings = {
    api: {
        base: "/api",
        version: "/v1",
        endpoints: {
            users: "/users",
            data: "/data"
        }
    }
};

const userUrl = settings.api.base + settings.api.endpoints.users;
const dataUrl = settings.api.version + settings.api.endpoints.data;

// Object property assignment
config.newEndpoint = "/v3";
const url3 = config.newEndpoint + "/resource";
