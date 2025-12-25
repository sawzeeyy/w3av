// Test file: Route parameters (Express/Vue Router style and Next.js style)

// Colon-style route parameters
const userRoute = "/users/:id";
const postRoute = "/posts/:postId/comments/:commentId";
const profileRoute = "/users/:userId/profile/:section";

// Bracket-style parameters (Next.js)
const archiveUrl = "archives/vendor-list-v[VERSION].json";
const dynamicPage = "/posts/[ID]/comments/[commentId]";
const apiVersion = "/api/[version]/users";

// Mixed in concatenation
const baseApi = window.location.origin + "/api/users/:id";

// Template string with route params
const endpoint = `/users/:userId/posts/:postId`;
const dynamicPath = `/data/[category]/items/[itemId]`;
