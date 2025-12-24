// Test file with various JavaScript escape sequences in URLs

// Hex escapes
const url1 = "/api/example?param1\x3dvalue1";

// Unicode escapes
const url2 = "/api/example?param2\u003dvalue2";

// Unicode code points
const url3 = "/api/example?param3\u{003D}value3";

// Octal escapes
const url4 = "/api/example?param4\075value4";

// Mixed escapes
const url5 = "/api/test?a\x3d1&b\u003d2&c\075d";

// In template strings
const url6 = `/api/endpoint?key\x3dval`;
