// Test file: String replace() method

const template = "/api/{version}/users";
const url1 = template.replace("{version}", "v2");

// With variables
const placeholder = "{id}";
const value = "123";
const path = "/users/{id}/profile";
const url2 = path.replace(placeholder, value);

// Multiple replacements
const baseTemplate = "/api/{env}/{resource}";
const url3 = baseTemplate.replace("{env}", "prod").replace("{resource}", "users");

// Variable references
const pattern = "/user/{userId}";
const userId = "456";
const url4 = pattern.replace("{userId}", userId);
